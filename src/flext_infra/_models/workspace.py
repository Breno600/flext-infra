"""Domain models for the workspace subpackage.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar

from flext_cli import m

from flext_infra import c, t
from flext_infra._models._config.base import FlextInfraConfigModels
from flext_infra._models._config.contexts import FlextInfraConfigModelsContexts
from flext_infra._models._git.identity import FlextInfraModelsGitIdentity
from flext_infra._models.mixins import FlextInfraModelsMixins


class FlextInfraModelsWorkspace:
    """Models for workspace discovery and orchestration.

    Canonical base policy:
    - ``ArbitraryTypesModel`` for mutable discovery payloads.
    - ``ContractModel`` reserved for immutable workspace settings contracts.
    """

    class WorkspaceEnvironmentRequest(m.ContractModel):
        """Read-only request for validating the active workspace environment."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(populate_by_name=True)

        repository_root: Annotated[Path, m.Field(description="Repository root path")]

    class LifecycleReceipt(m.ContractModel):
        """One public Make invocation; an absent exit is never a green receipt."""

        command: Annotated[
            t.VariadicTuple[str], m.Field(description="Public Make argv")
        ]
        cwd: Annotated[Path, m.Field(description="Repository execution directory")]
        output_file: Annotated[
            Path,
            m.Field(description="Durable combined stdout/stderr for reached steps"),
        ]
        exit_code: Annotated[
            int | None,
            m.Field(
                description="Observed exit; absent when unreached or launch failed"
            ),
        ] = None
        error: Annotated[
            str | None, m.Field(description="First execution failure, if observed")
        ] = None

    class LifecycleReport(m.ContractModel):
        """Complete declared scope and ordered reached/unreached lifecycle receipts."""

        workspace_root: Annotated[Path, m.Field(description="Invoking workspace root")]
        scope: Annotated[t.VariadicTuple[Path], m.Field(description="Governed roots")]
        receipts: Annotated[
            t.VariadicTuple[FlextInfraModelsWorkspace.LifecycleReceipt],
            m.Field(description="Ordered public command receipts for the entire scope"),
        ]

    class SubprojectLoadContext(m.ContractModel):
        """Workspace governance scope shared by every declared subproject entry."""

        integration_branch: Annotated[
            str | None,
            m.Field(
                description=(
                    "Resolved workspace integration line; absent defers to the "
                    "provider's conventional branch fallback"
                ),
            ),
        ] = None
        workspace_beads: Annotated[
            FlextInfraConfigModels.BeadsProjectSpec | None,
            m.Field(description="Workspace Beads ledger spec; absent disables routing"),
        ] = None
        allow_unprovisioned_members: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether declared Python members may stay unprovisioned "
                    "checkouts while CI omits them deliberately"
                ),
            ),
        ] = False

        declared_member: Annotated[
            FlextInfraConfigModelsContexts.RepositoryRef | None,
            m.Field(
                description="Catalog-declared member reference for this entry",
            ),
        ] = None

    class EnvironmentContractViolation(
        FlextInfraModelsMixins.PositiveLineMixin,
        m.ContractModel,
    ):
        """One static ``.envrc``/``.envrc.local`` contract violation.

        The line is carried as a typed field; the consuming gate renders the
        canonical ``line N: <message>`` text, so the textual projection stays at
        the reporting boundary and never in the declaration layer.
        """

        message: Annotated[
            str,
            m.Field(description="Violation description without the line prefix"),
        ]
        token: Annotated[
            str,
            m.Field(description="Offending token when the contract is token-based"),
        ] = ""

    class WorkspaceProjectContext(m.ContractModel):
        """Canonical context derived from one runtime working directory."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        cwd: Annotated[Path, m.Field(description="Resolved submitted directory")]
        identity: Annotated[
            FlextInfraModelsGitIdentity.GitIdentityReport | None,
            m.Field(description="Observed Git identity, absent outside a repository"),
        ] = None
        workspace: Annotated[
            FlextInfraConfigModels.WorkspaceSpec | None,
            m.Field(description="Governed workspace contract when declared"),
        ] = None
        target: Annotated[
            FlextInfraConfigModels.RepositoryConformTarget | None,
            m.Field(description="Effective governed project properties"),
        ] = None
        governed: Annotated[
            bool,
            m.Field(description="Whether repository-local FLEXT governance exists"),
        ] = False

    class FlextBindingRequest(m.ContractModel):
        """Session request binding one consumer onto a flext worktree."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(populate_by_name=True)

        repository_root: Annotated[Path, m.Field(description="Consumer project root")]
        flext_root: Annotated[
            Path,
            m.Field(description="Flext worktree supplying the packages"),
        ]
        python: Annotated[
            Path,
            m.Field(description="Interpreter of the environment to rebind"),
        ]

    class DirectUrlDirectoryInfo(m.ContractModel):
        """PEP 610 directory metadata for one installed distribution."""

        editable: Annotated[
            bool,
            m.Field(description="Distribution is installed as editable"),
        ] = False

    class DirectUrlVcsInfo(m.ContractModel):
        """Native PEP 610 VCS identity, independent of a moving requested ref."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="ignore",
            frozen=True,
        )
        vcs: Annotated[str, m.Field(description="Native VCS kind")]
        commit_id: Annotated[str, m.Field(description="Installed full commit identity")]

    class DirectUrlReceipt(m.ContractModel):
        """Any installed distribution's PEP 610 receipt, read for its kind only.

        VCS and archive receipts carry other keys; only the directory metadata
        decides whether the receipt names a checkout path.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore", frozen=True)

        dir_info: Annotated[
            FlextInfraModelsWorkspace.DirectUrlDirectoryInfo | None,
            m.Field(description="Directory metadata of a local install"),
        ] = None
        url: Annotated[
            t.NonEmptyStr,
            m.Field(description="Required PEP 610 origin URL"),
        ]
        vcs_info: FlextInfraModelsWorkspace.DirectUrlVcsInfo | None = m.Field(
            default=None,
            description="Installed immutable VCS identity",
        )

    class LockedPackageSource(m.ContractModel):
        """Only the lock's immutable installation source fields cross this boundary."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore", frozen=True)
        git: str | None = m.Field(default=None, description="Locked VCS URL and SHA")
        registry: str | None = m.Field(
            default=None,
            description="Locked registry artifact",
        )
        editable: str | None = m.Field(default=None, description="Local root source")
        directory: str | None = m.Field(
            default=None,
            description="Noneditable directory",
        )

    class LockedPackage(m.ContractModel):
        """Installed identity selected from the committed uv lock."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore", frozen=True)
        name: Annotated[str, m.Field(description="Locked distribution name")]
        version: Annotated[str, m.Field(description="Locked distribution version")]
        source: Annotated[
            FlextInfraModelsWorkspace.LockedPackageSource,
            m.Field(description="Locked source identity"),
        ]

    class LockedEnvironment(m.ContractModel):
        """Typed installation identities, never a dependency resolver."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore", frozen=True)
        package: Annotated[
            t.VariadicTuple[FlextInfraModelsWorkspace.LockedPackage],
            m.Field(description="Lock-owned package inventory"),
        ]

    class EditableDirectUrl(m.ContractModel):
        """Validated PEP 610 editable provenance payload."""

        url: Annotated[t.NonEmptyStr, m.Field(description="Editable source URL")]
        dir_info: Annotated[
            FlextInfraModelsWorkspace.DirectUrlDirectoryInfo,
            m.Field(description="Editable directory metadata"),
        ]

    class FleetPullRequest(m.ContractModel):
        """One open pull request observed in a member repository."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        number: Annotated[
            int,
            m.Field(description="Provider pull-request number"),
        ]
        head: Annotated[
            str,
            m.Field(description="Branch the pull request proposes"),
        ]
        title: Annotated[str, m.Field(description="Pull-request title")]
        url: Annotated[str, m.Field(description="Pull-request web address")]

    class FleetRepoGaps(m.ContractModel):
        """One repository's row of the workspace fleet-gaps report.

        Quality counts come only from explicitly selected, project-bound check
        invocations. None means unknown/not executed, never PASS. Other hygiene
        probes retain their independent presence and empty-value contracts.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        name: Annotated[str, m.Field(description="Repository name")]
        root: Annotated[Path, m.Field(description="Repository checkout root")]
        present: Annotated[
            bool,
            m.Field(description="Whether the declared checkout exists on disk"),
        ]
        dirty_paths: Annotated[
            t.StrSequence,
            m.Field(description="Porcelain status paths of the checkout"),
        ]
        open_pull_requests: Annotated[
            t.VariadicTuple[FlextInfraModelsWorkspace.FleetPullRequest],
            m.Field(description="Open pull requests; empty when the query fails"),
        ]
        unmerged_branches: Annotated[
            int,
            m.Field(description="Local branches not merged into the integration line"),
        ]
        lint_findings: Annotated[
            t.NonNegativeInt | None,
            m.Field(
                description="Executed eligible lint findings; null is unknown/not "
                "executed",
            ),
        ]
        pyrefly_findings: Annotated[
            t.NonNegativeInt | None,
            m.Field(
                description="Executed eligible Pyrefly findings; null is unknown/not "
                "executed",
            ),
        ]
        codemod_findings: Annotated[
            int,
            m.Field(
                description="Mod scan findings from the checkout's receipt; 0 absent",
            ),
        ]
        agents_doc_present: Annotated[
            bool,
            m.Field(description="Whether the checkout declares its AGENTS.md"),
        ]
        skills_stamp_present: Annotated[
            bool,
            m.Field(description="Whether the skills provisioning stamp exists"),
        ]
        skills_stamp_distribution_version: Annotated[
            str,
            m.Field(
                description=(
                    "Stamp's distribution_version; empty when the stamp is absent"
                ),
            ),
        ]
        beads_config_present: Annotated[
            bool,
            m.Field(description="Whether the Beads runtime identity exists"),
        ]

    class FleetGapsReport(m.ContractModel):
        """Typed receipt of one workspace fleet-gaps run.

        The report carries no wall-clock field: an unchanged tree produces a
        byte-identical receipt, so a rerun is its own idempotence proof.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        schema_version: Annotated[
            int,
            m.Field(description="Report schema version"),
        ]
        workspace_root: Annotated[
            Path,
            m.Field(description="Invoking workspace root"),
        ]
        workspace_name: Annotated[str, m.Field(description="Workspace identity name")]
        repos: Annotated[
            t.VariadicTuple[FlextInfraModelsWorkspace.FleetRepoGaps],
            m.Field(description="One row per declared member and external consumer"),
        ]

    class ProjectInfo(
        FlextInfraModelsMixins.ProjectEntryNameMixin,
        m.ArbitraryTypesModel,
    ):
        """Discovered project metadata for workspace operations."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            frozen=True,
            validate_default=False,
        )

        path: Annotated[Path, m.Field(description="Absolute or relative project path")]
        stack: Annotated[t.NonEmptyStr, m.Field(description="Primary technology stack")]
        has_tests: Annotated[bool, m.Field(description="Project has test suite")] = (
            False
        )
        has_src: Annotated[
            bool,
            m.Field(description="Project has source directory"),
        ] = True
        project_class: Annotated[
            t.NonEmptyStr,
            m.Field(description="Docs/governance project classification"),
        ] = "platform"
        package_name: Annotated[
            str,
            m.Field(description="Primary Python package name"),
        ] = ""
        make_profile: Annotated[
            c.Infra.MakeProfile,
            m.Field(description="Topology proven by this checkout's .gitmodules"),
        ] = c.Infra.MakeProfile.STANDALONE
        declared_subproject: Annotated[
            bool,
            m.Field(description="Whether the aggregate workspace declares this path"),
        ] = False

    class ProjectPyprojectState(m.ArbitraryTypesModel):
        """Centralized parsed pyproject state reused across discovery services.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            frozen=True,
            validate_default=False,
        )

        project_root: Annotated[Path, m.Field(description="Project root path")]
        pyproject_path: Annotated[Path, m.Field(description="Resolved pyproject path")]
        payload: Annotated[
            t.JsonMapping,
            m.Field(description="Parsed pyproject payload"),
        ]
        docs_meta: Annotated[
            t.JsonMapping,
            m.Field(description="Parsed tool.flext.docs payload"),
        ]
        project_name: Annotated[str, m.Field(description="Declared project name")] = ""
        package_name: Annotated[str, m.Field(description="Primary package name")] = ""
        dependency_names: Annotated[
            t.StrSequence,
            m.Field(description="Declared dependency names"),
        ] = m.Field(default_factory=tuple)


__all__: list[str] = ["FlextInfraModelsWorkspace"]
