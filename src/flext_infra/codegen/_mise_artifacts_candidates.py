"""Validated receipt and publication candidates for Mise transactions.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, r
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraMiseArtifactsCandidates:
    """Build the publication receipts of staged Mise artifacts."""

    @staticmethod
    def publication_plan(
        projects: t.VariadicTuple[m.Infra.MiseToolchainProjectState],
        stages: t.VariadicTuple[Path],
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenStagedFile]]:
        """Retain every staged artifact receipt, including unchanged destinations.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.CodegenStagedFile]]``.

        """
        publications: list[m.Infra.CodegenStagedFile] = []
        for project, stage in zip(projects, stages, strict=True):
            before_states = (
                project.config.before,
                project.artifacts.unix_launcher,
                project.artifacts.windows_launcher,
                project.artifacts.version_pin,
            )
            for before, (name, mode) in zip(
                before_states,
                c.Infra.PUBLICATION_SPECS,
                strict=True,
            ):
                replacement = files.read_state(stage / name, required=True)
                if replacement.failure or replacement.value.content is None:
                    return r[tuple[m.Infra.CodegenStagedFile, ...]].from_failure(
                        replacement,
                    )
                if replacement.value.mode != mode:
                    return r[tuple[m.Infra.CodegenStagedFile, ...]].fail(
                        f"staged Mise artifact mode differs: {stage / name}",
                    )
                publications.append(
                    m.Infra.CodegenStagedFile(
                        phase="mise",
                        project=project.layout.root,
                        before=before,
                        replacement=replacement.value,
                    ),
                )
        return r[tuple[m.Infra.CodegenStagedFile, ...]].ok(tuple(publications))


__all__: list[str] = ["FlextInfraMiseArtifactsCandidates"]
