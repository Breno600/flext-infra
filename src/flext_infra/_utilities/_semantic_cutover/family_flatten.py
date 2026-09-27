"""Plan the installed single-wrapper rule against one Rope snapshot."""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, config, m, p, t

from ..rope_runtime_modules import FlextInfraUtilitiesRopeRuntimeModules
from ..rope_runtime_refactors import FlextInfraUtilitiesRopeRuntimeRefactors
from ..rope_structure import FlextInfraUtilitiesRopeStructure
from .family_references import FlextInfraUtilitiesSemanticFamilyReferences


class FlextInfraUtilitiesSemanticFamilyFlatten(
    FlextInfraUtilitiesSemanticFamilyReferences
):
    """Flatten only private family parts, preserving real entity classes."""

    @classmethod
    def _family_flatten_edits(
        cls, workspace: p.Infra.RopeWorkspaceDsl, sources: t.MappingKV[Path, str]
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        from flext_infra import u

        candidates = tuple(
            path
            for path in sources
            if path.parent.name in c.Infra.FAMILY_DIRECTORIES.values()
            and not sources[path].startswith(c.Infra.AUTOGEN_HEADERS)
        )
        if not candidates:
            return ()
        rule = m.Infra.FamilyFlattenRule.model_validate(
            u.Cli.yaml_safe_load(
                type(config).ssot_config_dir()
                / "rules/rope/flatten-family-namespace-wrapper.yaml"
            ).unwrap()
        )
        project = FlextInfraUtilitiesRopeRuntimeModules.snapshot_project(
            workspace.rope_project, sources
        )
        rewrites: dict[Path, list[m.Infra.SourceRewrite]] = {}
        wrappers = 0
        try:
            for path in candidates:
                count = cls._flatten_family_part(
                    workspace, project, path, sources, rewrites
                )
                wrappers += count
            edits: list[m.Infra.SemanticMigrationEdit] = []
            for path, changes in sorted(rewrites.items()):
                resource = project.get_resource(
                    path.relative_to(Path(project.root.real_path)).as_posix()
                )
                change = FlextInfraUtilitiesRopeRuntimeRefactors.content_change(
                    resource, sources[path], changes
                )
                edits.append(
                    m.Infra.SemanticMigrationEdit(
                        file_path=path,
                        original_source=sources[path],
                        updated_source=change.new_contents,
                        changes=(
                            f"{rule.id}: wrappers={wrappers}, edits={len(changes)}",
                        ),
                    )
                )
            return tuple(edits)
        finally:
            project.close()

    @classmethod
    def _flatten_family_part(
        cls,
        workspace: p.Infra.RopeWorkspaceDsl,
        project: p.Infra.RopeProject,
        path: Path,
        sources: t.MappingKV[Path, str],
        rewrites: dict[Path, list[m.Infra.SourceRewrite]],
    ) -> int:
        root = Path(project.root.real_path)
        module = project.get_pymodule(
            project.get_resource(path.relative_to(root).as_posix())
        )
        scope = module.get_scope()
        if scope is None:
            msg = f"family part has no Rope scope: {path}"
            raise ValueError(msg)
        owner_name = workspace.convention(path).module_policy.expected_family
        if owner_name is None:
            return 0
        owner_scope = next(
            (
                item
                for item in scope.get_scopes()
                if item.pyobject.get_name() == owner_name
            ),
            None,
        )
        if owner_scope is None:
            return 0
        children = owner_scope.get_scopes()
        if len(children) != 1 or children[0].get_kind() != "Class":
            return 0
        child = children[0]
        wrapper_name = child.pyobject.get_name()
        if set(owner_scope.get_defined_names()) != {wrapper_name}:
            return 0
        facts = FlextInfraUtilitiesRopeStructure.logical_statements(sources[path])
        header = next(item for item in facts if item.line == child.get_start())
        if header.category != c.Infra.StatementCategory.CLASS_DEF:
            return 0
        preceding = sources[path].splitlines()[: header.line - 1]
        if preceding and preceding[-1].lstrip().startswith("@"):
            return 0
        if FlextInfraUtilitiesRopeStructure.class_base_names(header) or any(
            item.get_kind() == "Function" for item in child.get_scopes()
        ):
            return 0
        names = child.get_defined_names()
        if not names:
            return 0
        body = tuple(
            item for item in facts if header.end_line < item.line <= child.get_end()
        )
        if not body:
            msg = f"inline namespace wrapper cannot be flattened safely: {path}"
            raise ValueError(msg)
        if any(
            item.enclosing_name == wrapper_name
            and item.category
            not in {
                c.Infra.StatementCategory.CLASS_DEF,
                c.Infra.StatementCategory.ASSIGN,
                c.Infra.StatementCategory.ANN_ASSIGN,
                c.Infra.StatementCategory.TYPE_ALIAS,
                c.Infra.StatementCategory.OTHER,
            }
            for item in body
        ):
            msg = f"namespace wrapper contains executable statements: {path}:{wrapper_name}"
            raise ValueError(msg)
        owner_header = next(
            item for item in facts if item.line == owner_scope.get_start()
        )
        if len(owner_scope.pyobject.get_superclasses()) != len(
            FlextInfraUtilitiesRopeStructure.class_base_names(owner_header)
        ):
            msg = f"family owner inheritance is unresolved: {path}:{owner_name}"
            raise ValueError(msg)
        occupied = set(owner_scope.pyobject.get_attributes()) - {wrapper_name}
        # Prefix merging is the public identity of a flattened domain. Keeping
        # an unprefixed child merely because it does not collide in this file
        # can still overwrite a peer mixed into the composed facade (for
        # example Promoted.WorkspaceSpec versus Base.WorkspaceSpec).
        renamed = {name: f"{wrapper_name}{name}" for name in names}
        if any(name in occupied for name in renamed.values()) or len(
            set(renamed.values())
        ) != len(renamed):
            msg = f"family wrapper prefix collision is ambiguous: {path}:{wrapper_name}"
            raise ValueError(msg)
        wrapper = owner_scope.get_defined_names()[wrapper_name]
        candidate_rewrites: dict[Path, list[m.Infra.SourceRewrite]] = {}
        for consumer, source in sources.items():
            if source.startswith(c.Infra.AUTOGEN_HEADERS):
                continue
            resource = project.get_resource(consumer.relative_to(root).as_posix())
            blocked, changes = cls._family_consumer_rewrites(
                project,
                resource,
                source,
                owner_name=owner_name,
                wrapper_name=wrapper_name,
                wrapper=wrapper,
                names=renamed,
            )
            if blocked:
                # A consumer treats the wrapper as a real entity; preserve the
                # candidate instead of publishing partial rewrites.
                return 0
            if changes:
                candidate_rewrites.setdefault(consumer, []).extend(changes)
        candidate_rewrites.setdefault(path, []).extend(
            FlextInfraUtilitiesRopeRuntimeRefactors.unwrap_class_rewrites(
                sources[path],
                header_start=header.line,
                header_end=header.end_line,
                body_end=child.get_end(),
                indentation=body[0].indent - header.indent,
            )
        )
        for consumer, changes in candidate_rewrites.items():
            rewrites.setdefault(consumer, []).extend(changes)
        return 1


__all__: list[str] = ["FlextInfraUtilitiesSemanticFamilyFlatten"]
