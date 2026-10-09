"""Render context and repository reference models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PureWindowsPath
from typing import Annotated, ClassVar, Literal

from flext_cli import m

from flext_infra import t
from flext_infra._constants import (
    FlextInfraConstantsCodegenProject,
    FlextInfraConstantsWorkspace,
)
from flext_infra._models._config.beads import FlextInfraConfigModelsBeads
from flext_infra._models._config.contract import FlextInfraConfigModelsContract
from flext_infra._models._config.make import FlextInfraConfigModelsMake
from flext_infra._models._config.scaffold import FlextInfraConfigModelsScaffold
from flext_infra._models.deps_tool_config import FlextInfraModelsDepsToolConfig


class FlextInfraConfigModelsContexts:
    """Render context and repository reference models."""

    @staticmethod
    def _validated_hatch_build_hook_path(value: Path | None) -> Path | None:
        """Return one normalized project-relative Hatch hook declaration.

        Returns:
            One normalized project-relative Hatch hook declaration.

        Raises:
            ValueError: If hatch_build_hook_path must be a safe project-relative path.

        """
        if value is None:
            return None
        raw = str(value)
        not_project_relative = (
            value.is_absolute() or not value.parts or value.as_posix() in {"", "."}
        )
        unsafe_segments = (
            ".." in value.parts or "\\" in raw or bool(PureWindowsPath(raw).drive)
        )
        if not_project_relative or unsafe_segments:
            msg = f"hatch_build_hook_path must be a safe project-relative path: {raw}"
            raise ValueError(msg)
        return value

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
        worktree_environment_directory: Annotated[
            t.NonEmptyStr,
            m.Field(
                description="Declared sibling directory for linked worktree environments",
            ),
        ]

    class MakefileRenderSpec(MakeCommandContext):
        """Field-only render input for an existing repository Makefile."""

        mise_bootstrap: Annotated[
            FlextInfraConfigModelsContract.MiseBootstrapEnvironmentSpec,
            m.Field(description="Generated strict Mise bootstrap environment"),
        ]

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
        workspace_repositories: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsContexts.RepositoryRef],
            m.Field(description="Repositories editable from the selected workspace"),
        ] = ()
        workspace_gitlinks: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsContexts.ManagedGitlinkSpec],
            m.Field(description="Provider-resolved governed Git submodules"),
        ] = ()
        uv_link_mode: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured uv installation link mode"),
        ]
        uv_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="mise-owned uv version used by bootstrap validation"),
        ]
        mise_lockfile_platforms: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Platforms carried by artifact-tool lock entries"),
        ]
        npm_package_manager: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured Mise installer for npm CLIs"),
        ]
        qlty_selector: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured Mise selector for qlty"),
        ]
        jscpd_selector: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured Mise selector for jscpd"),
        ]
        prettier_selector: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured Mise selector for Prettier"),
        ]
        ast_grep_selector: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured Mise selector for ast-grep"),
        ]
        scc_selector: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured Mise selector for scc"),
        ]
        waza_selector: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured Mise selector for Waza"),
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

        mise_bootstrap: Annotated[
            FlextInfraConfigModelsContract.MiseBootstrapEnvironmentSpec,
            m.Field(description="Generated strict Mise bootstrap environment"),
        ]

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

        docs_audit: Annotated[
            FlextInfraConfigModelsContract.DocsAuditOverridesSpec,
            m.Field(
                default_factory=FlextInfraConfigModelsContract.DocsAuditOverridesSpec,
                description="Repository-owned documentation audit declarations",
            ),
        ]
        packaged_data_excludes: Annotated[
            t.StrSequence,
            m.Field(
                default=(),
                description=(
                    "Repository-relative files omitted from declared data directories"
                ),
            ),
        ]

        # This render field is the exact
        # projection of ProjectSpec; templates must not infer or default a hook.
        hatch_build_hook_path: Annotated[
            Path | None,
            m.Field(description="Project-relative Hatch custom build hook module"),
        ] = None
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
            """Settings environment prefix derived from the distribution name."""
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
            """Config base class composed by the generated ``_config.py``."""
            return self._config_base.class_name

        @m.computed_field
        @property
        def config_base_module(self) -> str:
            """Import module exposing ``config_base_class``."""
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
        kubectl_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact kubectl toolchain version"),
        ]
        helm_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact Helm toolchain version"),
        ]
        kind_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact kind toolchain version"),
        ]
        direnv_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Compatible direnv major.minor line"),
        ]
        uv_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Compatible uv major.minor line"),
        ]
        qlty_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Moving qlty release selector, e.g. 'latest'"),
        ]
        node_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Compatible Node.js major.minor line"),
        ]
        jscpd_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Moving jscpd release selector, e.g. 'latest'"),
        ]
        waza_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Moving Waza release selector, e.g. 'latest'"),
        ]
        taplo_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Taplo release selector; the committed mise.lock pins the "
                    "version generation authenticates"
                ),
            ),
        ]
        ast_grep_selector: Annotated[
            t.NonEmptyStr,
            m.Field(description="Mise selector for the ast-grep CLI"),
        ]
        ast_grep_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact ast-grep analyzer version"),
        ]
        gitleaks_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact Gitleaks scanner version"),
        ]
        scc_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact scc code-counter version"),
        ]
        kubeconform_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Compatible kubeconform minor line"),
        ]
        go_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact Go runtime version"),
        ]
        make_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Moving Make release selector, e.g. 'latest'"),
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
            return FlextInfraConfigModelsContexts._validated_hatch_build_hook_path(
                value,
            )

    class ProjectSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Deterministic project metadata required to materialize a new tree."""

        flext_source: Annotated[
            t.NonEmptyStr | None,
            m.Field(
                description=(
                    "Direct Git infrastructure requirement declared for scaffolding"
                ),
            ),
        ] = None

        # ProjectSpec is the sole declaration
        # owner; absence is meaningful and must never select a conventional hook.
        hatch_build_hook_path: Annotated[
            Path | None,
            m.Field(description="Project-relative Hatch custom build hook module"),
        ] = None
        package_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Import package name"),
        ]
        class_stem: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical public facade class stem"),
        ]
        namespace: Annotated[
            t.NonEmptyStr,
            m.Field(description="Nested c/t/p/m/u namespace"),
        ]
        constant_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured project name exposed through constants"),
        ]
        namespace_attribute: Annotated[
            t.NonEmptyStr,
            m.Field(description="Private module namespace token"),
        ]
        alias: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical public instance alias"),
        ]
        environment_prefix: Annotated[
            t.NonEmptyStr,
            m.Field(description="Project settings environment prefix"),
        ]
        description: Annotated[
            t.NonEmptyStr,
            m.Field(description="Project description"),
        ]
        license: Annotated[t.NonEmptyStr, m.Field(description="SPDX license id")]
        author_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Author display name"),
        ]
        author_email: Annotated[t.NonEmptyStr, m.Field(description="Author email")]
        upstream: Annotated[
            t.NonEmptyStr,
            m.Field(description="Upstream FLEXT facade module"),
        ]
        namespace_scan_dirs: Annotated[
            t.StrSequence,
            m.Field(
                description=(
                    "Production source roots the namespace validator enforces; "
                    "empty keeps every root in scope (previous behavior)"
                ),
            ),
        ] = ()
        inherited_facets: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Upstream facets re-exported by the project root. The lazy-init "
                    "public-root planner reads this to decide which upstream "
                    "namespace names the generated root __init__ may re-export: a "
                    "facet is inherited when declared here or actually imported "
                    "from source. Without the field the planner cannot honour a "
                    "manifest declaration and re-exports only what source imports "
                    "prove -- which silently drops manifest-declared facets."
                ),
            ),
        ] = ()
        root_packages: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Additional top-level packages under the source directory "
                    "that the distribution must ship beyond the primary "
                    "package. Declared per repository because the layout is a "
                    "fact of that repository, not of its upstream profile."
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
                    "Top-level single-file modules under the source directory "
                    "shipped alongside the packages; see the root_packages "
                    "namesake for why the declaration is per repository."
                ),
            ),
        ] = ()
        packaged_data_paths: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Repository-relative data files and directories"
                    " shipped with the package"
                ),
            ),
        ] = ()
        packaged_data_excludes: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Repository-relative files omitted from declared data directories"
                ),
            ),
        ] = ()
        cli_module: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether the package ships its cli entry module. A scaffold "
                    "renders the cli seed in the same plan; an existing checkout "
                    "derives the fact from its source tree. The default console "
                    "script is declared only then, because conform loads every "
                    "declared entry point in its fresh-import stage."
                ),
            ),
        ] = True
        runtime_dependency_overlay: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Runtime requirements this repository adds ahead of its "
                    "dependency profile's runtime set. The profile states what "
                    "every project on that upstream needs; the overlay states "
                    "what this one additionally needs, so neither owner has to "
                    "encode the other's scope."
                ),
            ),
        ] = ()
        homepage: Annotated[t.NonEmptyStr, m.Field(description="Project homepage")]
        documentation: Annotated[
            t.NonEmptyStr,
            m.Field(description="Project documentation URL"),
        ]
        repository_root_rel: Annotated[
            t.NonEmptyStr,
            m.Field(description="Declared relative path to the workspace root"),
        ]
        year: Annotated[int, m.Field(ge=2025, description="Copyright year")]

        @m.field_validator("hatch_build_hook_path")
        @classmethod
        def _validate_hatch_build_hook_path(cls, value: Path | None) -> Path | None:
            return FlextInfraConfigModelsContexts._validated_hatch_build_hook_path(
                value,
            )

    class WorkspaceIntegrationSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Declared integration provider and branch of one repository."""

        provider: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured provider key"),
        ]
        branch: Annotated[
            t.NonEmptyStr,
            m.Field(description="Workspace integration branch"),
        ]
        organization: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Optional provider organization override"),
        ] = None
        base_url: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Optional provider base URL override"),
        ] = None

    class RepositoryRef(FlextInfraConfigModelsContract.ConfigContract):
        """One declared repository and its immutable Git origin contract."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(use_enum_values=False)

        name: Annotated[t.NonEmptyStr, m.Field(description="Catalog key")]
        distribution: Annotated[
            t.NonEmptyStr,
            m.Field(description="Python distribution or repository name"),
        ]
        url: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical GitHub clone URL ending in .git"),
        ]
        path: Annotated[
            Path,
            m.Field(description="POSIX path relative to its workspace root"),
        ]
        role: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(description="Repository role in the declared topology"),
        ]
        state: Annotated[
            FlextInfraConstantsCodegenProject.RepositoryState,
            m.Field(description="Repository lifecycle state"),
        ] = FlextInfraConstantsCodegenProject.RepositoryState.ACTIVE
        checkout: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Physical checkout topology of the declared tree; "
                    "'root' marks the workspace's own primary checkout"
                ),
            ),
        ] = "root"
        provider: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Provider key the declaring repository's own manifest carries"
                ),
            ),
        ]
        kind: Annotated[
            FlextInfraConstantsCodegenProject.ProjectKind,
            m.Field(
                description=(
                    "Governance kind; only internal_flext repositories are "
                    "rewritten by generation. Defaults to internal_flext, which "
                    "is the behaviour every manifest had before this field "
                    "existed: a repository that omits it is one this generator "
                    "already conforms. Requiring it outright made every manifest "
                    "written before the field was added fail validation, so a "
                    "consumer that had not yet updated could not run `make gen` "
                    "at all -- and a consumer is allowed to lag."
                ),
            ),
        ] = FlextInfraConstantsCodegenProject.ProjectKind.INTERNAL_FLEXT
        codegen: Annotated[
            FlextInfraConstantsCodegenProject.CodegenKind,
            m.Field(description="Repository code-generation policy"),
        ]
        package: Annotated[
            bool,
            m.Field(description="Repository publishes a Python package"),
        ]
        publishes_release: Annotated[
            bool,
            m.Field(
                default=False,
                description=(
                    "Whether this distribution explicitly opts into the generated "
                    "release protocol"
                ),
            ),
        ] = False
        editable: Annotated[
            bool,
            m.Field(description="Overlay repository as an editable dependency"),
        ]
        read_only: Annotated[
            bool,
            m.Field(description="Repository rejects generated mutations"),
        ]
        uv_link_mode: Annotated[
            Literal["clone", "copy", "hardlink", "symlink"] | None,
            m.Field(
                description=(
                    "Repository-specific uv installation link mode; absent uses "
                    "the fleet toolchain default"
                ),
            ),
        ] = None
        duplication_trees: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Project-relative directory trees the duplication gate "
                    "must scan besides the canonical src/tests scope (e.g. "
                    "declared Helm charts)"
                ),
            ),
        ] = ()
        extra_verbs: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsMake.MakeVerbSpec],
            m.Field(
                description=(
                    "Additional public Make verbs this repository dispatches "
                    "beyond the canonical set (e.g. a script command framework)"
                ),
            ),
        ] = ()
        script_dispatch: Annotated[
            FlextInfraConfigModelsContexts.ScriptDispatchSpec | None,
            m.Field(
                description=(
                    "Opt-in script command-framework routing for non-builtin "
                    "verbs and WHAT selectors; None keeps builtin-only dispatch"
                ),
            ),
        ] = None

    class RepositoryConformTarget(FlextInfraConfigModelsContract.ConfigContract):
        """Runtime-derived conformance identity for one repository."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(use_enum_values=False)

        repository: Annotated[
            FlextInfraConfigModelsContexts.RepositoryRef,
            m.Field(description="Declared immutable repository identity"),
        ]
        root: Annotated[
            Path,
            m.Field(description="Resolved repository root receiving conformance"),
        ]
        make_profile: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(description="Make profile inferred from live Git topology"),
        ]
        beads: Annotated[
            FlextInfraConfigModelsBeads.BeadsProjectSpec | None,
            m.Field(description="Repository-local Beads identity when enabled"),
        ] = None
        project: Annotated[
            FlextInfraConfigModelsContexts.ProjectSpec | None,
            m.Field(
                description=(
                    "Declared project metadata of the manifest, when the "
                    "repository declares one; carries the distribution roots "
                    "the packaging phase must prove present"
                ),
            ),
        ] = None
        canonical_project_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical PEP 621 project name"),
        ]
        ci_enabled: Annotated[
            bool,
            m.Field(description="Whether conform owns the CI projection"),
        ]
        publishes_release: Annotated[
            bool,
            m.Field(
                default=False,
                description="Whether conform renders release-protocol artifacts",
            ),
        ] = False
        gascity_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether the repository consumes the Gas City runtime "
                    "contract; gates the gc tool projection and the inherited "
                    "Dolt endpoint keys at render time."
                ),
            ),
        ] = True
        external_dependency_paths: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Observed external or fork Git submodule paths"),
        ] = ()

    class ManagedGitlinkSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One governed submodule with its provider-owned baseline branch."""

        repository: Annotated[
            FlextInfraConfigModelsContexts.RepositoryRef,
            m.Field(description="Governed repository identity"),
        ]
        branch: Annotated[
            t.NonEmptyStr,
            m.Field(description="Declared gitlink branch (. follows the superproject)"),
        ]

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
                default=(),
                description="Directories holding rule fixtures and snapshots",
            ),
        ]

    class ScriptDispatchSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Opt-in routing of non-builtin verbs to a script command framework."""

        dispatcher: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Repository-relative dispatcher entrypoint that resolves "
                    "scripts/<verb>/<what>.{py,sh} commands"
                ),
            ),
        ]
        roots: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "Repository-relative script roots scanned for a matching "
                    "<verb>/<what> command before falling back to a builtin"
                ),
            ),
        ]

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
