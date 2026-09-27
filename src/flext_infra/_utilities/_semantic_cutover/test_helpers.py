"""Promote shared test behavior using its original Rope declaration identity."""

from __future__ import annotations

from pathlib import Path
from typing import override

import libcst as cst

from flext_infra import c, m, p, t

from .._rope_core_pymodule import FlextInfraUtilitiesRopeCorePyModuleMixin
from ..qualified_names import FlextInfraUtilitiesQualifiedNames
from ..rope_runtime_modules import FlextInfraUtilitiesRopeRuntimeModules
from .helper_references import FlextInfraUtilitiesSemanticHelperReferences


class FlextInfraUtilitiesSemanticTestHelpers(
    FlextInfraUtilitiesSemanticHelperReferences
):
    """Discover live fixture helpers and move them to their tier utilities owner."""

    class _MovedExports(cst.CSTTransformer):
        """Retire only the original declaration's former module export."""

        def __init__(self, name: str) -> None:
            self.names = frozenset({name})

        @override
        def leave_Assign[N: (cst.Assign, cst.AnnAssign)](
            self, original_node: N, updated_node: N
        ) -> N:
            return FlextInfraUtilitiesQualifiedNames.filter_exports(
                updated_node, self.names
            )

        @override
        def leave_AnnAssign(
            self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign
        ) -> cst.AnnAssign:
            return self.leave_Assign(original_node, updated_node)

    @classmethod
    def _test_helper_edits(
        cls, workspace: p.Infra.RopeWorkspaceDsl, sources: t.MappingKV[Path, str]
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        editable = {
            path.resolve(): source
            for path, source in sources.items()
            if not source.startswith(c.Infra.AUTOGEN_HEADERS)
        }
        candidates = tuple(
            path
            for path in sorted(editable)
            if c.Infra.DIR_TESTS in path.parts
            and workspace.convention(path).module_policy.is_fixture_module
        )
        if not candidates:
            return ()
        working = dict(sources)
        changes: dict[Path, list[str]] = {}
        for path in candidates:
            while True:
                project = FlextInfraUtilitiesRopeRuntimeModules.snapshot_project(
                    workspace.rope_project, working
                )
                try:
                    move = cls._shared_helper_move(
                        workspace, project, path, working, frozenset(editable)
                    )
                    if move is None:
                        break
                    planned = cls._helper_move_plan(
                        move, sources={path: working[path] for path in editable}
                    )
                    if not any(edit.file_path == path for edit in planned):
                        msg = f"shared test helper move did not remove its declaration: {path}"
                        raise ValueError(msg)
                    for edit in planned:
                        working[edit.file_path] = edit.updated_source
                        changes.setdefault(edit.file_path, []).extend(edit.changes)
                    working[path] = (
                        cst
                        .parse_module(working[path])
                        .visit(cls._MovedExports(move.class_name))
                        .code
                    )
                finally:
                    project.close()
        return tuple(
            m.Infra.SemanticMigrationEdit(
                file_path=path,
                original_source=sources[path],
                updated_source=working[path],
                changes=tuple(operations),
            )
            for path, operations in sorted(changes.items())
            if sources[path] != working[path]
        )

    @classmethod
    def _shared_helper_move(
        cls,
        workspace: p.Infra.RopeWorkspaceDsl,
        project: p.Infra.RopeProject,
        path: Path,
        sources: t.MappingKV[Path, str],
        editable: frozenset[Path],
    ) -> m.Infra.ClassMoveRequest | None:
        root = Path(project.root.real_path)
        resource = project.get_resource(path.relative_to(root).as_posix())
        scope = project.get_pymodule(resource).get_scope()
        if scope is None:
            msg = f"shared test helper module has no Rope scope: {path}"
            raise ValueError(msg)
        resources = tuple(
            project.get_resource(item.relative_to(root).as_posix())
            for item in sorted(editable)
        )
        for child in scope.get_scopes():
            if child.get_kind() != c.Infra.RopeScopeKind.CLASS:
                continue
            if not any(
                member.get_kind() == c.Infra.RopeScopeKind.FUNCTION
                for member in child.get_scopes()
            ) or any(
                name.startswith(c.Infra.NAMESPACE_PYTEST_MODULE_PREFIX)
                for name in child.pyobject.get_attributes()
            ):
                continue
            name = child.pyobject.get_name()
            offset = FlextInfraUtilitiesRopeCorePyModuleMixin.find_identifier_offset_in_lines(
                sources[path].splitlines(keepends=True),
                line=child.get_start(),
                symbol=name,
            )
            if offset is None:
                msg = f"shared helper declaration has no identifier: {path}:{name}"
                raise ValueError(msg)
            references = FlextInfraUtilitiesRopeRuntimeModules.runtime_find_occurrences(
                project, resource, offset, resources=resources, in_hierarchy=False
            )
            if not any(
                reference.resource is not None
                and Path(reference.resource.real_path).resolve() != path
                for reference in references
            ):
                continue
            target = cls._test_utilities_owner(workspace, path, sources)
            target_resource = project.get_resource(target.relative_to(root).as_posix())
            if name in project.get_pymodule(target_resource).get_attributes():
                msg = f"shared helper destination already binds {name}: {target}"
                raise ValueError(msg)
            return m.Infra.ClassMoveRequest(
                rope_project=project,
                source_file=path,
                target_file=target,
                class_name=name,
                line=child.get_start(),
                apply=False,
            )
        return None

    @staticmethod
    def _test_utilities_owner(
        workspace: p.Infra.RopeWorkspaceDsl, path: Path, sources: t.MappingKV[Path, str]
    ) -> Path:
        """Elect the unique declared utilities facade in this helper's tier."""
        prefix = workspace.convention(path).module_policy.project_prefix
        owners = tuple(
            candidate
            for candidate, source in sources.items()
            if candidate.parent in path.parents
            and not source.startswith(c.Infra.AUTOGEN_HEADERS)
            and (policy := workspace.convention(candidate).module_policy).expected_alias
            == "u"
            and policy.project_prefix == prefix
            and policy.is_internal_namespace
        )
        if len(owners) != 1:
            msg = f"shared test helper requires one utilities facade: {path}; owners={owners}"
            raise ValueError(msg)
        return owners[0]


__all__: list[str] = ["FlextInfraUtilitiesSemanticTestHelpers"]
