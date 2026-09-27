"""Root configuration namespaces and override payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from flext_cli import m

from flext_infra import t

from .. import FlextInfraModelsDepsToolConfig
from .._defaults import FlextInfraModelsDefaults
from .artifact import FlextInfraConfigModelsArtifact
from .contract import FlextInfraConfigModelsContract
from .release import FlextInfraConfigModelsRelease
from .static import FlextInfraConfigModelsStatic


class FlextInfraConfigModelsRoot:
    """Own root configuration and override namespaces."""

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
        enforcement: Annotated[
            FlextInfraConfigModelsStatic.StaticEnforcementSpec,
            m.Field(description="Rope-only static enforcement policy"),
        ]
        sed_patterns: Annotated[
            FlextInfraConfigModelsArtifact.SedPatternsSpec,
            m.Field(
                default_factory=FlextInfraConfigModelsArtifact.SedPatternsSpec,
                description="Declared literal replacement patterns for mass refactoring",
            ),
        ]
        refactor_csv_campaigns: Annotated[
            FlextInfraConfigModelsArtifact.RefactorCsvCampaignsSpec,
            m.Field(
                default_factory=FlextInfraConfigModelsArtifact.RefactorCsvCampaignsSpec,
                description="Declared CSV-driven rename campaigns for the mod verb",
            ),
        ]

    class Root(FlextInfraConfigModelsContract.ConfigContract):
        """Root payload deep-merged from flext-infra config files."""

        Infra: Annotated[
            FlextInfraConfigModelsRoot.Infra,
            m.Field(description="Validated flext-infra namespace"),
        ]

    class CodegenOverridesRoot(FlextInfraConfigModelsContract.ConfigContract):
        """Override root mirroring the codegen namespace."""

        codegen: Annotated[
            FlextInfraConfigModelsRoot._CodegenOverridesSection,
            m.Field(description="Override sections for the codegen namespace"),
        ]

    class _CodegenOverridesSection(FlextInfraConfigModelsContract.ConfigContract):
        """Override deltas that deep-merge onto codegen fields."""

        checkout_submodules_overrides: Annotated[
            Mapping[str, str],
            m.Field(
                default_factory=FlextInfraModelsDefaults.immutable_empty_mapping,
                description="Per-distribution checkout submodule override paths",
            ),
        ]
        ci_private_submodules: Annotated[
            Mapping[str, t.JsonMapping],
            m.Field(
                default_factory=FlextInfraModelsDefaults.immutable_empty_mapping,
                description="Per-distribution private submodule CI contracts",
            ),
        ]
        make: Annotated[
            FlextInfraConfigModelsRoot._MakeOverridesSection | None,
            m.Field(default=None, description="Make override deltas"),
        ] = None
        layout: Annotated[
            FlextInfraConfigModelsRoot._LayoutOverridesSection | None,
            m.Field(default=None, description="Layout override deltas"),
        ] = None

    class _MakeOverridesSection(FlextInfraConfigModelsContract.ConfigContract):
        """Override deltas for the generated Make contract."""

        custom_handler_profile_overrides: Annotated[
            Mapping[str, t.JsonMapping],
            m.Field(
                default_factory=FlextInfraModelsDefaults.immutable_empty_mapping,
                description="Per-profile custom handler policy overrides",
            ),
        ]

    class _LayoutOverridesSection(FlextInfraConfigModelsContract.ConfigContract):
        """Override deltas for the layout conformance contract."""

        project_overrides: Annotated[
            Mapping[str, t.JsonMapping],
            m.Field(
                default_factory=FlextInfraModelsDefaults.immutable_empty_mapping,
                description="Per-project layout override deltas",
            ),
        ]

    class CodegenOverridesSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Typed content of the codegen override layer."""

        Infra: Annotated[
            FlextInfraConfigModelsRoot.CodegenOverridesRoot,
            m.Field(description="flext-infra override namespace"),
        ]


__all__: list[str] = ["FlextInfraConfigModelsRoot"]
