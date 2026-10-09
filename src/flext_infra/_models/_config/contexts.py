"""Render context and repository reference models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal

from flext_cli import m

from flext_infra import t
from flext_infra._constants import (
    FlextInfraConstantsCodegenProject,
    FlextInfraConstantsPromoted,
    FlextInfraConstantsWorkspace,
)
from flext_infra._models._config.beads import FlextInfraConfigModelsBeads
from flext_infra._models._config.contract import FlextInfraConfigModelsContract
from flext_infra._models._config.make import FlextInfraConfigModelsMake
from flext_infra._models._config.repository import FlextInfraConfigModelsRepository
from flext_infra._models._config.scaffold import FlextInfraConfigModelsScaffold
from flext_infra._models.deps_tool_config import FlextInfraModelsDepsToolConfig


class FlextInfraConfigModelsContexts(FlextInfraConfigModelsRepository):
    """Render context models composed over the repository reference models."""

    class MakeCommandContext(FlextInfraConfigModelsContract.ConfigContract):
        """Shared command identity required by every generated Make surface."""

        infra_cli: Annotated[
            t.NonEmptyStr,
            m.Field(description="Installed infrastructure CLI command"),
        ]
        pytest: Annotated[
            FlextInfraModelsDepsToolConfig.PytestConfig,
            m.Field(description="Typed pytest execution policy"),
        ]
        environment_directory: Annotated[
            t.NonEmptyStr,
            m.Field(description="Runtime-root-local development environment"),
        ] = FlextInfraConstantsWorkspace.ENVIRONMENT_DIRECTORY
        contract_env_values: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="OPTIONS or HELP values that display a verb contract"),
        ] = tuple(sorted(FlextInfraConstantsPromoted.PROMOTED_ENV_ENABLED_VALUES))

    class MakefileRenderSpec(MakeCommandContext):
        """Field-only render input for an existing repository Makefile."""

        dist: Annotated[t.NonEmptyStr, m.Field(description="PEP 621 project name")]
        make_profile: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(description="Selected repository Make profile"),
        ]
        package: Annotated[
            bool,
            m.Field(description="Repository publishes a Python package"),
        ]
        repository_root_rel: Annotated[
            t.NonEmptyStr,
            m.Field(description="Relative workspace root path"),
        ]
        workspace_subprojects: Annotated[
            t.VariadicTuple[str],
            m.Field(description="Declared workspace subproject paths"),
        ] = ()
        workspace_gitlinks: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsContexts.ManagedGitlinkSpec],
            m.Field(description="Provider-resolved governed Git submodules"),
        ] = ()
        uv_link_mode: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured uv installation link mode"),
        ]
        mise_selector: Annotated[
            t.NonEmptyStr,
            m.Field(description="Mise backend selector the mise.lock pin is read from"),
        ]
        mise_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                description="Declared mise release the running binary must match",
            ),
        ]
        mise_install_tools: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "Explicit [tools] keys `mise install` provisions in setup "
                    "and upg, so the operator's global Mise registry is never "
                    "installed by a project verb"
                ),
            ),
        ]
        python_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Python minor line the environment syncs against"),
        ]
        make: Annotated[
            FlextInfraConfigModelsMake.MakeSpec,
            m.Field(description="Generated Make command contract"),
        ]
        extra_verbs: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsMake.MakeVerbSpec],
            m.Field(description="Repository-specific public Make verbs"),
        ] = ()
        script_dispatch: Annotated[
            FlextInfraConfigModelsContexts.ScriptDispatchSpec | None,
            m.Field(description="Optional script command dispatch contract"),
        ] = None

        makefile_custom_include: Annotated[
            t.NonEmptyStr,
            m.Field(description="Generated custom Make policy include directive"),
        ]
        workspace_cli_group: Annotated[
            t.NonEmptyStr,
            m.Field(description="CLI group that owns the workspace propagate route"),
        ]
        mypy_timeout_exit_code: Annotated[
            int,
            m.Field(gt=0, description="Wall-time limiter timeout exit code"),
        ]
        timeout_command: Annotated[
            t.NonEmptyStr,
            m.Field(description="Wall-time limiter executable"),
        ]
        timeout_kill_after_seconds: Annotated[
            int,
            m.Field(gt=0, description="Forced-termination grace period"),
        ]
        pytest_process_timeout_seconds: Annotated[
            int,
            m.Field(gt=0, description="Pytest process wall-time boundary"),
        ]

    class MakeRenderContext(MakeCommandContext):
        """Typed input consumed by the generated Make surface."""

        make: Annotated[
            FlextInfraConfigModelsMake.MakeSpec,
            m.Field(description="Generated Make command contract"),
        ]
        mypy_timeout_exit_code: Annotated[
            int,
            m.Field(gt=0, description="Wall-time limiter timeout exit code"),
        ]
        timeout_command: Annotated[
            t.NonEmptyStr,
            m.Field(description="Wall-time limiter executable"),
        ]
        timeout_kill_after_seconds: Annotated[
            int,
            m.Field(gt=0, description="Forced-termination grace period"),
        ]
        tooling_runtime: Annotated[
            FlextInfraModelsDepsToolConfig.ToolingRuntimeContext,
            m.Field(description="Resolved project/workspace tooling values"),
        ]

        dist: Annotated[t.NonEmptyStr, m.Field(description="Distribution name")]

        python_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Python major.minor tool value"),
        ]
        uv_link_mode: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured uv installation link mode"),
        ]
        ruff_per_file_ignores: Annotated[
            t.MappingKV[str, t.StrSequence],
            m.Field(
                description=(
                    "Effective Ruff exemptions: fleet policy composed with this "
                    "repository's own ManagedArtifacts overlay"
                ),
            ),
        ]
        ruff_extend_exclude: Annotated[
            t.StrSequence,
            m.Field(
                description=(
                    "Workspace exclusions added to Ruff's defaults: the "
                    "provider-owned tool-home projections stay outside the "
                    "member lint scope"
                ),
            ),
        ]
        make_profile: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(description="Generated Make execution profile"),
        ]
        repository_root_rel: Annotated[
            t.NonEmptyStr,
            m.Field(description="Relative path to the declared workspace root"),
        ]
        makefile_custom_include: Annotated[
            str,
            m.Field(
                min_length=1,
                description=("Make directive that includes the custom Make surface"),
            ),
        ]
        workspace_subprojects: Annotated[
            t.VariadicTuple[str],
            m.Field(description="Ordered workspace subproject paths"),
        ] = ()
        workspace_repositories: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsContexts.RepositoryRef],
            m.Field(description="Ordered workspace subproject records"),
        ] = ()
        workspace_gitlinks: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsContexts.ManagedGitlinkSpec],
            m.Field(description="Provider-resolved governed Git submodules"),
        ] = ()
        extra_verbs: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsMake.MakeVerbSpec],
            m.Field(description="Repository-specific additional public Make verbs"),
        ] = ()
        script_dispatch: Annotated[
            FlextInfraConfigModelsContexts.ScriptDispatchSpec | None,
            m.Field(description="Opt-in script command-framework routing contract"),
        ] = None
        workspace_cli_group: Annotated[
            str,
            m.Field(
                description=(
                    "CLI group name for the flext-infra workspace propagate route"
                ),
            ),
        ] = ""

    class ProjectRenderContext(MakeRenderContext):
        """Complete typed input consumed by project scaffold templates."""

        # This render field is the exact
        # projection of ProjectSpec; templates must not infer or default a hook.
        hatch_build_hook_path: Annotated[
            Path | None,
            m.Field(description="Project-relative Hatch custom build hook module"),
        ] = None
        docs_audit: Annotated[
            FlextInfraConfigModelsContract.DocsAuditOverridesSpec,
            m.Field(
                description="Repository-owned documentation audit declarations",
            ),
        ] = m.Field(
            default_factory=FlextInfraConfigModelsContract.DocsAuditOverridesSpec
        )
        namespace_scan_dirs: Annotated[
            t.StrSequence,
            m.Field(
                description=(
                    "Production source roots rendered as the namespace "
                    "validator's declared scan scope; empty keeps every root "
                    "in scope"
                ),
            ),
        ] = ()
        workspace_integration: Annotated[
            FlextInfraConfigModelsContexts.WorkspaceIntegrationSpec | None,
            m.Field(
                description=(
                    "Declared integration provider and branch written into the "
                    "workspace manifest so later renders derive from the "
                    "declaration, never from the checkout"
                ),
            ),
        ] = None

        @m.computed_field
        @property
        def repository_env_prefix(self) -> str:
            """Settings environment prefix derived from the distribution name.

            Returns:
                The resulting ``str``.
            """
            return f"{self.dist.upper().replace('-', '_')}_"

        @property
        def _config_base(self) -> FlextInfraConfigModelsScaffold.ScaffoldConfigBaseSpec:
            """ENFORCE-042 config base selected from the declared profile.

            The fleet-converged ``_config.py`` composes ``FlextSettings`` FIRST
            with the project's capability base. The base is a property of the
            declared dependency profile, never a per-project hand choice: the
            first entry of ``scaffold.project.config_bases`` whose distribution
            the profile depends on (its runtime requirements or its upstream).

            Raises:
                ValueError: If scaffold.project.config_bases declares no base for the
                    dependency profile of.

            """
            profile = self.dependency_profile
            depended = {
                requirement.split(">")[0].split("=")[0].split("[")[0].strip()
                for requirement in profile.runtime
            } | {profile.upstream.replace("_", "-")}
            for base in self.scaffold.project.config_bases:
                if base.distribution in depended:
                    return base
            msg = (
                "scaffold.project.config_bases declares no base for the "
                f"dependency profile of {self.dist}: {sorted(depended)}"
            )
            raise ValueError(msg)

        @m.computed_field
        @property
        def config_base_class(self) -> str:
            """Config base class composed by the generated ``_config.py``.

            Returns:
                The resulting ``str``.
            """
            return self._config_base.class_name

        @m.computed_field
        @property
        def config_base_module(self) -> str:
            """Import module exposing ``config_base_class``.

            Returns:
                The resulting ``str``.
            """
            return self._config_base.module

        scaffold: Annotated[
            FlextInfraConfigModelsScaffold.ScaffoldSpec,
            m.Field(description="New-project scaffold policy"),
        ]
        gitignore_sections: Annotated[
            t.VariadicTuple[
                FlextInfraConfigModelsScaffold.ScaffoldGitignoreSectionSpec
            ],
            m.Field(
                min_length=1,
                description=(
                    "Canonical .gitignore sections derived from the artifact SSOT"
                ),
            ),
        ]
        dependency_profile: Annotated[
            FlextInfraConfigModelsScaffold.ScaffoldDependencyProfileSpec,
            m.Field(description="Resolved upstream dependency profile"),
        ]
        tooling: Annotated[
            FlextInfraModelsDepsToolConfig.ToolConfigDocument,
            m.Field(description="Canonical validated tooling policy"),
        ]
        environment_path_prepends: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Configured read-only PATH additions for direnv"),
        ] = ()
        beads: Annotated[
            FlextInfraConfigModelsBeads.BeadsProjectSpec | None,
            m.Field(description="Repository-local Beads identity when enabled"),
        ] = None
        canonical_project_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical PEP 621 project name"),
        ]
        const_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured constant project name"),
        ]
        package_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Python import package name"),
        ]
        packaged_data_paths: Annotated[
            t.StrSequence,
            m.Field(
                description="Validated relative data paths shipped in distributions",
            ),
        ]
        packaged_data_files: Annotated[
            t.StrSequence,
            m.Field(description="Validated individually declared data files"),
        ]
        packaged_data_excludes: Annotated[
            t.StrSequence,
            m.Field(description="Validated files excluded from packaged data roots"),
        ] = ()
        class_stem: Annotated[
            t.NonEmptyStr,
            m.Field(description="Public facade class stem"),
        ]
        ns: Annotated[t.NonEmptyStr, m.Field(description="Public model namespace")]
        ns_attr: Annotated[
            t.NonEmptyStr,
            m.Field(description="Private namespace module token"),
        ]
        alias: Annotated[t.NonEmptyStr, m.Field(description="Public instance alias")]
        env_prefix: Annotated[
            t.NonEmptyStr,
            m.Field(description="Settings environment prefix"),
        ]
        upstream: Annotated[
            t.NonEmptyStr,
            m.Field(description="Upstream FLEXT facade module"),
        ]
        upstream_facades: Annotated[
            Mapping[t.NonEmptyStr, t.NonEmptyStr],
            m.Field(
                description=(
                    "Facade class the upstream declares for each letter in the "
                    "__all__ that binds it; scaffolded facades extend that class"
                ),
            ),
        ]
        inherited_facets: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Upstream facets re-exported by the project root; see the "
                    "RepositoryRef namesake for the lazy-init contract."
                ),
            ),
        ] = ()
        root_packages: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Additional shipped top-level packages; see the ProjectSpec "
                    "namesake for the declaration contract."
                ),
            ),
        ] = ()
        repository_namespace_packages: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Implicit namespace directories shipped from the repository root"
                ),
            ),
        ] = ()
        root_modules: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Additional shipped top-level modules; see the ProjectSpec "
                    "namesake for the declaration contract."
                ),
            ),
        ] = ()
        cli_module: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether the package ships its cli entry module; see the "
                    "ProjectSpec namesake."
                ),
            ),
        ]
        runtime_dependency_overlay: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Repository-declared runtime requirements rendered ahead of "
                    "the dependency profile's runtime set; see the ProjectSpec "
                    "namesake."
                ),
            ),
        ] = ()
        description: Annotated[
            t.NonEmptyStr,
            m.Field(description="Project description"),
        ]
        version: Annotated[t.NonEmptyStr, m.Field(description="Project version")]
        license: Annotated[t.NonEmptyStr, m.Field(description="SPDX license id")]
        python_required_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="PEP 440 project Python requirement"),
        ]
        dependency_cooldown_days: Annotated[
            int,
            m.Field(
                ge=1,
                description="Supply-chain cooldown rendered as mise release age",
            ),
        ]
        author_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Author display name"),
        ]
        author_email: Annotated[t.NonEmptyStr, m.Field(description="Author email")]
        repository: Annotated[
            t.NonEmptyStr,
            m.Field(description="Project repository page URL"),
        ]
        homepage: Annotated[t.NonEmptyStr, m.Field(description="Project homepage")]
        documentation: Annotated[
            t.NonEmptyStr,
            m.Field(description="Project documentation URL"),
        ]
        flext_git_base_url: Annotated[
            t.NonEmptyStr,
            m.Field(description="FLEXT Git provider base URL"),
        ]
        flext_git_branch: Annotated[
            t.NonEmptyStr,
            m.Field(description="FLEXT Git provider branch"),
        ]
        repository_provider: Annotated[
            t.NonEmptyStr,
            m.Field(description="Provider key the repository declares for itself"),
        ]
        repository_git_url: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical repository Git clone URL"),
        ]
        repository_branch: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical repository Git branch"),
        ]
        year: Annotated[int, m.Field(description="Copyright year")]

        @m.field_validator("hatch_build_hook_path")
        @classmethod
        def _validate_hatch_build_hook_path(cls, value: Path | None) -> Path | None:
            return FlextInfraConfigModelsContexts.validated_hatch_build_hook_path(
                value,
            )

    class SgconfigRenderSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Typed input for the generated ast-grep project config.

        Why: a provider manifest can declare ``sgconfig.yml`` as a
        required surface, but no generator owned it, so the file was authored by
        hand in one repository and simply absent in another -- provider discovery
        then failed closed with ``missing declared file: sgconfig.yml``. The rule
        and fixture directories are declared here so every repository renders the
        same contract from the SSOT instead of a hand-written copy.
        """

        rule_dirs: Annotated[
            t.VariadicTuple[str],
            m.Field(
                min_length=1,
                description="Directories holding this project's ast-grep rules",
            ),
        ]
        test_dirs: Annotated[
            t.VariadicTuple[str],
            m.Field(
                description="Directories holding rule fixtures and snapshots",
            ),
        ] = ()

    class ProfileSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Execution semantics for one generated Make profile."""

        name: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(description="Closed Make profile name"),
        ]
        environment_scope: Annotated[
            t.NonEmptyStr,
            m.Field(description="uv environment ownership"),
        ]
        setup_scope: Annotated[
            t.NonEmptyStr,
            m.Field(description="setup orchestration scope"),
        ]
        execution_scope: Annotated[
            t.NonEmptyStr,
            m.Field(description="check/test runtime scope"),
        ]
        discovery_scope: Annotated[
            Literal["gitmodules", "none"],
            m.Field(description="repository-local discovery authority"),
        ]
