"""Workspace manifest, integration, and policy models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Annotated, ClassVar, Literal, Self

from flext_cli import m

from flext_infra import c, t
from flext_infra._models._config.beads import FlextInfraConfigModelsBeads
from flext_infra._models._config.contexts import FlextInfraConfigModelsContexts
from flext_infra._models._config.contract import FlextInfraConfigModelsContract


class FlextInfraConfigModelsWorkspace:
    """Workspace manifest, integration, and policy models."""

    class CandidateBootstrapTargetSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One declared worktree and canonical conform surface."""

        path: Annotated[Path, m.Field(description="Relative candidate worktree path")]
        what: Annotated[
            c.Infra.CodegenConformSurface,
            m.Field(description="Canonical generator surface for this target"),
        ]

        @m.model_validator(mode="after")
        def _validate_path(self) -> Self:
            if self.path.is_absolute() or not self.path.parts:
                msg = "candidate bootstrap path must be relative"
                raise ValueError(msg)
            if self.what not in {
                c.Infra.CodegenConformSurface.MAKEFILE,
                c.Infra.CodegenConformSurface.DOCS_CONFIG,
                c.Infra.CodegenConformSurface.PYPROJECT,
            }:
                msg = "candidate bootstrap owns only declared recovery surfaces"
                raise ValueError(msg)
            return self

    class DependencyCommitSourceSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One dependency distribution resolved to an immutable Git commit.

        A staged candidate and a workspace member's recorded gitlink are the
        same fact: a distribution, its canonical repository and the exact
        commit it resolves to.
        """

        distribution: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact dependency distribution name"),
        ]
        url: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical HTTPS Git repository URL"),
        ]
        commit: Annotated[
            t.NonEmptyStr,
            m.Field(description="Full immutable Git commit OID"),
        ]

        @m.model_validator(mode="after")
        def _validate_source(self) -> Self:
            if not self.url.startswith("https://") or not self.url.endswith(".git"):
                msg = "dependency commit source URL must be canonical HTTPS Git"
                raise ValueError(msg)
            if c.Infra.GIT_COMMIT_OID_RE.fullmatch(self.commit) is None:
                msg = "dependency commit source must pin a full Git OID"
                raise ValueError(msg)
            return self

    class DependencyManifestSpec(m.ContractModel):
        """Dependency facts one member's own ``pyproject.toml`` declares."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="ignore",
            frozen=True,
        )

        name: Annotated[
            t.NonEmptyStr,
            m.Field(
                validation_alias=m.AliasPath("project", "name"),
                description="PEP 621 distribution name",
            ),
        ]
        dependencies: Annotated[
            t.StrSequence,
            m.Field(
                validation_alias=m.AliasPath("project", "dependencies"),
                description="PEP 621 runtime requirements",
            ),
        ] = ()
        dependency_groups: Annotated[
            t.MappingKV[str, t.StrSequence],
            m.Field(
                validation_alias=c.Infra.DEPENDENCY_GROUPS,
                description="PEP 735 dependency groups (dev, codegen, ...)",
            ),
        ] = m.Field(
            default_factory=lambda: MappingProxyType[str, t.StrSequence]({}),
        )

    class DependencyEdgeSpec(m.ContractModel):
        """One directed requirement edge between two workspace members."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid",
            frozen=True,
        )

        dependent: Annotated[
            t.NonEmptyStr,
            m.Field(description="Member distribution declaring the requirement"),
        ]
        dependency: Annotated[
            t.NonEmptyStr,
            m.Field(description="Member distribution it requires"),
        ]

    type CandidateBootstrapTargets = t.VariadicTuple[CandidateBootstrapTargetSpec]
    """Shared declaration type for repeated candidate worktree target fields."""

    class WorkspaceBeadsServerSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Optional Dolt connection declared by a versioned workspace manifest."""

        backend: Annotated[
            Literal["dolt"],
            m.Field(description="Workspace ledger storage engine"),
        ]
        mode: Annotated[
            Literal["server"],
            m.Field(description="Workspace ledger connection mode"),
        ]
        shared_server: Annotated[
            Literal[False],
            m.Field(description="Workspace ledger uses an external Dolt endpoint"),
        ] = False
        host: Annotated[t.NonEmptyStr, m.Field(description="Dolt server host")]
        port: Annotated[
            int,
            m.Field(ge=1, le=65535, description="Dolt server TCP port"),
        ]
        user: Annotated[t.NonEmptyStr, m.Field(description="Dolt server user")]
        auto_commit: Annotated[
            Literal["off", "on", "batch"],
            m.Field(description="Dolt auto-commit policy"),
        ]

    class RepositoryPolicyOverlaySpec(FlextInfraConfigModelsContract.ConfigContract):
        """Bounded per-project policy declared by a workspace manifest."""

        project: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical project distribution"),
        ]
        beads_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether the repository participates in Beads; an overlay "
                    "that omits it means the same as no overlay (enabled)"
                ),
            ),
        ] = True
        ci_enabled: Annotated[
            bool,
            m.Field(description="Whether conform owns the CI surface"),
        ] = True
        ci_matrix_auto_run: Annotated[
            bool,
            m.Field(description="Whether the CI matrix runs automatically"),
        ] = False
        gascity_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether the repository consumes the Gas City runtime "
                    "contract (city-owned Dolt server, gc tool projection, "
                    "inherited endpoint keys). False renders the standalone "
                    "shape: repository-local Dolt server owned by Beads."
                ),
            ),
        ] = True

    class WorkspaceExclusionSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One explicitly excluded workspace-relative path."""

        path: Annotated[Path, m.Field(description="Workspace-relative path")]
        reason: Annotated[t.NonEmptyStr, m.Field(description="Exclusion rationale")]

    class RefactorConfigSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Refactor file-selection configuration."""

        project_scan_dirs: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Relative directories scanned for candidate files"),
        ]
        file_extensions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description="Allowed file extensions (empty = all by pattern)",
            ),
        ] = m.Field(default_factory=tuple)

    class WorkspaceManifestSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Complete versioned input contract for ``config/workspace.yaml``."""

        version: Annotated[
            int,
            m.Field(
                ge=c.Infra.WORKSPACE_MANIFEST_VERSION,
                le=c.Infra.WORKSPACE_MANIFEST_VERSION,
                description="Workspace manifest schema version",
            ),
        ]
        name: Annotated[t.NonEmptyStr, m.Field(description="Workspace name")]
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
                    "Repository-level production roots the namespace validator "
                    "enforces; an empty declaration keeps every root in scope, and "
                    "an explicit project-level declaration wins"
                ),
            ),
        ] = ()
        ledger_id: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Optional workspace ledger database identity"),
        ] = None
        ledger_prefix: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Optional workspace issue-prefix identity"),
        ] = None
        beads_server: Annotated[
            FlextInfraConfigModelsWorkspace.WorkspaceBeadsServerSpec | None,
            m.Field(description="Optional workspace-local Dolt connection"),
        ] = None
        repository: Annotated[
            FlextInfraConfigModelsContexts.RepositoryRef,
            m.Field(description="Root repository declaration"),
        ]
        project: Annotated[
            FlextInfraConfigModelsContexts.ProjectSpec | None,
            m.Field(description="Optional project creation metadata"),
        ] = None
        members: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsContexts.RepositoryRef],
            m.Field(description="Declared member repository contracts"),
        ] = ()
        external_dependency_paths: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Declared external dependency paths"),
        ] = ()
        content_only: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Content-only Gitlink paths"),
        ] = ()
        exclusions: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsWorkspace.WorkspaceExclusionSpec],
            m.Field(description="Explicit workspace exclusions"),
        ] = ()
        integration: Annotated[
            FlextInfraConfigModelsContexts.WorkspaceIntegrationSpec | None,
            m.Field(description="Optional integration provider overlay"),
        ] = None
        candidate_dependencies: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsWorkspace.DependencyCommitSourceSpec],
            m.Field(description="Candidate-only exact dependency Git sources"),
        ] = ()
        candidate_bootstrap_targets: Annotated[
            FlextInfraConfigModelsWorkspace.CandidateBootstrapTargets,
            m.Field(description="Declared candidate worktrees conformed by Infra"),
        ] = ()
        repository_policy_overlays: Annotated[
            t.VariadicTuple[
                FlextInfraConfigModelsWorkspace.RepositoryPolicyOverlaySpec
            ],
            m.Field(description="Repository-local policy overlays"),
        ] = ()
        external_consumers: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsWorkspace.ExternalConsumerSpec],
            m.Field(
                description=(
                    "Out-of-workspace repositories propagation adjusts as"
                    " guests through their own make verbs"
                ),
            ),
        ] = ()
        refactor: Annotated[
            FlextInfraConfigModelsWorkspace.RefactorConfigSpec | None,
            m.Field(description="Refactor file-selection configuration"),
        ] = None

        @m.model_validator(mode="after")
        def _validate_references(self) -> Self:
            """Reject ambiguous paths and policy references in the full document.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If ``invalid_paths``; or if composed project paths must be
                    unique; or if composed projects cannot also be external
                    dependencies; or if repository policy overlays must be unique; or if
                    ``unknown_projects``; or if candidate dependency distributions must
                    be unique; or if candidate bootstrap targets must be unique.

            """
            external_paths = (*self.external_dependency_paths, *self.content_only)
            invalid_paths = tuple(
                path
                for path in external_paths
                if path.is_absolute() or not path.parts or ".." in path.parts
            )
            if invalid_paths:
                msg = "workspace dependency paths must be relative: " + ", ".join(
                    path.as_posix() for path in invalid_paths
                )
                raise ValueError(msg)
            member_paths = tuple(item.path for item in self.members)
            if len(set(member_paths)) != len(member_paths):
                msg = "composed project paths must be unique"
                raise ValueError(msg)
            if set(member_paths).intersection(external_paths):
                msg = "composed projects cannot also be external dependencies"
                raise ValueError(msg)
            projects = tuple(item.project for item in self.repository_policy_overlays)
            if len(set(projects)) != len(projects):
                msg = "repository policy overlays must be unique"
                raise ValueError(msg)
            repository_names = {
                item.distribution for item in (self.repository, *self.members)
            }
            unknown_projects = set(projects).difference(repository_names)
            if unknown_projects:
                msg = (
                    "repository policy overlays reference unknown projects: "
                    + ", ".join(sorted(unknown_projects))
                )
                raise ValueError(msg)
            candidate_names = tuple(
                item.distribution for item in self.candidate_dependencies
            )
            if len(set(candidate_names)) != len(candidate_names):
                msg = "candidate dependency distributions must be unique"
                raise ValueError(msg)
            targets = self.candidate_bootstrap_targets
            if len({target.path for target in targets}) != len(targets):
                msg = "candidate bootstrap targets must be unique"
                raise ValueError(msg)
            return self

    class CodegenBootstrapSource(FlextInfraConfigModelsContract.ConfigContract):
        """Explicit dependency provenance before a scaffold has project metadata."""

        url: Annotated[t.NonEmptyStr, m.Field(description="Infrastructure Git URL")]
        ref: Annotated[t.NonEmptyStr, m.Field(description="Infrastructure Git ref")]

    class ExternalConsumerSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One out-of-workspace repository propagation adjusts as a guest.

        The consumer keeps its own governance: propagation only advances its
        declared lane through the consumer's own canonical ``make`` verbs, so
        FLEXT architecture is never imposed on a non-member repository.
        """

        name: Annotated[t.NonEmptyStr, m.Field(description="Consumer display name")]
        root: Annotated[
            Path,
            m.Field(
                description=(
                    "Absolute checkout root of the consumer repository outside"
                    " this workspace"
                ),
            ),
        ]
        integration_branch: Annotated[
            t.NonEmptyStr | None,
            m.Field(
                description=(
                    "Consumer integration branch; absent defers to the"
                    " resolver's provider fallback"
                ),
            ),
        ] = None
        advance_locks: Annotated[
            bool,
            m.Field(
                description="Run the consumer's make upg so flext pins advance",
            ),
        ] = True
        fix_namespace: Annotated[
            bool,
            m.Field(description="Run the consumer's make fix-namespace verb"),
        ] = True
        fix_accessors: Annotated[
            bool,
            m.Field(description="Run the consumer's make fix-accessors verb"),
        ] = True

    class WorkspaceSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Local identity plus topology read from this repository's Git inputs."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Workspace name")]
        docs_audit: Annotated[
            FlextInfraConfigModelsContract.DocsAuditOverridesSpec,
            m.Field(
                description="Validated local documentation audit declarations",
            ),
        ] = m.Field(
            default_factory=FlextInfraConfigModelsContract.DocsAuditOverridesSpec
        )
        beads: Annotated[
            FlextInfraConfigModelsBeads.BeadsProjectSpec | None,
            m.Field(description="Repository-local Beads identity when enabled"),
        ] = None
        gascity_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Gas City runtime-contract participation resolved from the "
                    "matched repository policy overlay; True when the checkout "
                    "declares no manifest or no overlay."
                ),
            ),
        ] = True
        repository: Annotated[
            FlextInfraConfigModelsContexts.RepositoryRef,
            m.Field(description="Local repository Git contract"),
        ]
        project: Annotated[
            FlextInfraConfigModelsContexts.ProjectSpec | None,
            m.Field(description="Metadata required only when materializing a new tree"),
        ] = None
        flext_source: Annotated[
            FlextInfraConfigModelsWorkspace.CodegenBootstrapSource | None,
            m.Field(
                description=(
                    "FLEXT dependency source required before the first pyproject "
                    "exists; generated dependencies own provenance afterwards."
                ),
            ),
        ] = None
        namespace_scan_dirs: Annotated[
            t.StrSequence,
            m.Field(
                description=(
                    "Repository-level production roots the namespace validator "
                    "enforces; an empty declaration keeps every root in scope, and "
                    "an explicit project-level declaration wins"
                ),
            ),
        ] = ()
        integration: Annotated[
            FlextInfraConfigModelsContexts.WorkspaceIntegrationSpec | None,
            m.Field(
                description=(
                    "Declared integration provider and branch from the workspace "
                    "manifest; the resolver consults it before any Git fact"
                ),
            ),
        ] = None
        candidate_dependencies: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsWorkspace.DependencyCommitSourceSpec],
            m.Field(description="Candidate-only exact dependency Git sources"),
        ] = ()
        candidate_bootstrap_targets: Annotated[
            FlextInfraConfigModelsWorkspace.CandidateBootstrapTargets,
            m.Field(description="Declared candidate worktrees for bootstrap"),
        ] = ()
        subprojects: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsContexts.RepositoryRef],
            m.Field(description="Direct governed repositories from local .gitmodules"),
        ] = ()
        superproject_members: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Distribution names of the sibling members a superproject's "
                    "[tool.uv.workspace] declares when this checkout is one of "
                    "its members; empty for workspace roots and true standalones. "
                    "Attached manifests redirect sibling dependencies through "
                    "[tool.uv.sources] workspace = true while retaining inline "
                    "Git provenance for publication; standalone renders remove "
                    "the containing workspace source overlay."
                ),
            ),
        ] = ()
        external_dependency_paths: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Observed external or fork Git submodule paths"),
        ] = ()
        external_consumers: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsWorkspace.ExternalConsumerSpec],
            m.Field(
                description=(
                    "Out-of-workspace repositories propagation adjusts as"
                    " guests through their own make verbs"
                ),
            ),
        ] = ()

        @m.model_validator(mode="after")
        def _validate_topology_paths(self) -> Self:
            """Reject duplicate, ambiguous, or escaping topology paths.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If external dependency paths must be workspace-relative; or
                    if external dependency paths must be unique; or if subproject paths
                    must be unique; or if external dependencies cannot also be governed
                    subprojects; or if external consumers must declare unique names
                    with absolute roots.

            """
            invalid_external_paths = tuple(
                path
                for path in self.external_dependency_paths
                if path.is_absolute() or not path.parts or ".." in path.parts
            )
            if invalid_external_paths:
                msg = (
                    "external dependency paths must be workspace-relative: "
                    f"{', '.join(path.as_posix() for path in invalid_external_paths)}"
                )
                raise ValueError(msg)
            if len(set(self.external_dependency_paths)) != len(
                self.external_dependency_paths,
            ):
                msg = "external dependency paths must be unique"
                raise ValueError(msg)
            subproject_paths = {item.path for item in self.subprojects}
            if len(subproject_paths) != len(self.subprojects):
                msg = "subproject paths must be unique"
                raise ValueError(msg)
            overlap = subproject_paths.intersection(self.external_dependency_paths)
            if overlap:
                msg = (
                    "external dependencies cannot also be governed subprojects: "
                    f"{', '.join(sorted(path.as_posix() for path in overlap))}"
                )
                raise ValueError(msg)
            consumer_names = [item.name for item in self.external_consumers]
            if len(set(consumer_names)) != len(consumer_names):
                msg = "external consumer names must be unique"
                raise ValueError(msg)
            relative_roots = tuple(
                item.root
                for item in self.external_consumers
                if not item.root.is_absolute()
            )
            if relative_roots:
                msg = (
                    "external consumer roots must be absolute: "
                    f"{', '.join(path.as_posix() for path in relative_roots)}"
                )
                raise ValueError(msg)
            return self
