"""Multi-project orchestration service."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, override

from flext_core import r
from flext_infra import c, m, s, t

from ._orchestrator_discovery import FlextInfraWorkspaceOrchestratorDiscoveryMixin
from ._orchestrator_execution import FlextInfraWorkspaceOrchestratorExecutionMixin

if TYPE_CHECKING:
    from flext_infra import p
    from flext_infra.base import FlextInfraServiceBase


class FlextInfraOrchestratorService(
    s[bool],
    FlextInfraWorkspaceOrchestratorDiscoveryMixin,
    FlextInfraWorkspaceOrchestratorExecutionMixin,
):
    """Infrastructure service for multi-project make orchestration."""

    repository_root: Annotated[
        Path,
        m.Field(
            default_factory=Path.cwd,
            description="Repository root containing every orchestrated project.",
        ),
    ]
    verb: Annotated[str, m.Field(description="Make verb to execute")]
    projects: Annotated[
        t.StrSequence | None,
        m.Field(description="Projects to process; repeat --projects NAME as needed"),
    ] = None

    @m.computed_field
    @override
    @property
    def root(self) -> Path:
        """Canonical workspace root."""
        return self.repository_root.resolve()

    @override
    @classmethod
    def execute_command(cls, params: FlextInfraServiceBase[bool]) -> p.Result[bool]:
        """Execute the already validated internal orchestration request."""
        return params.execute()

    @override
    def execute(self) -> p.Result[bool]:
        """Execute the workspace-orchestrate CLI flow."""
        allowed_verbs = c.Infra.ORCHESTRATED_VERBS
        if self.verb not in allowed_verbs:
            allowed = ", ".join(allowed_verbs)
            return r[bool].fail(
                f"unsupported orchestrate verb '{self.verb}' (allowed: {allowed})"
            )

        resolved_projects = self._resolved_projects()
        if resolved_projects.failure:
            return r[bool].from_failure(resolved_projects)

        projects = resolved_projects.value
        if not projects:
            return r[bool].fail("no projects discovered")

        repository_root: Path = self.root
        orchestrate_result = self.orchestrate(
            projects=[
                self._project_target(project, repository_root=repository_root)
                for project in projects
            ],
            verb=self.verb,
        )
        if orchestrate_result.failure:
            return r[bool].from_failure(orchestrate_result)
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraOrchestratorService"]
