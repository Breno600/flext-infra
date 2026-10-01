"""Root configuration namespaces."""

from __future__ import annotations

from typing import Annotated

from flext_cli import m

from flext_infra import t

from ..deps import FlextInfraModelsDepsToolConfig
from .artifact import FlextInfraConfigModelsArtifact
from .contract import FlextInfraConfigModelsContract
from .release import FlextInfraConfigModelsRelease
from .static import FlextInfraConfigModelsStatic


class FlextInfraConfigModelsRoot:
    """Own the root configuration namespaces."""

    class Infra(FlextInfraConfigModelsContract.ConfigContract):
        """Complete flext-infra configuration namespace."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Project distribution name")]
        initial_project_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Version seeded into a newly scaffolded project"),
        ]
        codegen: Annotated[
            FlextInfraConfigModelsArtifact.CodegenConfigSpec,
            m.Field(description="Unified project and workspace codegen contract"),
        ]
        tooling: Annotated[
            FlextInfraModelsDepsToolConfig.ToolConfigDocument,
            m.Field(description="Validated lint, typecheck, and scaffold policy"),
        ]
        source_scan: Annotated[
            FlextInfraConfigModelsStatic.SourceScanSpec,
            m.Field(description="Production-only source discovery contract"),
        ]
        release: Annotated[
            FlextInfraConfigModelsRelease.ReleasePolicySpec,
            m.Field(description="Release protocol policy"),
        ]
        refactor_csv_campaigns: Annotated[
            FlextInfraConfigModelsArtifact.RefactorCsvCampaignsSpec,
            m.Field(
                description="Declared CSV-driven rename campaigns for the mod verb",
            ),
        ]

    class Root(FlextInfraConfigModelsContract.ConfigContract):
        """Root payload deep-merged from flext-infra config files."""

        Infra: Annotated[
            FlextInfraConfigModelsRoot.Infra,
            m.Field(description="Validated flext-infra namespace"),
        ]


__all__: list[str] = ["FlextInfraConfigModelsRoot"]
