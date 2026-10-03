"""Codegen artifact, conform, and plan result models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PureWindowsPath
from types import MappingProxyType
from typing import Annotated, Literal, Self

from flext_cli import m, u

from flext_infra import t
from flext_infra._constants import (
    FlextInfraConstantsCodegenProject,
    FlextInfraConstantsSharedInfra,
)
from flext_infra._models import FlextInfraModelsLayout
from flext_infra._models._config.contexts import FlextInfraConfigModelsContexts
from flext_infra._models._config.contract import FlextInfraConfigModelsContract
from flext_infra._models._config.make import FlextInfraConfigModelsMake
from flext_infra._models._config.provider import FlextInfraConfigModelsProvider
from flext_infra._models._config.release import FlextInfraConfigModelsRelease
from flext_infra._models._config.render import FlextInfraConfigModelsRender
from flext_infra._models._config.scaffold import FlextInfraConfigModelsScaffold
from flext_infra._models._config.templates import FlextInfraConfigModelsTemplates
from flext_infra._models._config.workspace import FlextInfraConfigModelsWorkspace
from flext_infra._models.deps_tool_config import FlextInfraModelsDepsToolConfig
from flext_infra._models.deps_tool_config_project_artifacts import (
    FlextInfraModelsDepsToolConfigProjectArtifacts,
)


class FlextInfraConfigModelsArtifact:
    """Codegen artifact, conform, and plan result models."""

    class CodegenArtifactSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One ephemeral/generated resource every ignore/exclude derives from."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Basename of the resource")]
        is_dir: Annotated[bool, m.Field(description="Directory (vs file) resource")] = (
            True
        )
        vscode_exclude: Annotated[
            bool,
            m.Field(description="Feed VS Code files.exclude + search.exclude"),
        ] = True
        watch_exclude: Annotated[
            bool,
            m.Field(description="Feed VS Code files.watcherExclude"),
        ] = True
        gitignore: Annotated[
            bool,
            m.Field(description="Feed the Python/tool section of .gitignore"),
        ] = True
        source_scan_ignore: Annotated[
            bool,
            m.Field(description="Feed source_scan.ignored_resources"),
        ] = False

    class CodegenVscodeSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Fully modeled content of the ``vscode`` section
        of ``config/codegen.yaml``.
        """

        scalar_settings: Annotated[
            Mapping[str, str | bool | int],
            m.Field(description="VS Code scalar keys enforced on every project"),
        ]
        list_settings: Annotated[
            Mapping[str, t.VariadicTuple[str]],
            m.Field(description="VS Code list keys enforced on every project"),
        ]
        map_union_settings: Annotated[
            Mapping[str, Mapping[str, str | bool | int]],
            m.Field(description="VS Code map keys union-merged over project settings"),
        ]
        stripped_keys: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "VS Code keys actively stripped from the settings projection "
                    "because they conflict with a pyrightconfig.json/pyproject.toml "
                    "owner (Pylance settingsNotOverridable)."
                ),
            ),
        ]

    class CodegenLocCapSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Per-module logical-LOC ceiling policy (scc code lines)."""

        max_lines: Annotated[
            int,
            m.Field(ge=1, description="Per-module code-LOC ceiling"),
        ]

    class CodegenConfigSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Fully modeled content of ``config/codegen.yaml``."""

        version: Annotated[int, m.Field(ge=1, description="Config schema version")]
        retired_projections: Annotated[
            t.VariadicTuple[str],
            m.Field(
                description=(
                    "Repository-relative generated projections that no template "
                    "renders any more; generation removes them from consumers"
                ),
            ),
        ]
        fresh_import_workers: Annotated[
            int,
            m.Field(ge=1, le=16, description="Concurrent fresh-import subprocesses"),
        ]
        loc_cap: Annotated[
            FlextInfraConfigModelsArtifact.CodegenLocCapSpec,
            m.Field(description="Per-module code-LOC ceiling policy"),
        ]
        toolchain: Annotated[
            FlextInfraConfigModelsContract.ToolchainSpec,
            m.Field(description="Exact generated toolchain"),
        ]
        github_actions: Annotated[
            Mapping[str, FlextInfraConfigModelsProvider.GithubActionPinSpec],
            m.Field(description="Immutable GitHub Action catalog"),
        ]
        checkout_submodules: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^(true|false|recursive)$",
                description=(
                    "Default actions/checkout submodules mode for every "
                    "generated workflow. 'false' keeps CI green on projects "
                    "whose submodules are private: the default GITHUB_TOKEN "
                    "cannot clone sibling private repositories and "
                    "'recursive' aborts the job at checkout"
                ),
            ),
        ]
        checkout_submodules_overrides: Annotated[
            Mapping[str, str],
            m.Field(
                description=(
                    "Per-distribution override of checkout_submodules, for "
                    "projects that really do exercise their subprojects in CI"
                ),
            ),
        ]
        ci_private_submodules: Annotated[
            Mapping[str, FlextInfraConfigModelsProvider.CiPrivateSubmodulesSpec],
            m.Field(
                description=(
                    "Per-distribution private submodule deploy-key contracts "
                    "rendered into generated CI before make setup"
                ),
            ),
        ]
        ci_private_dependency_auth: Annotated[
            Mapping[str, FlextInfraConfigModelsProvider.CiPrivateDependencyAuthSpec],
            m.Field(
                description=(
                    "Per-distribution GitHub App identity minting installation "
                    "tokens for private git dependencies in generated CI"
                ),
            ),
        ]
        ci_system_packages: Annotated[
            Mapping[str, t.VariadicTuple[t.NonEmptyStr]],
            m.Field(
                description=(
                    "Per-distribution runner packages (Ubuntu apt names) the "
                    "generated CI installs before the gates run"
                ),
            ),
        ]
        ci_package_registry_read: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Distributions whose generated CI gates resolve GitHub "
                    "Packages (for example private GHCR OCI dependencies); only "
                    "these grant the ci job packages: read, every other job "
                    "and distribution stays contents-only"
                ),
            ),
        ]
        uv_exclude_dependencies: Annotated[
            t.VariadicTuple[
                FlextInfraConfigModelsRender.UvScopedDependencyExclusionSpec
            ],
            m.Field(description="Project-scoped official uv dependency exclusions"),
        ] = ()
        sonarcloud: Annotated[
            FlextInfraConfigModelsRender.SonarcloudSpec,
            m.Field(description="Fleet SonarCloud automatic-analysis scope policy"),
        ]
        infra_repository: Annotated[
            FlextInfraConfigModelsProvider.RepositorySourceSpec,
            m.Field(description="Canonical infrastructure repository identity"),
        ]
        branch_policy: Annotated[
            FlextInfraConfigModelsProvider.BranchPolicySpec,
            m.Field(description="Global branch policy (CI triggers, integration line)"),
        ]
        profiles: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsContexts.ProfileSpec],
            m.Field(description="Ordered Make profiles"),
        ]
        make: Annotated[
            FlextInfraConfigModelsMake.MakeSpec,
            m.Field(description="Canonical Make contract"),
        ]
        vscode: Annotated[
            FlextInfraConfigModelsArtifact.CodegenVscodeSpec,
            m.Field(description="Canonical VS Code settings merge contract"),
        ]
        artifacts: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsArtifact.CodegenArtifactSpec],
            m.Field(
                min_length=1,
                description=(
                    "Ephemeral/generated artifact SSOT; every ignore/exclude "
                    "projection derives from this list"
                ),
            ),
        ]
        layout: Annotated[
            FlextInfraModelsLayout.LayoutSpec,
            m.Field(
                description=(
                    "Declarative project-layout conformance contract consumed "
                    "by the layout engine and the layout quality gate"
                ),
            ),
        ]

        @m.computed_field
        @property
        def vscode_files_exclude_map(self) -> Mapping[str, bool]:
            """Derived VS Code ``files.exclude`` entries from the artifact SSOT."""
            return {
                f"**/{artifact.name}": True
                for artifact in self.artifacts
                if artifact.vscode_exclude
            }

        @m.computed_field
        @property
        def vscode_watcher_exclude_map(self) -> Mapping[str, bool]:
            """Derived VS Code ``files.watcherExclude`` entries from the SSOT."""
            return {
                f"**/{artifact.name}/**": True
                for artifact in self.artifacts
                if artifact.watch_exclude
            }

        @m.computed_field
        @property
        def vscode_search_exclude_map(self) -> Mapping[str, bool]:
            """Derived VS Code ``search.exclude`` entries from the artifact SSOT."""
            return dict(self.vscode_files_exclude_map)

        @m.computed_field
        @property
        def source_scan_ignored(self) -> t.VariadicTuple[str]:
            """Derived ``source_scan.ignored_resources`` names from the SSOT."""
            return tuple(
                artifact.name
                for artifact in self.artifacts
                if artifact.source_scan_ignore
            )

        # The canonical .gitignore body is ONE computed
        # projection — the artifact SSOT feeds the Python/build section and the
        # static scaffold sections carry only what the SSOT cannot express
        # (file globs, secrets, editor/OS noise). Per-project exception fields
        # (extra_ignored / allowed dirs) land in their typed owner;
        # this projection is the seam they will extend.
        @m.computed_field
        @property
        def gitignore_sections(
            self,
        ) -> t.VariadicTuple[
            FlextInfraConfigModelsScaffold.ScaffoldGitignoreSectionSpec
        ]:
            """Derived canonical ``.gitignore`` sections (SSOT order, deduplicated).

            Ignore files are order-sensitive: a pattern placed before a
            catch-all such as ``/*`` is dead, and a directory ignored before
            its own ``!`` negation is never re-allowed. The declared sections
            are therefore emitted in their declared order, and derived artifact
            patterns are appended -- never prepended -- so a whitelist policy
            expressed in the SSOT survives the projection intact.
            """
            scaffold_sections = self.scaffold.gitignore_sections
            # A declared section may already govern a derived artifact, in
            # either direction: a whitelist re-allows `.agents/` with `!`, so
            # appending a bare `.agents/` ignore would contradict the declared
            # policy. Only artifacts the SSOT never mentions are appended.
            governed = {
                pattern.lstrip("!")
                for section in scaffold_sections
                for pattern in section.patterns
            }
            managed_allowed: t.MutableSequenceOf[str] = []
            declared_patterns = {
                pattern for section in scaffold_sections for pattern in section.patterns
            }
            for managed in self.managed_files:
                parts = managed.path.parts
                candidates = [
                    *(f"!{'/'.join(parts[:depth])}/" for depth in range(1, len(parts))),
                    f"!{managed.path.as_posix()}",
                ]
                managed_allowed.extend(
                    candidate
                    for candidate in candidates
                    if candidate not in declared_patterns
                    and candidate not in managed_allowed
                )
            derived: t.MutableSequenceOf[str] = []
            for pattern in self.gitignore_artifact_patterns:
                if pattern not in governed and pattern not in derived:
                    derived.append(pattern)
            sections: t.MutableSequenceOf[
                FlextInfraConfigModelsScaffold.ScaffoldGitignoreSectionSpec
            ] = []
            # Declared sections are emitted verbatim. Cross-section dedup is
            # unsound for ignore files: repeating `.beads/*` after an
            # intervening `!.beads/` is what keeps the directory scanned, so
            # dropping the repeat silently un-ignores its contents.
            sections.extend(scaffold_sections)
            # Derived artifacts are appended as their own trailing section: an
            # ignore file is evaluated in order, so injecting them into the
            # first section would place them before any `!` negation the policy
            # declares later and silently un-ignore governed paths.
            if derived:
                sections.append(
                    FlextInfraConfigModelsScaffold.ScaffoldGitignoreSectionSpec(
                        name=FlextInfraConstantsSharedInfra.GITIGNORE_DERIVED_SECTION_NAME,
                        patterns=tuple(derived),
                    ),
                )
            if managed_allowed:
                sections.append(
                    FlextInfraConfigModelsScaffold.ScaffoldGitignoreSectionSpec(
                        name=FlextInfraConstantsSharedInfra.GITIGNORE_MANAGED_SECTION_NAME,
                        patterns=tuple(managed_allowed),
                    ),
                )
            return tuple(sections)

        @m.computed_field
        @property
        def gitignore_artifact_patterns(self) -> t.VariadicTuple[str]:
            """Derived ``.gitignore`` artifact patterns from the SSOT (stable order)."""
            return tuple(
                f"{artifact.name}/" if artifact.is_dir else artifact.name
                for artifact in self.artifacts
                if artifact.gitignore
            )

        managed_files: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsTemplates.ManagedFileSpec],
            m.Field(description="Files owned by conform"),
        ]
        scaffold: Annotated[
            FlextInfraConfigModelsScaffold.ScaffoldSpec,
            m.Field(description="Typed new-project scaffold policy"),
        ]
        templates: Annotated[
            FlextInfraConfigModelsTemplates.TemplatesSpec,
            m.Field(description="New-project-only scaffold template manifest"),
        ]
        # flext-infra owns generic conform policy only. The set
        # of projects it serves is NOT its knowledge — each repository's own
        # .gitmodules is the read-only topology authority.

        @u.model_validator(mode="after")
        def _validate_github_artifact_ownership(self) -> Self:
            """Require one full-managed conform owner for every GitHub template.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If GitHub artifacts must have exactly one template and
                    managed owner; or if GitHub template/managed ownership mismatch; or
                    if GitHub artifacts must be full-managed.

            """
            github_templates = tuple(
                Path(entry.destination)
                for entry in self.templates.entries
                if Path(entry.destination).parts[:1] == (".github",)
            )
            github_managed = tuple(
                managed
                for managed in self.managed_files
                if managed.path.parts[:1] == (".github",)
            )
            template_paths = set(github_templates)
            managed_paths = {managed.path for managed in github_managed}
            duplicate_templates = len(github_templates) != len(template_paths)
            duplicate_managed = len(github_managed) != len(managed_paths)
            if duplicate_templates or duplicate_managed:
                msg = (
                    "GitHub artifacts must have exactly one template and managed owner"
                )
                raise ValueError(msg)
            if template_paths != managed_paths:
                missing_owners = sorted(
                    path.as_posix() for path in template_paths - managed_paths
                )
                missing_templates = sorted(
                    path.as_posix() for path in managed_paths - template_paths
                )
                msg = (
                    "GitHub template/managed ownership mismatch: "
                    f"missing owners={missing_owners}, "
                    f"missing templates={missing_templates}"
                )
                raise ValueError(msg)
            non_full = sorted(
                managed.path.as_posix()
                for managed in github_managed
                if managed.policy
                != FlextInfraConstantsSharedInfra.MANAGED_FILE_POLICY_FULL
            )
            if non_full:
                msg = f"GitHub artifacts must be full-managed: {non_full}"
                raise ValueError(msg)
            return self

    class CodegenConformSurfaceContract(m.Value):
        """Typed ownership contract for one requested conformance surface."""

        # Why: leaf conform planning contract lives on
        # m.Infra only (not nested in services).
        destinations: Annotated[
            frozenset[str] | None,
            m.Field(description="Output paths selected for conformance planning"),
        ] = None
        complete_governed: Annotated[
            bool,
            m.Field(description="Whether every governed output is represented"),
        ] = False
        dependencies_only: Annotated[
            bool,
            m.Field(description="Whether planning is dependency-only"),
        ] = False
        delegates: Annotated[
            bool,
            m.Field(description="Whether delegated templates are planned"),
        ] = True
        pyproject: Annotated[
            bool,
            m.Field(description="Whether project metadata is planned"),
        ] = True
        templates: Annotated[
            bool,
            m.Field(description="Whether managed templates are planned"),
        ] = True
        custom: Annotated[
            bool,
            m.Field(description="Whether custom Make policy is planned"),
        ] = True

    class CodegenConformRequest(FlextInfraConfigModelsContract.ConfigContract):
        """Validated public request for ``flext-infra codegen conform``."""

        root: Annotated[Path, m.Field(description="Repository or workspace root")]
        what: Annotated[
            FlextInfraConstantsCodegenProject.CodegenConformSurface,
            m.Field(description="Managed file selection"),
        ] = FlextInfraConstantsCodegenProject.CodegenConformSurface.ALL
        scope: Annotated[
            FlextInfraConstantsCodegenProject.CodegenConformScope,
            m.Field(description="Repository selection scope"),
        ] = FlextInfraConstantsCodegenProject.CodegenConformScope.SELF
        mode: Annotated[
            FlextInfraConstantsCodegenProject.CodegenConformMode,
            m.Field(description="Read-only check or atomic apply"),
        ] = FlextInfraConstantsCodegenProject.CodegenConformMode.CHECK

    class CodegenArtifactComposition(FlextInfraConfigModelsContract.ConfigContract):
        """Rendered artifact plus the exact source states used to compose it."""

        rendered: Annotated[
            str,
            m.Field(description="Fully composed managed-file content"),
        ]
        source_states: Annotated[
            t.VariadicTuple[m.Cli.AtomicFileState],
            m.Field(description="Ordered immutable sources consumed by composition"),
        ] = ()

    class CodegenRenderInputs(FlextInfraConfigModelsContract.ConfigContract):
        """Resolved inputs shared by every governed render of one repository.

        A conform planner resolves them once per repository; every template
        render, overlay composition, and pyproject conformance of that
        repository then reads these same values.
        """

        target: Annotated[
            FlextInfraConfigModelsContexts.RepositoryConformTarget,
            m.Field(description="Conformance identity and root being rendered"),
        ]
        workspace: Annotated[
            FlextInfraConfigModelsWorkspace.WorkspaceSpec,
            m.Field(description="Workspace manifest governing the repository"),
        ]
        codegen: Annotated[
            FlextInfraConfigModelsArtifact.CodegenConfigSpec,
            m.Field(description="Codegen contract the repository renders under"),
        ]
        tooling_runtime: Annotated[
            FlextInfraModelsDepsToolConfig.ToolingRuntimeContext,
            m.Field(description="Tooling values resolved for the repository"),
        ]
        managed_artifacts: Annotated[
            FlextInfraModelsDepsToolConfigProjectArtifacts.ProjectManagedArtifactsSnapshot,
            m.Field(description="Project managed-artifact catalog overlaid on renders"),
        ]
        integration_branch: Annotated[
            str | None,
            m.Field(
                description=(
                    "Integration branch the repository integrates on, resolved "
                    "once per plan for the project context and every workflow; "
                    "None when Git publishes none, so a render that needs it "
                    "fails with the resolver's own cause"
                ),
            ),
        ]
        planned_direct_sources: Annotated[
            t.VariadicTuple[str] | None,
            m.Field(
                description=(
                    "Requirement names the pyproject composed in this plan "
                    "takes by direct reference (forks and local projects). "
                    "Planners compose the pyproject first and record them; "
                    "None means this plan composes no pyproject, so the "
                    "committed one is the source"
                ),
            ),
        ] = None

    class CodegenFilePlan(FlextInfraConfigModelsContract.ConfigContract):
        """Exact before state and desired state for one managed file."""

        project: Annotated[Path, m.Field(description="Physical owning project root")]
        path: Annotated[Path, m.Field(description="Absolute managed file path")]
        before: Annotated[
            m.Cli.AtomicFileState | m.Cli.AtomicDirectoryChainPlan,
            m.Field(
                description=(
                    "Descriptor-authenticated file state, or the exact absent "
                    "parent chain captured by read-only planning"
                ),
            ),
        ]
        desired_content: Annotated[
            bytes | None,
            m.Field(
                strict=True,
                description="Exact desired bytes, or None for an absent destination",
            ),
        ]
        desired_mode: Annotated[
            int | None,
            m.Field(
                ge=0,
                le=0o7777,
                strict=True,
                description="Exact desired mode, or None for an absent destination",
            ),
        ]
        source_states: Annotated[
            t.VariadicTuple[m.Cli.AtomicFileState],
            m.Field(
                exclude=True,
                description="Exact source states that produced rendered content",
            ),
        ] = ()
        owner: Annotated[
            str,
            m.Field(description="Canonical artifact owner, empty for scaffold files"),
        ] = ""
        policy: Annotated[
            Literal["full", "merge"] | None,
            m.Field(description="Governed root artifact policy"),
        ] = None

        @u.model_validator(mode="after")
        def _validate_publication_identity(self) -> Self:
            """Bind one complete desired state to its exact project and target.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If codegen project and path must be absolute; or if codegen
                    desired bytes and mode must be present or absent together; or if
                    codegen before state belongs to another path; or if codegen absent
                    parent plan is inconsistent with its destination; or if codegen path
                    escapes owning project.

            """
            if not self.project.is_absolute() or not self.path.is_absolute():
                msg = "codegen project and path must be absolute"
                raise ValueError(msg)
            if isinstance(self.before, m.Cli.AtomicFileState):
                if self.before.path != self.path:
                    msg = "codegen before state belongs to another path"
                    raise ValueError(msg)
            elif (
                self.before.target != self.path.parent
                or not self.before.directories
                or self.desired_content is None
            ):
                msg = "codegen absent parent plan is inconsistent with its destination"
                raise ValueError(msg)
            try:
                self.path.relative_to(self.project)
            except ValueError as exc:
                msg = f"codegen path escapes owning project: {self.path}"
                raise ValueError(msg) from exc
            desired = (self.desired_content, self.desired_mode)
            if any(value is None for value in desired) != all(
                value is None for value in desired
            ):
                msg = (
                    "codegen desired bytes and mode must be present or absent together"
                )
                raise ValueError(msg)
            return self

    class CodegenPlan(FlextInfraConfigModelsContract.ConfigContract):
        """Fully validated plan produced before any managed-file write."""

        request: Annotated[
            FlextInfraConfigModelsArtifact.CodegenConformRequest,
            m.Field(description="Validated public request"),
        ]
        repositories: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsContexts.RepositoryRef],
            m.Field(description="Selected repositories in deterministic order"),
        ]
        workspace: Annotated[
            FlextInfraConfigModelsWorkspace.WorkspaceSpec,
            m.Field(description="Workspace governing the selection"),
        ]
        make_spec: Annotated[
            FlextInfraConfigModelsMake.MakeSpec,
            m.Field(description="Canonical Make contract"),
        ]
        uv_environments: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsRelease.UvEnvironmentPlan],
            m.Field(description="uv plans paired with selected repositories"),
        ]
        files: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsArtifact.CodegenFilePlan],
            m.Field(description="All render results validated before application"),
        ]

    class CodegenResult(FlextInfraConfigModelsContract.ConfigContract):
        """Public conformance outcome for check and apply modes."""

        plan: Annotated[
            FlextInfraConfigModelsArtifact.CodegenPlan,
            m.Field(description="Plan that governed the operation"),
        ]
        written_files: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Files atomically replaced by apply"),
        ] = ()
        errors: Annotated[
            t.VariadicTuple[str],
            m.Field(description="Fail-closed validation or write errors"),
        ] = ()

    class RenameCampaignSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One declared CSV-driven rename campaign applied by the mod verb."""

        csv: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Config-directory-relative path to the old,new rename-list "
                    "CSV; the list ships with the declaring config"
                ),
            ),
        ]
        roots: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Repository-root-relative scan directories; empty selects "
                    "the whole repository root"
                ),
            ),
        ] = ()
        bindings: Annotated[
            t.MappingKV[str, t.StrSequence],
            m.Field(
                default_factory=lambda: MappingProxyType[str, t.StrSequence]({}),
                description=(
                    "CSV expression prefixes mapped "
                    "to current public Rope owner identities"
                ),
            ),
        ]
        text_globs: Annotated[
            t.StrSequence,
            m.Field(
                default=(),
                description=(
                    "Explicit root-relative non-Python "
                    "documentation and configuration text surfaces"
                ),
            ),
        ]
        python_documentation: Annotated[
            bool,
            m.Field(
                default=False,
                description=(
                    "Rename comments and actual Python docstrings "
                    "without changing executable strings"
                ),
            ),
        ]
        exclude_globs: Annotated[
            t.StrSequence,
            m.Field(
                default=(),
                description="Generated projections excluded from campaign targets",
            ),
        ]

        @u.model_validator(mode="after")
        def _validate_source_paths(self) -> Self:
            """Keep campaign drivers and scan roots inside their declared owners.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If CSV campaign path must be relative and non-escaping.

            """
            for value in (self.csv, *self.roots):
                path = Path(value)
                if (
                    path.is_absolute()
                    or PureWindowsPath(value).root
                    or not path.parts
                    or ".." in path.parts
                    or "\\" in value
                    or PureWindowsPath(value).drive
                ):
                    msg = (
                        f"CSV campaign path must be relative and non-escaping: {value}"
                    )
                    raise ValueError(msg)
            return self

    class RefactorCsvCampaignsSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Declared CSV-driven rename campaigns for the mod verb's rename phase."""

        campaigns: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsArtifact.RenameCampaignSpec],
            m.Field(default=(), description="Ordered rename campaigns"),
        ] = ()

    class SedPatternSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One declared literal regex substitution applied across the mod scope."""

        pattern: Annotated[t.NonEmptyStr, m.Field(description="Regex source to match")]
        replacement: Annotated[str, m.Field(description="Literal replacement text")]
        file_glob: Annotated[
            t.NonEmptyStr | None,
            m.Field(default=None, description="Optional file glob filter"),
        ]
        flags: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=("Regex flags by name (IGNORECASE, MULTILINE, DOTALL)"),
            ),
        ] = ()
        description: Annotated[
            t.NonEmptyStr | None,
            m.Field(default=None, description="Why this substitution exists"),
        ] = None

    class SedPatternsSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Declared sed-by-list substitution set with optional per-pattern filters."""

        patterns: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsArtifact.SedPatternSpec],
            m.Field(default=(), description="Ordered substitution patterns"),
        ] = ()
