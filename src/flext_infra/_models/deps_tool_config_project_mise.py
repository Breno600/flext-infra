"""Project-owned Mise configuration models."""

from __future__ import annotations

from typing import Annotated

from flext_cli import m

from flext_infra import t


class FlextInfraModelsDepsToolConfigProjectMise:
    """Project-local Mise tools extending fleet tool declarations."""

    class ProjectMiseTool(m.ArbitraryTypesModel):
        """One project-owned Mise tool with one exact version."""

        version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact version written to the generated .mise.toml."),
        ]

    class ProjectMiseConfig(m.ArbitraryTypesModel):
        """Exact project-owned Mise selectors and their tool declarations."""

        tools: Annotated[
            t.MappingKV[
                t.NonEmptyStr, FlextInfraModelsDepsToolConfigProjectMise.ProjectMiseTool
            ],
            m.Field(description="Project-local Mise tools added to generated config."),
        ]


__all__: list[str] = ["FlextInfraModelsDepsToolConfigProjectMise"]
