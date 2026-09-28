"""Live Beads reservation ownership proofs for work operations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import FlextInfraWorktreeService, c, m, u

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkOwnership:
    """Authorize one Bead against unique active branch and path reservations."""

    workspace_root: Path

    def _owned_reservation(
        self, bead_id: str, branch: str, worktree: Path
    ) -> p.Result[m.Infra.BeadIssue]:
        listed = u.Infra.beads_list_reservations(root=self.workspace_root)
        if listed.failure:
            return r.fail(listed.error or "failed to list lane reservations")
        owners = tuple(
            issue
            for issue in listed.value
            if issue.status in c.Infra.WORK_ACTIVE_ISSUE_STATUSES
            and issue.metadata is not None
            and (
                issue.metadata.branch == branch
                or issue.metadata.worktree.resolve() == worktree.resolve()
            )
        )
        if len(owners) != 1:
            owner_ids = ",".join(issue.id for issue in owners) or "none"
            return r.fail(
                f"lane reservation requires one active owner: branch={branch} "
                f"worktree={worktree} owners={owner_ids}"
            )
        owner = owners[0]
        if owner.id != bead_id:
            return r.fail(
                f"lane reservation owned by foreign bead {owner.id}: "
                f"branch={branch} worktree={worktree}"
            )
        metadata = owner.metadata
        if metadata is None or metadata.branch != branch:
            return r.fail(f"bead {bead_id} reservation branch mismatch")
        if metadata.worktree.resolve() != worktree.resolve():
            return r.fail(f"bead {bead_id} reservation worktree mismatch")
        return r.ok(owner)

    def _assert_start_reservation(
        self, primary_root: Path, bead_id: str, branch: str, epic_lane: Path | None
    ) -> p.Result[Path]:
        canonical = FlextInfraWorktreeService.canonical_lane_path(
            primary_root, branch, epic_lane
        )
        if canonical.failure:
            return r.fail(canonical.error or "failed to derive canonical lane path")
        listed = u.Infra.beads_list_reservations(root=self.workspace_root)
        if listed.failure:
            return r.fail(listed.error or "failed to list lane reservations")
        collisions = tuple(
            issue
            for issue in listed.value
            if issue.status in c.Infra.WORK_ACTIVE_ISSUE_STATUSES
            and issue.metadata is not None
            and (
                issue.metadata.branch == branch
                or issue.metadata.worktree.resolve() == canonical.value.resolve()
            )
        )
        foreign = tuple(issue for issue in collisions if issue.id != bead_id)
        if foreign:
            return r.fail(
                f"lane reservation collision with foreign bead {foreign[0].id}: "
                f"branch={branch} worktree={canonical.value}"
            )
        same = tuple(issue for issue in collisions if issue.id == bead_id)
        if len(same) > 1:
            return r.fail(f"duplicate active reservation inventory for bead {bead_id}")
        if same:
            metadata = same[0].metadata
            if metadata is None or metadata.branch != branch:
                return r.fail(f"bead {bead_id} reservation branch mismatch")
            if metadata.worktree.resolve() != canonical.value.resolve():
                return r.fail(f"bead {bead_id} reservation worktree mismatch")
        return r.ok(canonical.value)


__all__: list[str] = ["FlextInfraWorkOwnership"]
