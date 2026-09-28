from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import m

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorktreeLifecycle:
    @staticmethod
    def rollback_new_lane(
        primary_root: Path,
        lane: Path,
        branch: str,
        created_branch_oid: str | None,
        setup_error: str,
    ) -> p.Result[str]:
        from flext_infra import u

        status = u.Infra.git_status(m.Infra.GitStatusRequest(repo_root=lane))
        if status.failure:
            return r[str].from_failure(status)
        if status.value.dirty:
            return r[str].fail(
                f"worktree setup failed: {setup_error}; preserving lane {lane} "
                "because setup left worktree changes"
            )
        cleanup = u.Infra.git_remove_clean_worktree(primary_root, lane)
        if cleanup.failure:
            return r[str].from_failure(cleanup)
        if created_branch_oid is not None:
            branch_cleanup = u.Infra.git_delete_ref(
                m.Infra.GitDeleteRefRequest(
                    repo_root=primary_root,
                    reference=f"refs/heads/{branch}",
                    expected_oid=created_branch_oid,
                )
            )
            if branch_cleanup.failure:
                return r[str].from_failure(branch_cleanup)
        return r[str].fail(
            f"worktree setup failed: {setup_error}; clean lane rolled back"
        )

    @staticmethod
    def update_lane(lane: Path, branch: str, base: str) -> p.Result[str]:
        from flext_infra import u

        if not lane.is_dir():
            return r[str].fail(f"worktree lane does not exist: {lane}")
        current_branch = u.Infra.git_symbolic_ref_short(
            m.Infra.GitRepoRequest(repo_root=lane)
        )
        if current_branch.failure:
            return r[str].from_failure(current_branch)
        if current_branch.value.text != branch:
            return r[str].fail(
                f"worktree lane branch mismatch: expected {branch}, "
                f"found {current_branch.value.text}"
            )
        status = u.Infra.git_status(m.Infra.GitStatusRequest(repo_root=lane))
        if status.failure:
            return r[str].from_failure(status)
        if status.value.dirty:
            return r[str].fail(
                "worktree update requires a clean lane; commit the owned WIP "
                "before merge-forward"
            )
        resolved_base = u.Infra.git_resolve_commit(
            m.Infra.GitCommitishRequest(repo_root=lane, commitish=base)
        )
        if resolved_base.failure:
            return r[str].from_failure(resolved_base)
        base_oid = resolved_base.value.oid
        contains_base = u.Infra.git_is_ancestor(
            m.Infra.GitCommitishRequest(repo_root=lane, commitish=base_oid)
        )
        if contains_base.failure:
            return r[str].from_failure(contains_base)
        if contains_base.value.value:
            return r[str].ok(str(lane))
        updated = u.Infra.git_merge_no_edit(
            m.Infra.GitCommitishRequest(repo_root=lane, commitish=base_oid)
        )
        if updated.failure:
            return r[str].from_failure(updated)
        return r[str].ok(str(lane))


__all__: list[str] = ["FlextInfraWorktreeLifecycle"]
