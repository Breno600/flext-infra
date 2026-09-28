"""Workspace orchestration discovery helpers.

Keeps project lookup and workspace bootstrap preparation concerns isolated from the
main public orchestrator facade.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from flext_infra import m, t, u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p

    class _WorkspaceOrchestratorProtocol(Protocol):
        @property
        def root(self) -> Path: ...

        @property
        def projects(self) -> t.StrSequence | None: ...


class FlextInfraWorkspaceOrchestratorDiscoveryMixin:
    """Resolve workspace projects and materialize project-level artifacts."""

    def _resolved_projects(
        self: _WorkspaceOrchestratorProtocol,
    ) -> p.Result[t.SequenceOf[m.Infra.ProjectInfo]]:
        """Resolve the declared project inventory, narrowed by explicit selection."""
        return u.Infra.resolve_projects(self.root, self.projects or ())

    @staticmethod
    def _project_target(project: m.Infra.ProjectInfo, *, repository_root: Path) -> str:
        """Map a project info object into a relative make target."""
        project_path = project.path.resolve()
        resolved_repository_root = repository_root.resolve()
        try:
            return str(project_path.relative_to(resolved_repository_root))
        except ValueError:
            return str(project_path)


__all__: list[str] = ["FlextInfraWorkspaceOrchestratorDiscoveryMixin"]
