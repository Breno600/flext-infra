"""Workspace and release CLI route ownership.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import ClassVar

from flext_infra import c, infra, m, p, t, u
from flext_infra.git import FlextInfraGitService
from flext_infra.release.orchestrator import FlextInfraReleaseOrchestrator
from flext_infra.services.cli_route_base import FlextInfraCliRouteBase
from flext_infra.services.cli_routes_refactor import FlextInfraRefactorRoutes
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from flext_infra.workspace.environment import FlextInfraWorkspaceEnvironmentMixin
from flext_infra.workspace.environment_provenance import (
    FlextInfraWorkspaceEnvironmentProvenance,
)
from flext_infra.workspace.flext_binding import FlextInfraBindingService
from flext_infra.workspace.propagation import FlextInfraWorkspacePropagation


class FlextInfraWorkspaceRoutes(FlextInfraRefactorRoutes):
    """Own refactor, release, and workspace routes."""

    @staticmethod
    def _apply_flext_binding(
        params: m.Infra.FlextBindingRequest,
    ) -> p.Result[t.Cli.ResultValue]:
        """Apply the typed binding request through its service owner.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        return FlextInfraBindingService.apply(
            consumer_root=params.repository_root,
            flext_root=params.flext_root,
            python=params.python,
        ).map(FlextInfraCliRouteBase.as_route_value)

    @staticmethod
    def _sync_environment(
        params: m.Infra.WorkspaceEnvironmentCliRequest,
    ) -> p.Result[t.Cli.ResultValue]:
        """Keep the internal beads render context off the public CLI surface.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        request = m.Infra.WorkspaceEnvironmentSyncRequest.model_validate(
            params.model_dump(),
        )
        return FlextInfraWorkspaceEnvironmentMixin.execute_request(request).map(
            FlextInfraCliRouteBase.as_route_value,
        )

    workspace_routes: ClassVar[
        MutableMapping[str, t.VariadicTuple[m.Cli.ResultCommandRoute]]
    ] = {
        c.Infra.CLI_GROUP_REFACTOR: FlextInfraRefactorRoutes.refactor_routes,
        c.Infra.CLI_GROUP_RELEASE: (
            m.Cli.ResultCommandRoute(
                name=c.Infra.VERB_RUN,
                help_text="Run release orchestration CLI flow",
                model_cls=FlextInfraReleaseOrchestrator,
                handler=FlextInfraCliRouteBase.result_handler(infra.release_run),
                success_message="Release completed successfully",
            ),
        ),
        c.Infra.CLI_GROUP_WORKSPACE: (
            m.Cli.ResultCommandRoute(
                name="validate-lifecycle",
                help_text="Validate the root and governed member lifecycles serially",
                model_cls=m.Infra.WorkspaceEnvironmentRequest,
                handler=FlextInfraCliRouteBase.result_handler(
                    FlextInfraWorkspaceLifecycle.execute_request,
                ),
                success_message="workspace serial lifecycle validated",
            ),
            m.Cli.ResultCommandRoute(
                name="verify-lane",
                help_text=(
                    "Verify stash absence and declared live integration ancestry "
                    "without effects"
                ),
                model_cls=m.Infra.GitLaneVerificationRequest,
                handler=FlextInfraCliRouteBase.result_handler(
                    FlextInfraGitService.verify_lane,
                ),
                success_message="lane stash and live integration ancestry verified",
            ),
            m.Cli.ResultCommandRoute(
                name="verify-lanes",
                help_text="Read-only lane inventory, ownership census, and refusals",
                model_cls=m.Infra.GitLaneVerificationRequest,
                handler=FlextInfraCliRouteBase.result_handler(
                    FlextInfraGitService.verify_lanes,
                ),
                success_message="lane inventory verified",
            ),
            m.Cli.ResultCommandRoute(
                name="identity",
                help_text="Report canonical Git checkout identity",
                model_cls=m.Infra.GitRepoRequest,
                handler=FlextInfraCliRouteBase.result_handler(u.Infra.git_identity),
                success_message="workspace Git identity resolved",
            ),
            m.Cli.ResultCommandRoute(
                name="verify-clean",
                help_text=(
                    "Fail if a Git worktree has staged, unstaged, or untracked changes"
                ),
                model_cls=m.Infra.GitStatusRequest,
                handler=FlextInfraCliRouteBase.result_handler(
                    FlextInfraGitService.verify_clean,
                ),
                success_message="workspace Git worktree is clean",
            ),
            m.Cli.ResultCommandRoute(
                name="verify-environment",
                help_text="Verify live workspace editable provenance",
                model_cls=m.Infra.WorkspaceEnvironmentRequest,
                handler=FlextInfraCliRouteBase.result_handler(
                    FlextInfraWorkspaceEnvironmentProvenance.execute_request,
                ),
                success_message="workspace editable provenance verified",
            ),
            m.Cli.ResultCommandRoute(
                name="flext-binding",
                help_text="Bind this project onto a flext worktree for the session",
                model_cls=m.Infra.FlextBindingRequest,
                handler=_apply_flext_binding,
                success_message="flext worktree binding applied",
            ),
            *(
                m.Cli.ResultCommandRoute(
                    name=route_name,
                    help_text=help_text,
                    model_cls=model_cls,
                    handler=handler,
                )
                for route_name, help_text, model_cls, handler in (
                    (
                        "detect",
                        "Detect workspace or standalone mode",
                        FlextInfraWorkspaceDetector,
                        FlextInfraCliRouteBase.result_handler(
                            FlextInfraWorkspaceDetector.execute_command,
                        ),
                    ),
                    (
                        "propagate",
                        "Publish this workspace's flext-infra to every member",
                        FlextInfraWorkspacePropagation,
                        FlextInfraCliRouteBase.result_handler(
                            infra.workspace_propagate,
                        ),
                    ),
                    (
                        "sync-environment",
                        "Sync generated direnv/mise environment files",
                        m.Infra.WorkspaceEnvironmentCliRequest,
                        _sync_environment,
                    ),
                )
            ),
        ),
    }


__all__: list[str] = ["FlextInfraWorkspaceRoutes"]
