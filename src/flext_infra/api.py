"""Public API facade for flext-infra."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from flext_core import r
from flext_infra import m, t, u

from .base import s
from .check.workspace_check import FlextInfraWorkspaceChecker
from .validate.namespace_validator import FlextInfraNamespaceValidator
from .workspace.environment_beads import FlextInfraWorkspaceEnvironmentSync
from .workspace.rope import FlextInfraRopeWorkspace

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfra(FlextInfraWorkspaceEnvironmentSync, s[t.JsonDict]):
    """Thin public FLEXT facade over infra services."""

    app_name: ClassVar[str] = "flext-infra"

    def rope_workspace(
        self, repository_root: Path | None = None
    ) -> p.Infra.RopeWorkspaceDsl:
        """Open the public Rope workspace DSL directly from the facade."""
        # NOTE (multi-agent, flext-wkii.17.24): Rope reads its source policy
        # directly from config.Infra at the service boundary.
        resolved_root = (
            self.repository_root if repository_root is None else repository_root
        )
        return FlextInfraRopeWorkspace.open_workspace(resolved_root)

    def check(self, request: m.Infra.RunCommand) -> p.Result[bool]:
        """Compose one shared Rope cycle and execute every requested gate."""
        with FlextInfraRopeWorkspace.open_workspace(request.repository_root) as rope:
            return FlextInfraWorkspaceChecker(
                repository_root=request.repository_root, rope=rope
            ).execute_payload(request)

    def validate_namespace(
        self, repository_root: Path
    ) -> p.Result[m.Infra.ValidationReport]:
        """Validate one project through a single composed Rope cycle."""
        with FlextInfraRopeWorkspace.open_workspace(repository_root) as rope:
            return FlextInfraNamespaceValidator(
                repository_root=repository_root, rope=rope
            ).build_report()

    @staticmethod
    def project_context(cwd: Path) -> p.Result[m.Infra.WorkspaceProjectContext]:
        """Derive Git, workspace, and effective project facts from ``cwd``."""
        resolved = cwd.expanduser().resolve()
        if not resolved.is_dir():
            return r[m.Infra.WorkspaceProjectContext].fail(
                f"project context cwd is not a directory: {resolved}"
            )
        identity = u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=resolved))
        if identity.failure:
            return r[m.Infra.WorkspaceProjectContext].ok(
                m.Infra.WorkspaceProjectContext(cwd=resolved)
            )
        root = identity.value.repo_root
        if not (root / "config" / "beads.yaml").is_file():
            return r[m.Infra.WorkspaceProjectContext].ok(
                m.Infra.WorkspaceProjectContext(cwd=resolved, identity=identity.value)
            )
        workspace = u.Infra.workspace_spec_load(root)
        if workspace.failure:
            return r[m.Infra.WorkspaceProjectContext].from_failure(workspace)
        target = u.Infra.repository_conform_target(root, workspace.value)
        if target.failure:
            return r[m.Infra.WorkspaceProjectContext].from_failure(target)
        return r[m.Infra.WorkspaceProjectContext].ok(
            m.Infra.WorkspaceProjectContext(
                cwd=resolved,
                identity=identity.value,
                workspace=workspace.value,
                target=target.value,
                governed=True,
            )
        )

    @override
    def execute(self) -> p.Result[t.JsonDict]:
        """Execute a lightweight facade health report."""
        report: t.JsonDict = {
            "service": "flext-infra",
            "status": "ok",
            "repository_root": str(self.repository_root),
            "apply_changes": self.apply_changes,
        }
        return r[t.JsonDict].ok(report)


infra: FlextInfra = FlextInfra.fetch_global()
"""Shared FlextInfra facade instance."""


__all__: list[str] = ["FlextInfra", "infra"]
