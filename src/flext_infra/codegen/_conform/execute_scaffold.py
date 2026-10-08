"""Scaffold parent-directory preparation for conformance execution.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, config, m, p, r, t, u
from flext_infra.codegen._conform.plan import FlextInfraCodegenConformPlan
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector


class FlextInfraCodegenConformExecuteScaffold(FlextInfraCodegenConformPlan):
    """Create and roll back config-declared scaffold parent chains.

    Composed into execution by MRO: plan <- execute scaffold <- execute.
    """

    def _prepare_scaffold_directories(
        self,
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicDirectoryState]]:
        """Create config-declared scaffold parent chains under the generation lock.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Cli.AtomicDirectoryState]]``.

        """
        planned_workspace = self._scaffold_plan(request)
        if planned_workspace.failure:
            return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].from_failure(
                planned_workspace,
            )
        (workspace, project), planned_present = planned_workspace.value
        if not planned_present or workspace is None or project is None:
            return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].ok(())
        destinations = self._scaffold_destination_directories(
            request,
            workspace,
            project,
        )
        if destinations.failure:
            return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].from_failure(
                destinations,
            )
        return self._create_scaffold_directories(destinations.value)

    def _scaffold_plan(
        self,
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[
        t.Pair[
            t.Pair[m.Infra.WorkspaceSpec | None, m.Infra.ProjectSpec | None],
            bool,
        ]
    ]:
        """Resolve the workspace and project metadata that drive scaffolding.

        Scaffolding a new project requires its declared metadata, and that
        path supplies the workspace explicitly. Conforming a repository that
        declares no project block has no scaffold chain to create — nothing
        to do is not invalid input, and treating it as an error made
        ``make gen`` unusable in every repository without its own manifest.

        Returns:
            The resulting ``p.Result[t.Pair[t.Pair[m.Infra.WorkspaceSpec |
                None, m.Infra.ProjectSpec | None], bool]]`` where the boolean
            marks plan presence (False means no scaffold chain applies).

        """
        result_type = r[
            t.Pair[
                t.Pair[m.Infra.WorkspaceSpec | None, m.Infra.ProjectSpec | None],
                bool,
            ]
        ]
        if (
            c.Infra.CodegenConformMode(request.mode)
            is not c.Infra.CodegenConformMode.APPLY
        ):
            return result_type.ok(((None, None), False))
        scaffolding = self.initial_workspace
        workspace = scaffolding
        if workspace is None:
            workspace_result = FlextInfraWorkspaceDetector.load_workspace_spec(
                request.root.expanduser().resolve(),
            )
            if workspace_result.failure:
                return result_type.from_failure(workspace_result)
            workspace = workspace_result.value
        project = workspace.project
        if project is None:
            if scaffolding is not None:
                return result_type.fail("scaffold workspace has no project metadata")
            return result_type.ok(((None, None), False))
        return result_type.ok(((workspace, project), True))

    @staticmethod
    def _scaffold_destination_directories(
        request: m.Infra.CodegenConformRequest,
        workspace: m.Infra.WorkspaceSpec,
        project: m.Infra.ProjectSpec,
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Derive the scaffold parent directories from the config template entries.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        """
        profile = workspace.repository.role
        root = request.root.expanduser().resolve()
        directories = {root}
        for entry in config.Infra.codegen.templates.entries:
            if profile not in entry.profiles:
                continue
            if entry.requires_beads and workspace.beads is None:
                continue
            destination = entry.destination.format(
                package_name=project.package_name,
                ns=project.namespace_attribute,
            )
            relative = Path(destination)
            if relative.is_absolute() or ".." in relative.parts:
                return r[t.VariadicTuple[Path]].fail(
                    f"template destination escapes repository root: {destination}",
                )
            directories.add((root / relative).parent)
        return r[t.VariadicTuple[Path]].ok(
            tuple(sorted(directories, key=u.Infra.path_depth)),
        )

    def _create_scaffold_directories(
        self,
        directories: t.VariadicTuple[Path],
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicDirectoryState]]:
        """Materialize the planned scaffold chains, rolling back on any failure.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Cli.AtomicDirectoryState]]
            ``.

        """
        result_type = r[t.VariadicTuple[m.Cli.AtomicDirectoryState]]
        created: list[m.Cli.AtomicDirectoryState] = []
        for directory in directories:
            planned = u.Cli.atomic_plan_directory_chain(directory)
            if planned.failure:
                rollback = self._rollback_scaffold_directories(tuple(created))
                if rollback.failure:
                    return result_type.fail(
                        f"{planned.error}; scaffold directory rollback failed: "
                        f"{rollback.error}",
                    )
                return result_type.from_failure(planned)
            materialized = u.Cli.atomic_create_directory_chain_guarded(
                planned.value,
                permission_mode=0o755,
            )
            if materialized.failure:
                rollback = self._rollback_scaffold_directories(tuple(created))
                if rollback.failure:
                    return result_type.fail(
                        f"{materialized.error}; scaffold directory rollback failed: "
                        f"{rollback.error}",
                    )
                return result_type.from_failure(materialized)
            created.extend(materialized.value)
        return result_type.ok(tuple(created))

    @staticmethod
    def _rollback_scaffold_directories(
        created: t.VariadicTuple[m.Cli.AtomicDirectoryState],
    ) -> p.Result[bool]:
        """Remove only directories created by this locked scaffold attempt.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for state in reversed(created):
            removed = u.Cli.atomic_delete_empty_directory_guarded(state)
            if removed.failure:
                return removed
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraCodegenConformExecuteScaffold"]
