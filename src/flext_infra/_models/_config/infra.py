"""Typed root namespace for the flext-infra configuration document."""

from __future__ import annotations

from typing import Annotated

from flext_cli import m

from ... import t
from ..deps_tool_config import FlextInfraModelsDepsToolConfig
from .artifact import FlextInfraConfigModelsArtifact
from .contract import FlextInfraConfigModelsContract
from .release import FlextInfraConfigModelsRelease
from .static import FlextInfraConfigModelsStatic


class FlextInfraConfigModelsInfra:
    """Complete validated namespace consumed by ``config.Infra``."""

    class Infra(FlextInfraConfigModelsContract.ConfigContract):
        """Complete flext-infra configuration namespace."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Project distribution name")]
        initial_project_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Version seeded into a newly scaffolded project's pyproject; "
                    "from then on the release protocol is the only writer"
                )
            ),
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
            m.Field(description="Release protocol policy: eligibility, bumps, index"),
        ]
        enforcement: Annotated[
            FlextInfraConfigModelsStatic.StaticEnforcementSpec,
            m.Field(description="Rope-only static enforcement policy"),
        ]
        sed_patterns: Annotated[
            FlextInfraConfigModelsArtifact.SedPatternsSpec,
            m.Field(
                default_factory=FlextInfraConfigModelsArtifact.SedPatternsSpec,
                description="Sed-by-list mass replacement patterns for literal refactoring",
            ),
        ]
        check_policy: Annotated[
            FlextInfraConfigModelsArtifact.CheckPolicySpec,
            m.Field(
                default_factory=FlextInfraConfigModelsArtifact.CheckPolicySpec,
                description="Producer-owned global activation policy for finding gates",
            ),
        ]
        refactor_csv_campaigns: Annotated[
            FlextInfraConfigModelsArtifact.RefactorCsvCampaignsSpec,
            m.Field(
                default_factory=FlextInfraConfigModelsArtifact.RefactorCsvCampaignsSpec,
                description="Declared CSV-driven rename campaigns for the mod verb",
            ),
        ]


__all__: list[str] = ["FlextInfraConfigModelsInfra"]
