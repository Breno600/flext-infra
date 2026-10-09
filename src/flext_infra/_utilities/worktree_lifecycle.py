"""Worktree lifecycle module.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import m, r
from flext_infra._utilities import (
    FlextInfraUtilitiesGitSemanticPublishMixin,
    FlextInfraUtilitiesGitSemanticRefsMixin,
    FlextInfraUtilitiesGitWorktreeRemovalMixin,
    FlextInfraUtilitiesGitWorktreeStatusMixin,
)

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

        status = FlextInfraUtilitiesGitWorktreeStatusMixin.git_status(
            m.Infra.GitStatusRequest(repo_root=lane),
        )
        if status.failure:
            return r[str].from_failure(status)
        if status.value.dirty:
            return r[str].fail(
                f"worktree setup failed: {setup_error}; preserving lane {lane} "
                "because setup left worktree changes",
            )
        cleanup = FlextInfraUtilitiesGitWorktreeRemovalMixin.git_remove_clean_worktree(
            primary_root,
            lane,
        )
        if cleanup.failure:
            return r[str].from_failure(cleanup)
        if created_branch_oid is not None:
            branch_cleanup = FlextInfraUtilitiesGitSemanticPublishMixin.git_delete_ref(
                m.Infra.GitDeleteRefRequest(
                    repo_root=primary_root,
                    reference=f"refs/heads/{branch}",
                    expected_oid=created_branch_oid,
                ),
            )
            if branch_cleanup.failure:
                return r[str].from_failure(branch_cleanup)
        return r[str].fail(
            f"worktree setup failed: {setup_error}; clean lane rolled back",
        )

    @staticmethod
    def update_lane(lane: Path, branch: str, base: str) -> p.Result[str]:
        """Fast-forward one clean worktree lane to its base branch.

        Returns:
            The resulting ``p.Result[str]``.

        """
        preflight = FlextInfraWorktreeLifecycle._validated_lane(
            lane,
            branch,
        )
        if preflight.failure:
            return r[str].from_failure(preflight)
        resolved_base = FlextInfraUtilitiesGitSemanticRefsMixin.git_resolve_commit(
            m.Infra.GitCommitishRequest(repo_root=lane, commitish=base),
        )
        if resolved_base.failure:
            return r[str].from_failure(resolved_base)
        return FlextInfraWorktreeLifecycle._merged_lane(
            lane,
            resolved_base.value.oid,
        )

    @staticmethod
    def _validated_lane(lane: Path, branch: str) -> p.Result[bool]:
        """Require one existing lane on its expected branch with clean status.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if not lane.is_dir():
            return r[bool].fail(f"worktree lane does not exist: {lane}")
        refs = FlextInfraUtilitiesGitSemanticRefsMixin
        current_branch = refs.git_current_branch(
            m.Infra.GitRepoRequest(repo_root=lane),
        )
        if current_branch.failure:
            return r[bool].from_failure(current_branch)
        if current_branch.value.text != branch:
            return r[bool].fail(
                f"worktree lane branch mismatch: expected {branch}, "
                f"found {current_branch.value.text}",
            )
        status = FlextInfraUtilitiesGitWorktreeStatusMixin.git_status(
            m.Infra.GitStatusRequest(repo_root=lane),
        )
        if status.failure:
            return r[bool].from_failure(status)
        if status.value.dirty:
            return r[bool].fail(
                "worktree update requires a clean lane; commit the owned WIP "
                "before merge-forward",
            )
        return r[bool].ok(value=True)

    @staticmethod
    def _merged_lane(lane: Path, base_oid: str) -> p.Result[str]:
        """Merge the lane to its base when the base is not already contained.

        Returns:
            The resulting ``p.Result[str]``.

        """
        contains_base = FlextInfraUtilitiesGitSemanticRefsMixin.git_is_ancestor(
            m.Infra.GitAncestryRequest(repo_root=lane, ancestor=base_oid),
        )
        if contains_base.failure:
            return r[str].from_failure(contains_base)
        if contains_base.value.value:
            return r[str].ok(str(lane))
        updated = FlextInfraUtilitiesGitSemanticPublishMixin.git_merge_no_edit(
            m.Infra.GitCommitishRequest(repo_root=lane, commitish=base_oid),
        )
        if updated.failure:
            return r[str].from_failure(updated)
        return r[str].ok(str(lane))


__all__: list[str] = ["FlextInfraWorktreeLifecycle"]
