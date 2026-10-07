"""Project-owned managed-artifact configuration models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from flext_cli import m

from flext_infra import t
from flext_infra._models import (
    FlextInfraModelsDepsToolConfigProjectGitignore,
    FlextInfraModelsDepsToolConfigProjectMise,
)


class FlextInfraModelsDepsToolConfigProjectArtifacts(
    FlextInfraModelsDepsToolConfigProjectGitignore,
):
    """Managed-artifact models composed from project-owned slices."""

    class ProjectRuffConfig(m.ArbitraryTypesModel):
        """Project-owned Ruff exemptions for generated managed artifacts."""

        per_file_ignores: Annotated[
            t.Infra.PerFileIgnores,
            m.Field(
                description="Project-local per-file rules owned by this repository.",
            ),
        ]

    class ProjectManagedArtifactsConfig(m.ArbitraryTypesModel):
        """Project-owned configuration for generated artifacts."""

        Mise: Annotated[
            FlextInfraModelsDepsToolConfigProjectMise.ProjectMiseConfig,
            m.Field(description="Mise additions owned by the current project."),
        ]
        Gitignore: Annotated[
            FlextInfraModelsDepsToolConfigProjectGitignore.ProjectGitignoreConfig,
            m.Field(description="Ignore patterns owned by the current project."),
        ]
        Ruff: Annotated[
            FlextInfraModelsDepsToolConfigProjectArtifacts.ProjectRuffConfig,
            m.Field(description="Ruff additions owned by the current project."),
        ]

    class ProjectManagedArtifactsResolution(m.ArbitraryTypesModel):
        """Composed project configuration plus selector provenance."""

        artifacts: Annotated[
            FlextInfraModelsDepsToolConfigProjectArtifacts.ProjectManagedArtifactsConfig,
            m.Field(description="Composed managed-artifact configuration."),
        ]
        mise_tool_sources: Annotated[
            t.MappingKV[t.NonEmptyStr, Path],
            m.Field(description="Source YAML path for every local Mise selector."),
        ]

    class ProjectManagedArtifactsSnapshot(m.ArbitraryTypesModel):
        """One immutable YAML snapshot and its single parsed resolution."""

        sources: Annotated[
            t.VariadicTuple[m.Cli.AtomicFileState],
            m.Field(description="Ordered exact project configuration sources."),
        ]
        resolution: Annotated[
            FlextInfraModelsDepsToolConfigProjectArtifacts.ProjectManagedArtifactsResolution,
            m.Field(description="Managed artifacts parsed from those exact sources."),
        ]


__all__: list[str] = ["FlextInfraModelsDepsToolConfigProjectArtifacts"]
