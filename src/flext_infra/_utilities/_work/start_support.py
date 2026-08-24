"""Registered-lane adoption and epic resolution for work start."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import FlextInfraWorktreeService, c, m, u
from flext_infra._utilities._work.topology import FlextInfraWorkTopology

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkStartSupport(FlextInfraWorkTopology):
    """Prove reusable and epic lanes before provisioning begins."""

    workspace_root: Path

    @staticmethod
    def _reusable_lane(primary_root: Path, branch: str) -> Path | None:
        registered = FlextInfraWorktreeService.registered_lane(primary_root, branch)
        if registered.failure:
            return None
        lane = registered.value
        return lane if lane.is_dir() else None

    @staticmethod
    def _rollback_started_lane(
        primary_root: Path, branch: str, reused: Path | None, error: str | None
    ) -> str:
        reason = error or "failed to register lane on bead"
        if reused is not None:
            return reason
        removed = FlextInfraWorktreeService(
            workspace_root=primary_root,
            operation=c.Infra.WorktreeOperation.REMOVE,
            branch=branch,
            apply_changes=True,
        ).execute()
        if removed.failure:
            return (
                f"{reason}; lane {branch} rollback failed: "
                f"{removed.error or 'unknown worktree removal failure'}"
            )
        return f"{reason}; lane {branch} rolled back"

    def _registered_epic(
        self, primary_root: Path, child: m.Infra.BeadIssue, epic_bead: str
    ) -> p.Result[tuple[str, Path]]:
        topology = m.Infra.ChildLaneTopology(
            role=c.Infra.WorkLaneRole.CHILD,
            epic_bead=epic_bead,
            epic_branch="pending",
            epic_worktree=Path("pending"),
            child_slug="pending",
        )
        shown = u.Infra.beads_show(epic_bead, root=self.workspace_root)
        if shown.failure or not isinstance(
            shown.value.metadata, m.Infra.ReadyLaneMetadata
        ):
            return r.fail(shown.error or f"epic bead {epic_bead} lane is not ready")
        metadata = shown.value.metadata
        topology = topology.model_copy(
            update={"epic_branch": metadata.branch, "epic_worktree": metadata.worktree}
        )
        bound = self._live_child_topology(primary_root, child, topology)
        if bound.failure:
            return r.fail(bound.error or "epic binding failed")
        return r.ok((metadata.branch, bound.value))


__all__: list[str] = ["FlextInfraWorkStartSupport"]
