"""Plan the installed single-wrapper rule against one Rope snapshot.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping, Sequence
from pathlib import Path

from flext_cli import u

from flext_infra import c, config, m, p, t
from flext_infra._utilities import (
    FlextInfraUtilitiesCodegenNamespace,
    FlextInfraUtilitiesRopeRuntimeModules,
    FlextInfraUtilitiesRopeRuntimeRefactors,
    FlextInfraUtilitiesRopeStructure,
)
from flext_infra._utilities._semantic_cutover.family_references import (
    FlextInfraUtilitiesSemanticFamilyReferences,
)


class FlextInfraUtilitiesSemanticFamilyFlatten(
    FlextInfraUtilitiesSemanticFamilyReferences,
):
    """Flatten only private family parts, preserving real entity classes."""

    @classmethod
    def _family_flatten_edits(
        cls,
        workspace: p.Infra.RopeWorkspaceDsl,
        sources: t.MappingKV[Path, str],
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:

        candidates = tuple(
            path
            for path in sources
            if FlextInfraUtilitiesCodegenNamespace.facade_family_of_directory(
                path.parent.name,
            )
            is not None
            and not sources[path].startswith(c.Infra.AUTOGEN_HEADERS)
        )
        if not candidates:
            return ()
        rule = m.Infra.FamilyFlattenRule.model_validate(
            u.Cli.yaml_safe_load(
                type(config).ssot_config_dir().parent
                / c.Infra.CODEMOD_ROPE_RULES_RELPATH
                / "flatten-family-namespace-wrapper.yaml",
            ).unwrap(),
        )
        project = FlextInfraUtilitiesRopeRuntimeModules.snapshot_project(
            workspace.rope_project,
            sources,
        )
        rewrites: MutableMapping[Path, list[m.Infra.SourceRewrite]] = {}
        wrappers = 0
        try:
            for path in candidates:
                count = cls._flatten_family_part(
                    workspace,
                    project,
                    path,
                    sources,
                    rewrites,
                )
                wrappers += count
            edits: list[m.Infra.SemanticMigrationEdit] = []
            for path, changes in sorted(rewrites.items()):
                resource = project.get_resource(
                    path.relative_to(Path(project.root.real_path)).as_posix(),
                )
                change = FlextInfraUtilitiesRopeRuntimeRefactors.content_change(
                    resource,
                    sources[path],
                    changes,
                )
                edits.append(
                    m.Infra.SemanticMigrationEdit(
                        file_path=path,
                        original_source=sources[path],
                        updated_source=change.new_contents,
                        changes=(
                            f"{rule.id}: wrappers={wrappers}, edits={len(changes)}",
                        ),
                    ),
                )
            return tuple(edits)
        finally:
            project.close()

    @classmethod
    def _wrapper_scopes(
        cls,
        workspace: p.Infra.RopeWorkspaceDsl,
        project: p.Infra.RopeProject,
        path: Path,
    ) -> t.Pair[p.Infra.RopeScopeDsl, p.Infra.RopeScopeDsl] | None:
        """Resolve the family owner scope and its single wrapper child.

        Returns:
            The resulting scope pair, or ``None`` when this part holds no
            flattenable inline wrapper.

        Raises:
            ValueError: If family part has no Rope scope.

        """
        root = Path(project.root.real_path)
        module = project.get_pymodule(
            project.get_resource(path.relative_to(root).as_posix()),
        )
        scope = module.get_scope()
        if scope is None:
            msg = f"family part has no Rope scope: {path}"
            raise ValueError(msg)
        owner_name = workspace.convention(path).module_policy.expected_family
        if owner_name is None:
            return None
        owner_scope = next(
            (
                item
                for item in scope.get_scopes()
                if item.pyobject.get_name() == owner_name
            ),
            None,
        )
        if owner_scope is None:
            return None
        children = owner_scope.get_scopes()
        if len(children) != 1 or children[0].get_kind() != "Class":
            return None
        child = children[0]
        if set(owner_scope.get_defined_names()) != {child.pyobject.get_name()}:
            return None
        return owner_scope, child

    @classmethod
    def _wrapper_layout(
        cls,
        child: p.Infra.RopeScopeDsl,
        source: str,
        path: Path,
    ) -> (
        t.Triple[
            m.Infra.LogicalStatement,
            t.VariadicTuple[m.Infra.LogicalStatement],
            t.Pair[int, int] | None,
        ]
        | None
    ):
        """Validate the wrapper header and collect its flat body span.

        Returns:
            The resulting ``(header, body, docstring span)`` triple, or
            ``None`` when the wrapper cannot flatten.

        Raises:
            ValueError: If inline namespace wrapper cannot be flattened safely.

        """
        facts = FlextInfraUtilitiesRopeStructure.logical_statements(source)
        header = next(item for item in facts if item.line == child.get_start())
        if header.category != c.Infra.StatementCategory.CLASS_DEF:
            return None
        preceding = source.splitlines()[: header.line - 1]
        if preceding and preceding[-1].lstrip().startswith("@"):
            return None
        if FlextInfraUtilitiesRopeStructure.class_base_names(header) or any(
            item.get_kind() == "Function" for item in child.get_scopes()
        ):
            return None
        names = child.get_defined_names()
        if not names:
            return None
        body = tuple(
            item for item in facts if header.end_line < item.line <= child.get_end()
        )
        if not body:
            msg = f"inline namespace wrapper cannot be flattened safely: {path}"
            raise ValueError(msg)
        wrapper_docstring = (
            (body[0].line, body[0].end_line)
            if source
            .splitlines()[body[0].line - 1]
            .lstrip()
            .startswith(('"""', "'''", '"', "'"))
            else None
        )
        return header, body, wrapper_docstring

    @classmethod
    def _verified_flatten(
        cls,
        project: p.Infra.RopeProject,
        source: str,
        path: Path,
        owner_scope: p.Infra.RopeScopeDsl,
        child: p.Infra.RopeScopeDsl,
    ) -> m.Infra.FamilyWrapperFlatten:
        """Build the flatten plan after proving the wrapper is safely removable.

        Returns:
            The resulting ``m.Infra.FamilyWrapperFlatten``.

        Raises:
            ValueError: If family owner inheritance is unresolved; or if family
                wrapper prefix collision is ambiguous.

        """
        wrapper_name = child.pyobject.get_name()
        owner_name = owner_scope.pyobject.get_name()
        facts = FlextInfraUtilitiesRopeStructure.logical_statements(source)
        owner_header = next(
            item for item in facts if item.line == owner_scope.get_start()
        )
        if len(owner_scope.pyobject.get_superclasses()) != len(
            FlextInfraUtilitiesRopeStructure.class_base_names(owner_header),
        ):
            msg = f"family owner inheritance is unresolved: {path}:{owner_name}"
            raise ValueError(msg)
        occupied = set(owner_scope.pyobject.get_attributes()) - {wrapper_name}
        # Prefix merging is the public identity of a flattened domain. Keeping
        # an unprefixed child merely because it does not collide in this file
        # can still overwrite a peer mixed into the composed facade (for
        # example Promoted.WorkspaceSpec versus Base.WorkspaceSpec).
        renamed = {name: f"{wrapper_name}{name}" for name in child.get_defined_names()}
        if any(name in occupied for name in renamed.values()) or len(
            set(renamed.values()),
        ) != len(renamed):
            msg = f"family wrapper prefix collision is ambiguous: {path}:{wrapper_name}"
            raise ValueError(msg)
        return m.Infra.FamilyWrapperFlatten(
            project=project,
            owner_name=owner_name,
            wrapper_name=wrapper_name,
            wrapper=owner_scope.get_defined_names()[wrapper_name],
            names=renamed,
        )

    @classmethod
    def _aggregate_consumer_rewrites(
        cls,
        project: p.Infra.RopeProject,
        sources: t.MappingKV[Path, str],
        flatten: m.Infra.FamilyWrapperFlatten,
    ) -> t.Pair[bool, MutableMapping[Path, list[m.Infra.SourceRewrite]]]:
        """Collect candidate consumer rewrites for non-generated sources.

        Returns:
            The resulting ``(blocked, candidate rewrites)`` pair.

        """
        root = Path(project.root.real_path)
        candidate_rewrites: MutableMapping[Path, list[m.Infra.SourceRewrite]] = {}
        for consumer, source in sources.items():
            if source.startswith(c.Infra.AUTOGEN_HEADERS):
                continue
            resource = project.get_resource(consumer.relative_to(root).as_posix())
            blocked, changes = cls._family_consumer_rewrites(
                resource,
                source,
                flatten=flatten,
            )
            if blocked:
                return True, candidate_rewrites
            if changes:
                candidate_rewrites.setdefault(consumer, []).extend(changes)
        return False, candidate_rewrites

    @classmethod
    def _flatten_family_part(
        cls,
        workspace: p.Infra.RopeWorkspaceDsl,
        project: p.Infra.RopeProject,
        path: Path,
        sources: t.MappingKV[Path, str],
        rewrites: MutableMapping[Path, list[m.Infra.SourceRewrite]],
    ) -> int:

        scopes = cls._wrapper_scopes(workspace, project, path)
        if scopes is None:
            return 0
        owner_scope, child = scopes
        layout = cls._wrapper_layout(child, sources[path], path)
        if layout is None:
            return 0
        header, body, wrapper_docstring = layout
        flatten = cls._verified_flatten(
            project,
            sources[path],
            path,
            owner_scope,
            child,
        )
        blocked, candidate_rewrites = cls._aggregate_consumer_rewrites(
            project,
            sources,
            flatten,
        )
        if blocked:
            # A consumer treats the wrapper as a real entity; preserve the
            # candidate instead of publishing partial rewrites.
            return 0
        if cls._has_uncovered_wrapper_member(
            project,
            sources,
            flatten,
            candidate_rewrites,
        ):
            # A caller still names the wrapper. Flattening would drop that
            # name, so the wrapper stays a real namespace.
            return 0
        candidate_rewrites.setdefault(path, []).extend(
            FlextInfraUtilitiesRopeRuntimeRefactors.unwrap_class_rewrites(
                sources[path],
                m.Infra.ClassBlockLayout(
                    header_start=header.line,
                    header_end=header.end_line,
                    body_end=child.get_end(),
                    indentation=body[0].indent - header.indent,
                    docstring_span=wrapper_docstring,
                ),
            ),
        )
        for consumer, consumer_rewrites in candidate_rewrites.items():
            rewrites.setdefault(consumer, []).extend(consumer_rewrites)
        return 1

    @classmethod
    def _has_uncovered_wrapper_member(
        cls,
        project: p.Infra.RopeProject,
        sources: t.MappingKV[Path, str],
        flatten: m.Infra.FamilyWrapperFlatten,
        rewrites: t.MappingKV[Path, Sequence[m.Infra.SourceRewrite]],
    ) -> bool:
        """Return whether a resolved wrapper member has no planned rewrite.

        Returns:
            Whether a resolved wrapper member has no planned rewrite.

        """
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        root = Path(project.root.real_path)
        for path, source in sources.items():
            if source.startswith(c.Infra.AUTOGEN_HEADERS):
                continue
            resource = project.get_resource(path.relative_to(root).as_posix())
            module = project.get_pymodule(resource)
            covered = rewrites.get(path, ())
            for node in ast.walk(ast.parse(source)):
                if (
                    not isinstance(node, ast.Attribute)
                    or node.attr not in flatten.names
                ):
                    continue
                start, end = cls.expression_range(source, node)
                if any(edit.start <= start and end <= edit.end for edit in covered):
                    continue
                scope = runtime.scope_at(module, start)
                resolved = runtime.resolve_symbol(scope, node.value)
                if runtime.same_name(flatten.wrapper, resolved):
                    return True
                # An unresolved attribute that still spells the wrapper is a
                # caller the occurrence finder did not bind (a lazy facade).
                # Flattening would drop that name.
                value = node.value
                spells_wrapper = (
                    isinstance(value, ast.Name) and value.id == flatten.wrapper_name
                ) or (
                    isinstance(value, ast.Attribute)
                    and value.attr == flatten.wrapper_name
                )
                if resolved is None and spells_wrapper:
                    return True
        return False


__all__: list[str] = ["FlextInfraUtilitiesSemanticFamilyFlatten"]
