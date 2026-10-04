"""Render specification models for generated workflow and env surfaces.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from flext_cli import m

from flext_infra import t
from flext_infra._constants import (
    FlextInfraConstantsCodegenProject,
    FlextInfraConstantsDocs,
    FlextInfraConstantsWorkspace,
)
from flext_infra._models._config.contexts import FlextInfraConfigModelsContexts
from flext_infra._models._config.contract import FlextInfraConfigModelsContract
from flext_infra._models._config.make import FlextInfraConfigModelsMake
from flext_infra._models._config.provider import FlextInfraConfigModelsProvider
from flext_infra._models.deps_tool_config import FlextInfraModelsDepsToolConfig


class FlextInfraConfigModelsRender:
    """Render specification models for generated workflow and env surfaces."""

    class GithubWorkflowRenderSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Typed input consumed by generated GitHub workflow templates."""

        dist: Annotated[t.NonEmptyStr, m.Field(description="Distribution name")]
        docs_report_filenames: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Structured docs reports CI dumps and uploads"),
        ] = FlextInfraConstantsDocs.DOCS_STRUCTURED_REPORT_FILENAMES
        make_profile: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(
                description=(
                    "Make/codegen profile; ci-matrix projected only for "
                    "workspace/standalone; standalone excluded "
                    "and orphan copies pruned"
                ),
            ),
        ]
        gascity_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Gas City runtime-contract participation; gates the Dolt "
                    "server mode the generated Beads policy script asserts."
                ),
            ),
        ] = True
        repository_branch: Annotated[
            t.NonEmptyStr,
            m.Field(description="Repository integration branch"),
        ]
        python_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Python major.minor line"),
        ]
        github_actions: Annotated[
            Mapping[str, FlextInfraConfigModelsProvider.GithubActionPinSpec],
            m.Field(description="Immutable GitHub Action catalog"),
        ]
        make: Annotated[
            FlextInfraConfigModelsMake.MakeSpec,
            m.Field(description="Canonical workflow command contract"),
        ]
        workspace_repositories: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsContexts.RepositoryRef],
            m.Field(
                default=(),
                description=(
                    "Governed subproject repositories consumed by workspace-scoped "
                    "workflow templates (docs paths, dependabot directories)"
                ),
            ),
        ]
        ci_trigger_branches: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description="Ordered, deduplicated blocking CI branches",
            ),
        ] = ()
        has_devcontainer: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether the rendered repository ships a .devcontainer "
                    "directory. Dependabot only accepts a devcontainers "
                    "ecosystem entry when one exists; declaring it for a "
                    "repository without that directory makes GitHub reject the "
                    "whole manifest, which silently disables EVERY ecosystem in "
                    "it, security updates included. Derived from the repository "
                    "on disk rather than declared, because the directory is the "
                    "fact and a second declaration could disagree with it"
                ),
            ),
        ] = False
        dependency_cooldown_days: Annotated[
            int,
            m.Field(
                ge=1,
                description=(
                    "Fleet supply-chain cooldown (codegen.toolchain SSOT) "
                    "rendered as default-days into every dependabot ecosystem "
                    "entry."
                ),
            ),
        ]
        cooldown_excluded_dependencies: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Requirement names the project takes by direct git "
                    "reference (forks and local projects): derived from its "
                    "pyproject, they never enter the cooldown."
                ),
            ),
        ] = ()
        checkout_submodules: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^(true|false|recursive)$",
                description="actions/checkout submodules mode resolved from config",
            ),
        ]
        custom_steps: Annotated[
            str,
            m.Field(
                default="",
                description=(
                    "Verbatim project-owned workflow steps injected before the "
                    "toolchain installer, read from the project's own "
                    "custom-steps file; empty when the project declares none"
                ),
            ),
        ] = ""
        private_submodules: Annotated[
            FlextInfraConfigModelsProvider.CiPrivateSubmodulesSpec | None,
            m.Field(
                default=None,
                description=(
                    "Optional private-subproject deploy-key init for this "
                    "distribution; None means the workflow skips the step"
                ),
            ),
        ] = None
        private_dependency_auth: Annotated[
            FlextInfraConfigModelsProvider.CiPrivateDependencyAuthSpec | None,
            m.Field(
                default=None,
                description=(
                    "Optional GitHub App token minting for private git "
                    "dependencies; None means the workflow skips the step"
                ),
            ),
        ] = None
        system_packages: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Runner packages this distribution's tests need; empty "
                    "means the workflow renders no install step"
                ),
            ),
        ] = ()
        packages_read: Annotated[
            bool,
            m.Field(
                default=False,
                description=(
                    "Grant the ci job packages: read because this "
                    "distribution's gates resolve GitHub Packages; False keeps "
                    "the job contents-only"
                ),
            ),
        ] = False

    class MakeWorkflowRenderSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Typed input shared by generated local workflow surfaces."""

        dist: Annotated[t.NonEmptyStr, m.Field(description="Distribution name")]
        make: Annotated[
            FlextInfraConfigModelsMake.MakeSpec,
            m.Field(description="Canonical workflow command contract"),
        ]

    class ToolingRenderSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Typed input for project-independent generated tooling surfaces."""

        tooling: Annotated[
            FlextInfraModelsDepsToolConfig.ToolConfigDocument,
            m.Field(description="Canonical validated tooling policy"),
        ]

    class DistroDockerRenderSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Typed input consumed by generated distro Dockerfiles."""

        package_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Python import package name"),
        ]
        python_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Python major.minor line"),
        ]
        make: Annotated[
            FlextInfraConfigModelsMake.MakeSpec,
            m.Field(description="Canonical Make CI token contract for ENV CI=Y"),
        ]
        mise_bootstrap: Annotated[
            FlextInfraConfigModelsContract.MiseBootstrapEnvironmentSpec,
            m.Field(description="Strict Mise environment projected into containers"),
        ]

    class EnvrcRenderSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Typed input consumed only by the generated project ``.envrc``."""

        repository_root_rel: Annotated[
            t.NonEmptyStr,
            m.Field(description="Project-relative owner of the runtime environment"),
        ] = "."
        environment_path_prepends: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Project-relative executable paths"),
        ]
        mise_bootstrap: Annotated[
            FlextInfraConfigModelsContract.MiseBootstrapEnvironmentSpec,
            m.Field(description="Strict persistent Mise storage contract"),
        ]
        environment_directory: Annotated[
            t.NonEmptyStr,
            m.Field(description="Runtime-root-local development environment"),
        ] = FlextInfraConstantsWorkspace.ENVIRONMENT_DIRECTORY
        worktree_environment_directory: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Declared sibling directory for linked worktree environments"
                ),
            ),
        ]

    class SonarcloudIssueExclusionSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One SonarCloud issue exclusion applied as a server-side project setting.

        SonarCloud automatic analysis ignores ``sonar.issue.ignore.*`` in
        ``.sonarcloud.properties``; the exclusion lives in each project's
        SonarCloud settings. This record is its single fleet owner, rendered
        into the generated file only as documentation.
        """

        rule_key: Annotated[
            t.NonEmptyStr,
            m.Field(description="Sonar rule key, e.g. 'text:S8565'"),
        ]
        resource_key: Annotated[
            t.NonEmptyStr,
            m.Field(description="Project-relative resource pattern"),
        ]
        reason: Annotated[
            t.NonEmptyStr,
            m.Field(description="Operator justification and bead"),
        ]

    class SonarcloudSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Fleet SonarCloud automatic-analysis scope policy."""

        exclusions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "sonar.exclusions: generated, cache, vendored, and build "
                    "output only; never governed source"
                ),
            ),
        ]
        cpd_exclusions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="sonar.cpd.exclusions duplication-scope patterns"),
        ] = ()
        api_url: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^https://[^/]+$",
                description="SonarCloud web API origin the settings sync writes to",
            ),
        ]
        api_timeout_seconds: Annotated[
            t.PositiveInt,
            m.Field(description="Per-request SonarCloud web API timeout"),
        ]
        issue_exclusions: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsRender.SonarcloudIssueExclusionSpec],
            m.Field(
                description=(
                    "Server-side issue exclusions applied through SonarCloud "
                    "project settings; never written as file properties"
                ),
            ),
        ] = ()

    class SonarcloudRenderSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Typed input consumed only by the generated ``.sonarcloud.properties``."""

        sonarcloud: Annotated[
            FlextInfraConfigModelsRender.SonarcloudSpec,
            m.Field(description="Fleet SonarCloud scope policy"),
        ]
        tests_dir: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Project-relative tests directory; conform always "
                    "materializes it (managed tests/fixtures/ci/docker "
                    "projections), so sonar.tests always names a real directory"
                ),
            ),
        ]
        workspace_subprojects: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Workspace-relative member checkout paths of a workspace "
                    "root; each member is its own repository with its own "
                    "SonarCloud project, so the root scope excludes them. "
                    "Empty for a standalone repository"
                ),
            ),
        ] = ()

    class UvPackageSelectorSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Package selector for one official uv scoped dependency exclusion."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Selected package name")]
        version: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Optional selected package version expression"),
        ] = None

    class UvScopedDependencyExclusionSpec(
        FlextInfraConfigModelsContract.ConfigContract,
    ):
        """Project-routed official uv scoped dependency exclusion."""

        project: Annotated[
            t.NonEmptyStr,
            m.Field(exclude=True, description="Owning project distribution route"),
        ]
        package: Annotated[
            FlextInfraConfigModelsRender.UvPackageSelectorSpec,
            m.Field(description="Package whose transitive edge is scoped"),
        ]
        dependencies: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Excluded transitive dependency names"),
        ]

    class UvResolutionSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Resolver keys conform owns in one project's ``[tool.uv]`` table.

        Every key is declared: an empty sequence removes it from the table.
        """

        link_mode: Annotated[str, m.Field(description="uv installation link mode")]
        constraint_dependencies: Annotated[
            t.VariadicTuple[str],
            m.Field(description="Declared constraints; the uv pin is never kept"),
        ]
        exclude_dependencies: Annotated[
            t.VariadicTuple[
                FlextInfraConfigModelsRender.UvScopedDependencyExclusionSpec
            ],
            m.Field(description="Scoped dependency exclusions routed to the project"),
        ]
        environments: Annotated[
            t.VariadicTuple[str],
            m.Field(description="Resolved environment markers uv resolves for"),
        ]
