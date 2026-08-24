"""Workspace and release CLI route ownership."""

from __future__ import annotations

from typing import ClassVar

from flext_infra import FlextInfraWorkService, c, m
from flext_infra.release.orchestrator import FlextInfraReleaseOrchestrator
from flext_infra.services.cli_route_base import CliRouteBase
from flext_infra.services.cli_routes_refactor import RefactorRoutes
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from flext_infra.workspace.environment_provenance import (
    FlextInfraWorkspaceEnvironmentProvenance,
)
from flext_infra.workspace.flext_binding import FlextInfraFlextBindingService
from flext_infra.workspace.orchestrator import FlextInfraOrchestratorService


class WorkspaceRoutes(RefactorRoutes):
    """Own refactor, release, and workspace routes."""

    workspace_routes: ClassVar[dict[str, tuple[m.Cli.ResultCommandRoute, ...]]] = {
        c.Infra.CLI_GROUP_REFACTOR: RefactorRoutes.refactor_routes,
        c.Infra.CLI_GROUP_RELEASE: (
            m.Cli.ResultCommandRoute(
                name=c.Infra.VERB_RUN,
                help_text="Run release orchestration CLI flow",
                model_cls=FlextInfraReleaseOrchestrator,
                handler=lambda params: FlextInfraReleaseOrchestrator.execute_command(
                    params
                ).map(CliRouteBase.as_route_value),
                success_message="Release completed successfully",
            ),
        ),
        c.Infra.CLI_GROUP_WORKSPACE: (
            m.Cli.ResultCommandRoute(
                name="verify-environment",
                help_text="Verify live workspace editable provenance",
                model_cls=m.Infra.WorkspaceEnvironmentRequest,
                handler=lambda params: (
                    FlextInfraWorkspaceEnvironmentProvenance.execute_request(
                        params
                    ).map(CliRouteBase.as_route_value)
                ),
                success_message="workspace editable provenance verified",
            ),
            m.Cli.ResultCommandRoute(
                name="flext-binding",
                help_text="Bind this project onto a flext worktree for the session",
                model_cls=m.Infra.FlextBindingRequest,
                handler=lambda params: FlextInfraFlextBindingService.apply(
                    consumer_root=params.workspace_root,
                    flext_root=params.flext_root,
                    python=params.python,
                ).map(CliRouteBase.as_route_value),
                success_message="flext worktree binding applied",
            ),
            *(
                m.Cli.ResultCommandRoute(
                    name=route_name,
                    help_text=help_text,
                    model_cls=model_cls,
                    handler=lambda params, mc=model_cls: mc.execute_command(params),
                )
                for route_name, help_text, model_cls in (
                    (
                        "detect",
                        "Detect workspace or standalone mode",
                        FlextInfraWorkspaceDetector,
                    ),
                    (
                        "orchestrate",
                        "Run make verb across projects",
                        FlextInfraOrchestratorService,
                    ),
                    (
                        "work",
                        "Unified bead/GitFlow/worktree/PR lane saga",
                        FlextInfraWorkService,
                    ),
                )
            ),
        ),
    }


__all__: list[str] = ["WorkspaceRoutes"]
