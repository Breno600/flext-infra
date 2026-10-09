"""Promote shared test behavior using its original Rope declaration identity.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_infra import c, m, p, t
from flext_infra._utilities._rope_core_pymodule import (
    FlextInfraUtilitiesRopeCorePyModuleMixin,
)
from flext_infra._utilities._semantic_cutover.helper_references import (
    FlextInfraUtilitiesSemanticHelperReferences,
)
from flext_infra._utilities.qualified_names import FlextInfraUtilitiesQualifiedNames
from flext_infra._utilities.rope_runtime_modules import (
    FlextInfraUtilitiesRopeRuntimeModules,
)

if TYPE_CHECKING:
    import libcst as cst


class FlextInfraUtilitiesSemanticTestHelpers(
    FlextInfraUtilitiesSemanticHelperReferences,
):
    """Discover shared test helpers and move them to their tier utilities owner."""

    @classmethod
    def _test_helper_edits(
        cls,
        workspace: p.Infra.RopeWorkspaceDsl,
        sources: t.MappingKV[Path, str],
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        import libcst as cst

        class _MovedExports(cst.CSTTransformer):
            """Retire only the original declaration's former module export."""

            def __init__(self, name: str) -> None:
                self.names = frozenset({name})

            @override
            def leave_Assign[N: (cst.Assign, cst.AnnAssign)](
                self,
                original_node: N,
                updated_node: N,
            ) -> N:
                return FlextInfraUtilitiesQualifiedNames.filter_exports(
                    updated_node,
                    self.names,
                )

            @override
            def leave_AnnAssign(
                self,
                original_node: cst.AnnAssign,
                updated_node: cst.AnnAssign,
            ) -> cst.AnnAssign:
                return self.leave_Assign(original_node, updated_node)

        editable = {
            path.resolve(): source
            for path, source in sources.items()
            if not source.startswith(c.Infra.AUTOGEN_HEADERS)
        }
        candidates = tuple(
            path
            for path in sorted(editable)
            if c.Infra.DIR_TESTS in path.parts
            and (
                workspace.convention(path).module_policy.is_fixture_module
                or (path.stem.startswith("_") and path.stem != "__init__")
            )
        )
        if not candidates:
            return ()
        working = dict(sources)
        changes: MutableMapping[Path, list[str]] = {}
        for path in candidates:
            while True:
                project = FlextInfraUtilitiesRopeRuntimeModules.snapshot_project(
                    workspace.rope_project,
                    working,
                )
                try:
                    move = cls._shared_helper_move(
                        workspace,
                        project,
                        path,
                        working,
                        frozenset(editable),
                    )
                    if move is None:
                        break
                    planned = cls._helper_move_plan(
                        move,
                        sources={path: working[path] for path in editable},
                    )
                    if not any(edit.file_path == path for edit in planned):
                        msg = (
                            f"shared test helper move did not remove "
                            f"its declaration: {path}"
                        )
                        raise ValueError(msg)
                    for edit in planned:
                        working[edit.file_path] = edit.updated_source
                        changes.setdefault(edit.file_path, []).extend(edit.changes)
                    working[path] = (
                        cst
                        .parse_module(working[path])
                        .visit(_MovedExports(move.class_name))
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
        resources = tuple(
            project.get_resource(item.relative_to(root).as_posix())
            for item in sorted(editable)
        )
        declarations = tuple(
            node
            for node in ast.parse(sources[path]).body
            if isinstance(node, ast.ClassDef)
        )
        for declaration in declarations:
            name = declaration.name
            if not any(
                isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                for member in ast.walk(declaration)
            ) or any(
                member.name.startswith(c.Infra.NAMESPACE_PYTEST_MODULE_PREFIX)
                for member in ast.walk(declaration)
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
            ):
                continue
            find_offset = (
                FlextInfraUtilitiesRopeCorePyModuleMixin.find_identifier_offset_in_lines
            )
            offset = find_offset(
                sources[path].splitlines(keepends=True),
                line=declaration.lineno,
                symbol=name,
            )
            if offset is None:
                msg = f"shared helper declaration has no identifier: {path}:{name}"
                raise ValueError(msg)
            references = FlextInfraUtilitiesRopeRuntimeModules.runtime_find_occurrences(
                project,
                resource,
                offset,
                resources=resources,
                in_hierarchy=False,
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
                line=declaration.lineno,
                apply=False,
            )
        return None

    @staticmethod
    def _test_utilities_owner(
        workspace: p.Infra.RopeWorkspaceDsl,
        path: Path,
        sources: t.MappingKV[Path, str],
    ) -> Path:
        """Elect the unique declared utilities facade in this helper's tier.

        Returns:
            The resulting ``Path``.

        Raises:
            ValueError: If shared test helper requires one utilities facade.

        """
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
            msg = (
                f"shared test helper requires one utilities facade: {path}; "
                f"owners={owners}"
            )
            raise ValueError(msg)
        return owners[0]


__all__: list[str] = ["FlextInfraUtilitiesSemanticTestHelpers"]
