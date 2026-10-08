"""Composed project-owned managed-artifact configuration document.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Annotated

from flext_cli import m

from flext_infra._models.deps_tool_config_project_artifacts import (
    FlextInfraModelsDepsToolConfigProjectArtifacts,
)


class FlextInfraModelsDepsToolConfigProject(
    FlextInfraModelsDepsToolConfigProjectArtifacts,
):
    """Document layer composing every project-owned managed-artifact model."""

    class ProjectManagedArtifactsFragment(m.ArbitraryTypesModel):
        """Optional project-owned sections present in one configuration source."""

        Mise: Annotated[
            FlextInfraModelsDepsToolConfigProjectArtifacts.ProjectMiseConfig | None,
            m.Field(description="Mise section declared by this source"),
        ] = None
        Gitignore: Annotated[
            FlextInfraModelsDepsToolConfigProjectArtifacts.ProjectGitignoreConfig
            | None,
            m.Field(description="Gitignore section declared by this source"),
        ] = None
        Ruff: Annotated[
            FlextInfraModelsDepsToolConfigProjectArtifacts.ProjectRuffConfig | None,
            m.Field(description="Ruff section declared by this source"),
        ] = None

    class ProjectConfigDocument(m.ArbitraryTypesModel):
        """Relevant managed-artifact slice loaded from project config files."""

        ManagedArtifacts: Annotated[
            FlextInfraModelsDepsToolConfigProject.ProjectManagedArtifactsFragment,
            m.Field(description="Project-local managed artifact configuration."),
        ]


# The composed document layer is the module's single declared owner. The
# layers below it are the mechanism of that composition -- each exists so a
# sibling model resolves as a base-class attribute at definition time -- and
# are reached through it, never imported on their own. Declaring them here
# made the module look like four competing owners, which left the class-nesting
# planner unable to name one and failed `make mod` for the whole fleet.
__all__: list[str] = ["FlextInfraModelsDepsToolConfigProject"]
