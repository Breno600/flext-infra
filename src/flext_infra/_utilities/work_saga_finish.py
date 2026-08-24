"""make work WHAT=finish saga step."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r

from flext_infra import FlextInfraWorktreeService, c, m, u
from flext_infra._utilities.work_saga_common import FlextInfraWorkSagaCommon

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkSagaFinish(FlextInfraWorkSagaCommon):
    """Finish step for the public work saga."""

    apply_changes: bool

    def _finish(self, primary_root: Path) -> p.Result[str]:
        if not self.apply_changes:
            return r.fail("work finish requires --apply")
        bead = (self.bead or "").strip()
        if not bead:
            return r.fail("work finish requires --bead")
        shown = u.Infra.beads_show(bead, root=self.workspace_root)
        if shown.failure:
            return r.fail(shown.error or f"unknown bead {bead}")
        metadata = shown.value.metadata
        if metadata is None:
            return r.fail(f"bead {bead} has no lane metadata")
        if not isinstance(metadata, m.Infra.ReadyLaneMetadata):
            return r.fail(f"bead {bead} lane is not ready for finish")
        branch = metadata.branch
        worktree = str(metadata.worktree)
        expected = metadata.head_oid
        pr_number = metadata.pr_number or ""
        integration = metadata.integration_base
        ownership = self._owned_reservation(bead, branch, metadata.worktree)
        if ownership.failure:
            return r.fail(ownership.error or "work finish reservation ownership failed")
        lane_meta = Path(worktree)
        if lane_meta == Path("removed"):
            return r.ok(
                self._format_receipt(
                    bead=bead,
                    operation=c.Infra.WorkOperation.FINISH,
                    primary=primary_root,
                    worktree=worktree,
                    branch=branch,
                    base=integration,
                    head_oid=expected,
                    pr=pr_number,
                )
            )
        if self._is_primary_path(primary_root, lane_meta):
            return r.fail("work finish refuses the primary worktree")
        permanent = self._refuse_permanent_branch(branch, integration)
        if permanent.failure:
            return r.fail(
                permanent.error or f"work finish refuses permanent branch {branch}"
            )
        branch_ref = f"refs/heads/{branch}"
        exists = u.Infra.git_ref_exists(
            m.Infra.GitRefRequest(repo_root=primary_root, reference=branch_ref)
        )
        if exists.failure:
            return r.fail(exists.error or f"failed to inspect local ref {branch}")
        if not lane_meta.is_dir():
            registered = FlextInfraWorktreeService.registered_lane(primary_root, branch)
            if registered.success:
                return r.fail(f"lane worktree missing: {lane_meta}")
            if exists.value.value:
                deleted = u.Infra.git_delete_ref(
                    m.Infra.GitDeleteRefRequest(
                        repo_root=primary_root,
                        reference=branch_ref,
                        expected_oid=expected,
                    )
                )
                if deleted.failure:
                    return r.fail(
                        deleted.error or f"failed to delete local ref {branch}"
                    )
            return self._record_finished_lane(primary_root, bead, metadata)
        bound = self._bound_registered_lane(primary_root, branch, worktree)
        if bound.failure:
            return r.fail(bound.error or "work finish lane binding failed")
        lane = bound.value
        topology = self._validated_lane_topology(primary_root, metadata, lane)
        if topology.failure:
            return r.fail(topology.error or "work finish topology validation failed")
        if isinstance(metadata.topology, m.Infra.EpicLaneTopology):
            children = FlextInfraWorktreeService.registered_children(primary_root, lane)
            if children.failure:
                return r.fail(children.error or "failed to inspect epic child lanes")
            if children.value:
                registered = ", ".join(str(child) for child in children.value)
                return r.fail(
                    f"work finish refuses epic while children are registered: {registered}"
                )
        if isinstance(metadata.topology, m.Infra.ChildLaneTopology):
            live = self._live_child_topology(
                primary_root, shown.value, metadata.topology
            )
            if live.failure:
                return r.fail(live.error or "work finish child binding failed")
        if not lane.is_dir():
            return r.fail(f"lane worktree missing: {lane}")
        merged = self._require_merged_pr(primary_root, branch, pr_number)
        if merged.failure:
            return r.fail(merged.error or "work finish PR state check failed")
        if not expected:
            return r.fail(f"bead {bead} missing metadata.head_oid for finish CAS")
        matrix = metadata.matrix
        if matrix is None:
            return r.fail("work finish requires matrix metadata")
        matrix_cas = self._validate_matrix_cas(lane, matrix)
        if matrix_cas.failure:
            return r.fail(matrix_cas.error or "work finish matrix CAS failed")
        for entry in matrix.entries:
            project_root = self._matrix_project_root(lane, entry.project)
            if project_root.failure:
                return r.fail(project_root.error or "matrix project is invalid")
            merged = self._require_merged_pr(
                project_root.value, entry.branch, entry.pr_number
            )
            if merged.failure:
                return r.fail(merged.error or "work finish PR state check failed")
        ownership = self._owned_reservation(bead, branch, lane)
        if ownership.failure:
            return r.fail(ownership.error or "work finish reservation changed")
        if isinstance(metadata.topology, m.Infra.ChildLaneTopology):
            live = self._live_child_topology(
                primary_root, shown.value, metadata.topology
            )
            if live.failure:
                return r.fail(live.error or "work finish child binding changed")
            advanced = self._merge_remote_epic(
                primary_root, shown.value, metadata.topology
            )
            if advanced.failure:
                return r.fail(advanced.error or "work finish epic merge-forward failed")
        removed = FlextInfraWorktreeService(
            workspace_root=primary_root,
            operation=c.Infra.WorktreeOperation.REMOVE,
            branch=branch,
            apply_changes=True,
        ).execute()
        if removed.failure:
            return r.fail(removed.error or f"failed to remove lane {branch}")
        deleted = u.Infra.git_delete_ref(
            m.Infra.GitDeleteRefRequest(
                repo_root=primary_root, reference=branch_ref, expected_oid=expected
            )
        )
        if deleted.failure:
            exists = u.Infra.git_ref_exists(
                m.Infra.GitRefRequest(repo_root=primary_root, reference=branch_ref)
            )
            if exists.success and exists.value.value:
                return r.fail(deleted.error or f"failed to delete local ref {branch}")
        return self._record_finished_lane(primary_root, bead, metadata)

    def _record_finished_lane(
        self, primary_root: Path, bead: str, metadata: m.Infra.ReadyLaneMetadata
    ) -> p.Result[str]:
        worktree = str(metadata.worktree)
        branch = metadata.branch
        matrix = metadata.matrix
        if matrix is None:
            return r.fail("work finish requires matrix metadata")
        notes = (
            f"work finish: cmd=make work WHAT=finish cwd={primary_root} exit=0 "
            f"decisive=removed {worktree} branch={branch}"
        )
        removed_matrix = m.Infra.WorkLaneMatrix(
            entries=tuple(
                entry.model_copy(update={"state": "removed"})
                for entry in matrix.entries
            )
        )
        removed_metadata = metadata.model_copy(
            update={"worktree": Path("removed"), "matrix": removed_matrix}
        )
        updated = u.Infra.beads_update_lane(
            bead, metadata=removed_metadata, notes=notes, root=self.workspace_root
        )
        if updated.failure:
            return r.fail(updated.error or "failed to record finish on bead")
        receipt = self._format_receipt(
            bead=bead,
            operation=c.Infra.WorkOperation.FINISH,
            primary=primary_root,
            worktree=worktree,
            branch=branch,
            base=metadata.integration_base,
            head_oid=metadata.head_oid,
            pr=metadata.pr_number or "",
        )
        return r.ok(f"FINISHED BRANCH={branch} WORKTREE={worktree}\n{receipt}")

    @staticmethod
    def _require_merged_pr(
        primary_root: Path, branch: str, pr_number: str
    ) -> p.Result[bool]:
        """Refuse to retire a lane whose pull request is not merged."""
        if not pr_number:
            open_prs = u.Cli.capture(
                (
                    "gh",
                    "pr",
                    "list",
                    "--head",
                    branch,
                    "--state",
                    "open",
                    "--json",
                    "number",
                ),
                cwd=primary_root,
            )
            if open_prs.failure:
                return r.fail(open_prs.error or f"failed to list open PRs for {branch}")
            if (open_prs.value or "").strip() not in {"", "[]"}:
                return r.fail(f"work finish refuses open PR on {branch}")
            return r.ok(True)
        viewed = u.Cli.capture(
            ("gh", "pr", "view", pr_number, "--json", "state,mergedAt,headRefName"),
            cwd=primary_root,
        )
        if viewed.failure:
            return r.fail(viewed.error or "failed to inspect PR merge state")
        payload = json.loads(viewed.value or "{}")
        state = str(payload.get("state") or "")
        head_ref = str(payload.get("headRefName") or "").strip()
        if head_ref and head_ref != branch:
            return r.fail(
                f"work finish PR #{pr_number} head {head_ref} "
                f"does not match lane branch {branch}"
            )
        if state.upper() != "MERGED" and not payload.get("mergedAt"):
            return r.fail(f"work finish requires merged PR #{pr_number}; state={state}")
        return r.ok(True)


__all__: list[str] = ["FlextInfraWorkSagaFinish"]
