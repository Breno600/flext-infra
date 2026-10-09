"""Destination-local staging for complete Mise artifact projections.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, r, u
from flext_infra.codegen._mise_artifacts_candidates import (
    FlextInfraMiseArtifactsCandidates,
)
from flext_infra.codegen._mise_artifacts_process import (
    FlextInfraMiseArtifactsProcess as process,
)

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraMiseStaging:
    """Build every replacement before the journal permits live publication.

    Generation never produces a launcher: every selected project receives the
    exact bytes of the runtime root's `make upg` triple (the runtime root
    itself receives its own bytes, a no-op publication).
    """

    def stage(
        self,
        plan: m.Infra.MiseToolchainWorkspacePlan,
    ) -> p.Result[
        t.Pair[
            t.VariadicTuple[m.Infra.CodegenStagedFile],
            t.VariadicTuple[m.Cli.AtomicDirectoryState],
        ]
    ]:
        """Stage the runtime-root triple alongside each project's declaration.

        Returns:
            The resulting ``p.Result[t.Pair[t.VariadicTuple[m.Infra.CodegenStagedFile],
                t.VariadicTuple[m.Cli.AtomicDirectoryState]]]``.

        """
        result_type = r[
            tuple[
                tuple[m.Infra.CodegenStagedFile, ...],
                tuple[m.Cli.AtomicDirectoryState, ...],
            ]
        ]
        if not plan.projects:
            return result_type.fail("Mise plan declares no projects")
        projected = tuple(
            state.content
            for state in plan.runtime_artifacts.states
            if state.content is not None
        )
        if len(projected) != len(c.Infra.ARTIFACT_SPECS):
            return result_type.fail(
                "runtime Mise artifacts are incomplete; run make upg in "
                f"{plan.layout.scope_root}",
            )
        publications: list[m.Infra.CodegenStagedFile] = []
        directories: list[m.Cli.AtomicDirectoryState] = []
        for project in plan.projects:
            if project.layout.transaction_root is None:
                return result_type.fail(
                    f"Mise transaction root is absent: {project.layout.selector}",
                )
            stage_root = project.layout.transaction_root / "stage"
            staged = self._stage_project(
                project,
                stage_root=stage_root,
                projected=projected,
            )
            if staged.failure:
                return result_type.from_failure(staged)
            receipts = FlextInfraMiseArtifactsCandidates.publication_plan(
                (project,),
                (stage_root,),
            )
            if receipts.failure:
                return result_type.from_failure(receipts)
            publications.extend(receipts.value)
            directories.extend(staged.value)
        return result_type.ok((tuple(publications), tuple(directories)))

    @staticmethod
    def _stage_project(
        project: m.Infra.MiseToolchainProjectState,
        *,
        stage_root: Path,
        projected: t.VariadicTuple[bytes],
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicDirectoryState]]:
        """Build one project and retain its guarded directory creation receipts.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Cli.AtomicDirectoryState]]``.

        """
        result_type = r[tuple[m.Cli.AtomicDirectoryState, ...]]
        stage_plan = u.Cli.atomic_plan_directory_chain(stage_root / "bin")
        if stage_plan.failure:
            return result_type.from_failure(stage_plan)
        if tuple(stage_plan.value.directories) != (stage_root, stage_root / "bin"):
            return result_type.fail(
                f"Mise stage already exists for {project.layout.selector}",
            )
        created = u.Cli.atomic_create_directory_chain_guarded(
            stage_plan.value,
            permission_mode=0o700,
        )
        if created.failure:
            return result_type.from_failure(created)
        config_write = process.write_new(
            stage_root / c.Infra.CONFIG_SPEC[0],
            project.config.replacement_content,
            project.config.replacement_mode,
        )
        if config_write.failure:
            return result_type.from_failure(config_write)
        for content, (name, mode) in zip(
            projected,
            c.Infra.ARTIFACT_SPECS,
            strict=True,
        ):
            copied = process.write_new(stage_root / name, content, mode)
            if copied.failure:
                return result_type.from_failure(copied)
        return result_type.ok(tuple(created.value))


__all__: list[str] = ["FlextInfraMiseStaging"]
