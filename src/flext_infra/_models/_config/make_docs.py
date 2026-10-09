"""Make docs verb lifecycle, preview-limit, and cross-repo link models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Self

from flext_cli import m

from flext_infra import c, t
from flext_infra._models._config.contract import FlextInfraConfigModelsContract


class FlextInfraConfigModelsMakeDocs:
    """Generated Makefile docs verb lifecycle and documentation link models."""

    class DocsOverviewPreviewLimitsSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Maximum list sizes in the generated public API overview."""

        aliases: Annotated[int, m.Field(gt=0, description="Alias preview limit")]
        public_symbols: Annotated[
            int,
            m.Field(gt=0, description="Public symbol preview limit"),
        ]
        facades: Annotated[int, m.Field(gt=0, description="Facade preview limit")]
        module_exports: Annotated[
            int,
            m.Field(gt=0, description="Module export preview limit"),
        ]
        keywords: Annotated[int, m.Field(gt=0, description="Keyword preview limit")]

    class DocsGithubRepoSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One governed GitHub repository used for cross-repo doc links."""

        organization: Annotated[
            t.NonEmptyStr,
            m.Field(description="GitHub organization"),
        ]
        repository: Annotated[t.NonEmptyStr, m.Field(description="GitHub repository")]
        branch: Annotated[
            t.NonEmptyStr,
            m.Field(description="Working-line branch for doc links"),
        ]
        local_checkout: Annotated[
            str,
            m.Field(
                default="",
                description=(
                    "Optional local checkout path (~ expanded) for existence checks"
                ),
            ),
        ] = ""

    class MakeDocsSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Generated Makefile docs verb lifecycle and audit policy."""

        actions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "Docs verb lifecycle actions in execution order; every "
                    "entry must be a registered docs CLI action"
                ),
            ),
        ]
        mutable_actions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Docs actions that mutate"),
        ]
        reports_dir: Annotated[
            Path,
            m.Field(description="Repository-relative docs reports directory"),
        ]
        overview_preview_limits: Annotated[
            FlextInfraConfigModelsMakeDocs.DocsOverviewPreviewLimitsSpec,
            m.Field(description="Maximum preview sizes for generated API overviews"),
        ]
        cross_project_relative_link_pattern: Annotated[
            t.NonEmptyStr,
            m.Field(
                description="Regex rejecting cross-project relative Markdown links",
            ),
        ]
        stale_github_organizations: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=("organization",),
                description="Placeholder GitHub orgs that must be rewritten",
            ),
        ] = ("organization",)
        github_repos: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsMakeDocs.DocsGithubRepoSpec],
            m.Field(
                default=(),
                description="Governed org/repo/branch map for cross-repo doc URLs",
            ),
        ] = ()

        @m.model_validator(mode="after")
        def _validate_actions(self) -> Self:
            """Reject unknown, duplicated, or out-of-lifecycle docs actions.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If docs actions must be unique; or if docs action is not a
                    registered CLI action; or if mutable_actions entry is not part of
                    the docs lifecycle.

            """
            if len(set(self.actions)) != len(self.actions):
                msg = "docs actions must be unique"
                raise ValueError(msg)
            unknown = next(
                (
                    action
                    for action in self.actions
                    if action not in c.Infra.DOCS_ACTION_IDS
                ),
                None,
            )
            if unknown is not None:
                msg = f"docs action is not a registered CLI action: {unknown}"
                raise ValueError(msg)
            outside = next(
                (
                    action
                    for action in self.mutable_actions
                    if action not in self.actions
                ),
                None,
            )
            if outside is not None:
                msg = (
                    "mutable_actions entry is not part of the docs lifecycle:"
                    f" {outside}"
                )
                raise ValueError(msg)
            return self


__all__: list[str] = ["FlextInfraConfigModelsMakeDocs"]
