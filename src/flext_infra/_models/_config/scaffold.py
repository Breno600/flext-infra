"""Project scaffold specification models."""

from __future__ import annotations

from typing import Annotated

from flext_cli import m

from ... import t
from ..._constants import FlextInfraConstantsCodegenProject
from .contract import FlextInfraConfigModelsContract


class FlextInfraConfigModelsScaffold:
    """Project scaffold specification models."""

    class ScaffoldBuildSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Configured Python build backend for newly scaffolded projects."""

        backend: Annotated[t.NonEmptyStr, m.Field(description="PEP 517 backend")]
        requirements: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Build-system requirements"),
        ]

    class ScaffoldDependencyProfileSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Dependencies selected by the declared upstream FLEXT facade."""

        upstream: Annotated[
            t.NonEmptyStr, m.Field(description="Supported upstream facade package")
        ]
        project: Annotated[
            t.NonEmptyStr | None,
            m.Field(
                description="Distribution receiving additional requirements; unset selects the shared upstream profile"
            ),
        ] = None
        runtime: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Runtime requirements"),
        ]
        codegen: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Code-generation requirements"),
        ] = ()

    class ScaffoldProjectSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Project metadata policy for newly scaffolded distributions."""

        readme: Annotated[t.NonEmptyStr, m.Field(description="PEP 621 readme path")]
        supported_licenses: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Licenses with complete templates"),
        ]
        classifiers: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Default PyPI classifiers"),
        ]
        keywords: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Default project keywords"),
        ] = ()
        copyright_year: Annotated[
            int,
            m.Field(
                ge=2025,
                description=(
                    "LICENSE/NOTICE year for existing-tree ProjectSpec. "
                    "Override scaffold.project.copyright_year; gen must not "
                    "use the clock."
                ),
            ),
        ]
        dev: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description="Canonical development and validation requirements",
            ),
        ]
        dependency_profiles: Annotated[
            t.VariadicTuple[
                FlextInfraConfigModelsScaffold.ScaffoldDependencyProfileSpec
            ],
            m.Field(min_length=1, description="Upstream dependency profiles"),
        ]

    class ScaffoldPingExampleSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Values for the functional ping example created only by codegen new."""

        command_name: Annotated[
            t.NonEmptyStr, m.Field(description="Public CLI command")
        ]
        help_text: Annotated[
            t.NonEmptyStr, m.Field(description="Public CLI command help")
        ]
        success_message: Annotated[
            t.NonEmptyStr, m.Field(description="CLI success message")
        ]
        enabled_default: Annotated[
            bool, m.Field(description="Default runtime enablement")
        ]
        reply: Annotated[t.NonEmptyStr, m.Field(description="Enabled ping response")]
        disabled_reply: Annotated[
            t.NonEmptyStr, m.Field(description="Disabled ping response")
        ]

    class ScaffoldGitignoreSectionSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One configured section of the generated Git ignore policy."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Section heading")]
        patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Ignored path patterns"),
        ]
        profiles: Annotated[
            t.VariadicTuple[FlextInfraConstantsCodegenProject.MakeProfile],
            m.Field(
                description=(
                    "Make profiles this section applies to; empty means every "
                    "profile (universal). Sections that only make sense at the "
                    "superproject root (subproject-directory allowlists, workspace "
                    "manifest, submodule/Beads coordination) declare "
                    "[workspace] so subprojects and standalone projects never "
                    "receive the phantom entries."
                )
            ),
        ] = ()

    class ScaffoldSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Complete typed policy consumed only by new-project templates."""

        build: Annotated[
            FlextInfraConfigModelsScaffold.ScaffoldBuildSpec,
            m.Field(description="Build-system policy"),
        ]
        project: Annotated[
            FlextInfraConfigModelsScaffold.ScaffoldProjectSpec,
            m.Field(description="Project metadata and dependency policy"),
        ]
        ping_example: Annotated[
            FlextInfraConfigModelsScaffold.ScaffoldPingExampleSpec,
            m.Field(description="Functional scaffold example"),
        ]
        gitignore_sections: Annotated[
            t.VariadicTuple[
                FlextInfraConfigModelsScaffold.ScaffoldGitignoreSectionSpec
            ],
            m.Field(min_length=1, description="Generated Git ignore sections"),
        ]
