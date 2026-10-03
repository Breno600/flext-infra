"""Managed file and template entry specification models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self

from flext_cli import m

from flext_infra import t
from flext_infra._constants import FlextInfraConstantsCodegenProject
from flext_infra._models._config.contract import FlextInfraConfigModelsContract
from flext_infra._models._config.scaffold import FlextInfraConfigModelsScaffold


class FlextInfraConfigModelsTemplates:
    """Managed file and template entry specification models."""

    class TemplateEntrySpec(FlextInfraConfigModelsContract.ConfigContract):
        """One scaffold artifact and its typed rendering owner."""

        source: Annotated[
            Path | None,
            m.Field(description="Template-root-relative source for render entries"),
        ] = None
        destination: Annotated[
            t.NonEmptyStr,
            m.Field(description="Tokenized repository-relative destination"),
        ]
        profiles: Annotated[
            t.VariadicTuple[FlextInfraConstantsCodegenProject.MakeProfile],
            m.Field(description="Profiles that consume the template"),
        ]
        delegate: Annotated[
            FlextInfraConstantsCodegenProject.TemplateDelegate,
            m.Field(description="Canonical rendering delegate"),
        ]
        requires_release_protocol: Annotated[
            bool,
            m.Field(
                default=False,
                description=(
                    "Whether this projection requires the repository's explicit "
                    "release-protocol opt-in"
                ),
            ),
        ] = False
        requires_beads: Annotated[
            bool,
            m.Field(description="Whether the projection requires Beads participation"),
        ] = False

        @m.model_validator(mode="after")
        def validate_delegate_source(self) -> Self:
            """Require a template only for the delegate that renders one.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If render delegate requires a template source; or if
                    manifest delegate must not declare a template source.

            """
            if (
                self.delegate
                == FlextInfraConstantsCodegenProject.TemplateDelegate.RENDER
            ):
                if self.source is None:
                    msg = "render delegate requires a template source"
                    raise ValueError(msg)
            elif self.source is not None:
                msg = "manifest delegate must not declare a template source"
                raise ValueError(msg)
            return self

    class TemplatesSpec(FlextInfraConfigModelsContract.ConfigContract):
        """New-project scaffold root and ordered artifact declarations."""

        root: Annotated[Path, m.Field(description="Package-relative template root")]
        entries: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsTemplates.TemplateEntrySpec],
            m.Field(description="Complete ordered template manifest"),
        ]

    class ManagedFileSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One versioned file governed by codegen lifecycle policy."""

        path: Annotated[Path, m.Field(description="Repository-relative file path")]
        owner: Annotated[t.NonEmptyStr, m.Field(description="Canonical owner")]
        policy: Annotated[
            Literal["full", "merge"],
            m.Field(
                description=(
                    "Conform mutation policy: full renders the whole file; merge "
                    "dispatches to the owner merge that keeps CUSTOM content"
                ),
            ),
        ]
        mode: Annotated[
            int,
            m.Field(
                ge=0,
                le=0o7777,
                strict=True,
                description="Exact permission bits owned by generated publication",
            ),
        ] = 0o644
        conflict_sections: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Dotted sections the owner renders, so a merge conflict in "
                    "them is resolvable by re-rendering rather than by hand. A "
                    "section the owner produces but does not declare here "
                    "dead-ends the merge: absorbing an integration base that "
                    "still carries the previous projection leaves a conflict "
                    "the canonical surface cannot resolve."
                ),
            ),
        ] = ()
        preserve_project_keys: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "CUSTOM PEP 621 [project] keys kept from the live file when "
                    "policy is merge."
                ),
            ),
        ] = ()
        overwrite_project_keys: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "MANAGED PEP 621 [project] keys the template overwrites. "
                    "Must be disjoint from preserve_project_keys."
                ),
            ),
        ] = ()

        @m.computed_field
        @property
        def managed_tool_tables(self) -> t.VariadicTuple[str]:
            """First ``tool.*`` segment of each declared conflict section."""
            return tuple(
                dict.fromkeys(
                    section.split(".", 1)[1].split(".", 1)[0]
                    for section in self.conflict_sections
                    if section.startswith("tool.") and "." in section
                ),
            )

    class GitignoreRenderContext(FlextInfraConfigModelsContract.ConfigContract):
        """Profile-filtered input consumed by the Git ignore template."""

        gitignore_sections: Annotated[
            t.VariadicTuple[
                FlextInfraConfigModelsScaffold.ScaffoldGitignoreSectionSpec
            ],
            m.Field(min_length=1, description="Applicable Git ignore sections"),
        ]

    class GitignoreRenderSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Typed, profile-filtered input for the generated Git ignore file."""

        gitignore_sections: Annotated[
            t.VariadicTuple[
                FlextInfraConfigModelsScaffold.ScaffoldGitignoreSectionSpec
            ],
            m.Field(
                min_length=1,
                description="Canonical ignore sections applicable to one profile",
            ),
        ]

    class StaticTextRenderSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Empty typed context for a variable-free governed text template."""
