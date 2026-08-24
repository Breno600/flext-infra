"""Domain models for the github subpackage."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from flext_cli import m
from flext_infra import t
from flext_infra._models.mixins import FlextInfraModelsMixins as mm


class FlextInfraModelsGithub:
    """Models for GitHub PR orchestration and repository management."""

    class GithubWorkflowSyncRequest(mm.WriteMixin, m.ContractModel):
        """CLI/service request for workflow synchronization."""

        report: Annotated[str | None, m.Field(description="Output report file")] = None
        prune: Annotated[bool, m.Field(description="Remove unknown files")] = False

        @property
        def report_path(self) -> Path | None:
            """Resolved report path when provided."""
            return Path(self.report).resolve() if self.report else None

    class GithubWorkflowLintRequest(mm.ReadMixin, m.ContractModel):
        """CLI/service request for workflow lint."""

        strict: Annotated[bool, m.Field(description="Strict mode")] = False

    class GithubPullRequestRequest(
        mm.GithubPullRequestFieldsMixin, mm.WriteMixin, m.ContractModel
    ):
        """CLI/service request for a single-repository PR action."""

        repo_root: Annotated[str, m.Field(..., description="Repository root directory")]

        @property
        def repo_root_path(self) -> Path:
            """Resolved repository root path."""
            return Path(self.repo_root).resolve()

    class GithubPullRequestWorkspaceRequest(
        mm.WorkspaceCliRequestMixin,
        mm.GithubPullRequestFieldsMixin,
        mm.WriteMixin,
        m.ContractModel,
    ):
        """CLI/service request for workspace-wide PR automation."""

    class GithubPullRequestOutcome(m.ArbitraryTypesModel):
        """Outcome of a single pull-request command on one repository."""

        display: Annotated[
            t.NonEmptyStr, m.Field(description="Repository display name")
        ]
        status: Annotated[t.NonEmptyStr, m.Field(description="Execution status")]
        elapsed: Annotated[
            t.NonNegativeInt, m.Field(description="Elapsed time in seconds")
        ]
        exit_code: Annotated[int, m.Field(description="Process exit code")]
        log_path: Annotated[str | None, m.Field(description="Log file path")] = None

        @property
        def message(self) -> str:
            """CLI-facing success or failure summary."""
            return f"{self.display}: {self.status} (exit={self.exit_code})"

    class GithubPullRequestWorkspaceReport(m.ArbitraryTypesModel):
        """Aggregated report for workspace-wide pull-request execution."""

        total: Annotated[
            t.NonNegativeInt, m.Field(description="Total repositories processed")
        ]
        success: Annotated[
            t.NonNegativeInt, m.Field(description="Successful executions")
        ]
        fail: Annotated[t.NonNegativeInt, m.Field(description="Failed executions")]
        outcomes: t.VariadicTuple[FlextInfraModelsGithub.GithubPullRequestOutcome] = (
            m.Field(default_factory=tuple, description="Per-repository outcomes")
        )

        @property
        def message(self) -> str:
            """CLI-facing workspace summary."""
            return f"workspace PR run: {self.success}/{self.total} successful"

    class RepoUrls(m.ArbitraryTypesModel):
        """Repository URL pair with SSH and HTTPS variants."""

        ssh_url: Annotated[str, m.Field(description="SSH clone URL")] = ""
        https_url: Annotated[str, m.Field(description="HTTPS clone URL")] = ""

    class GithubWorkflowLintOutcome(m.ArbitraryTypesModel):
        """Outcome payload for workflow lint execution."""

        status: Annotated[t.NonEmptyStr, m.Field(description="Lint status")]
        reason: Annotated[str | None, m.Field(description="Skip reason")] = None
        detail: Annotated[str | None, m.Field(description="Failure detail")] = None
        exit_code: Annotated[int | None, m.Field(description="Process exit code")] = (
            None
        )
        stdout: Annotated[str | None, m.Field(description="Captured stdout")] = None
        stderr: Annotated[str | None, m.Field(description="Captured stderr")] = None

        @property
        def message(self) -> str:
            """CLI-facing lint summary."""
            if self.status == "ok":
                return "workflow lint passed"
            if self.status == "skipped" and self.reason:
                return f"workflow lint skipped: {self.reason}"
            if self.detail:
                return f"workflow lint failed: {self.detail}"
            if self.reason:
                return f"workflow lint failed: {self.reason}"
            return "workflow lint failed"

    class GithubWorkflowSyncOperation(mm.ProjectNameMixin, m.ArbitraryTypesModel):
        """Describe one workflow synchronization operation."""

        path: Annotated[
            str, m.Field(..., description="File path relative to project root.")
        ]
        action: Annotated[
            str, m.Field(..., description="Sync action (create, update, noop, prune).")
        ]
        reason: Annotated[str, m.Field(..., description="Reason for the action.")]

    class GithubWorkflowSyncReport(m.ArbitraryTypesModel):
        """Structured report for a workflow synchronization request."""

        mode: Annotated[str, m.Field(description="Execution mode")]
        summary: Annotated[
            t.JsonMapping, m.Field(description="Count of operations by action")
        ]
        operations: t.VariadicTuple[
            FlextInfraModelsGithub.GithubWorkflowSyncOperation
        ] = m.Field(default_factory=tuple, description="Workflow operations")

        @classmethod
        def from_operations(
            cls,
            *,
            apply: bool,
            operations: t.MutableSequenceOf[
                FlextInfraModelsGithub.GithubWorkflowSyncOperation
            ],
        ) -> FlextInfraModelsGithub.GithubWorkflowSyncReport:
            """Build a typed report from collected operations."""
            summary: dict[str, int] = {}
            for operation in operations:
                summary[operation.action] = summary.get(operation.action, 0) + 1
            return cls(
                mode="apply" if apply else "dry-run",
                summary=summary,
                operations=tuple(operations),
            )

        @property
        def message(self) -> str:
            """CLI-facing sync summary."""
            return f"github workflows {self.mode}: {len(self.operations)} operations"

    class GithubWorkflowSyncContext(mm.ProjectNameFieldMixin, m.ArbitraryTypesModel):
        """Resolved context for syncing workflows in one project."""

        project_root: Annotated[Path, m.Field(description="Project root path")]
        rendered_template: Annotated[str, m.Field(description="Rendered workflow body")]
        request: Annotated[
            FlextInfraModelsGithub.GithubWorkflowSyncRequest,
            m.Field(description="Original sync request"),
        ]

        @property
        def workflows_dir(self) -> Path:
            """Workflows dir."""
            return self.project_root / ".github" / "workflows"

        @property
        def ci_destination(self) -> Path:
            """Ci destination."""
            return self.workflows_dir / "ci.yml"

        @property
        def apply(self) -> bool:
            """Apply."""
            return self.request.apply

        @property
        def prune(self) -> bool:
            """Prune."""
            return self.request.prune

    class GithubPullRequestWorkspaceContext(
        mm.WorkspaceRootPathMixin, m.ArbitraryTypesModel
    ):
        """Resolved context for workspace-wide pull-request execution."""

        request: Annotated[
            FlextInfraModelsGithub.GithubPullRequestWorkspaceRequest,
            m.Field(description="Original workspace pull-request request"),
        ]
        outcomes: Annotated[
            t.MutableSequenceOf[FlextInfraModelsGithub.GithubPullRequestOutcome],
            m.Field(description="Accumulated pull-request outcomes"),
        ] = m.Field(description="Accumulated pull-request outcomes")


__all__: list[str] = ["FlextInfraModelsGithub"]
