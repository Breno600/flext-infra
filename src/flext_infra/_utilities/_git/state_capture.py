"""Public durable checkpoint application and guarded source cleanup.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from git import GitCommandError

from flext_infra import m, p, r
from flext_infra._utilities import FlextInfraUtilitiesGitStateTransitionMixin


class FlextInfraUtilitiesGitStateCaptureMixin(
    FlextInfraUtilitiesGitStateTransitionMixin,
):
    """Use the existing Git-root writer leases and physical file preconditions."""

    @classmethod
    def _state_apply(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        destination_root: Path,
    ) -> None:
        snapshot = checkpoint.snapshot
        if destination_root.resolve() == snapshot.repo_root:
            msg = "capture destination must differ from its original source"
            raise ValueError(msg)
        with cls._state_leases((snapshot.repo_root, destination_root)):
            cls._state_validate_checkpoint(checkpoint)
            baseline = cls._state_preflight_transition(
                snapshot,
                destination_root,
                cleanup=False,
            )
            cls._state_materialize(snapshot, destination_root, baseline, cleanup=False)
            actual = cls._state_snapshot(
                m.Infra.GitWorktreeStateRequest(
                    repo_root=destination_root,
                    paths=snapshot.paths,
                ),
            )
            if (
                actual.index_entries != snapshot.index_entries
                or actual.files != snapshot.files
            ):
                msg = "checkpoint materialization did not preserve both layers"
                raise ValueError(msg)

    @classmethod
    def git_apply_worktree_checkpoint(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        destination_root: Path,
    ) -> p.Result[bool]:
        """Apply only retained bytes, resuming proven partial prior effects.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        try:
            cls._state_apply(checkpoint, destination_root)
        except (GitCommandError, OSError, ValueError) as exc:
            return r[bool].fail(str(exc), exception=exc)
        return r[bool].ok(value=True)

    @classmethod
    def _state_cleanup(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        destination_root: Path,
        saved_commit: str,
        publication: m.Infra.GitWorktreeCheckpointPublication,
    ) -> None:
        snapshot = checkpoint.snapshot
        if destination_root.resolve() == snapshot.repo_root:
            msg = "cleanup requires an independently saved destination"
            raise ValueError(msg)
        with cls._state_leases((snapshot.repo_root, destination_root)):
            cls._state_verify_publication(checkpoint, publication)
            cls._state_verify_saved(checkpoint, destination_root, saved_commit)
            baseline = cls._state_preflight_transition(
                snapshot,
                snapshot.repo_root,
                cleanup=True,
            )
            cls._state_materialize(snapshot, snapshot.repo_root, baseline, cleanup=True)
            observed = cls._state_snapshot(
                m.Infra.GitWorktreeStateRequest(
                    repo_root=snapshot.repo_root,
                    paths=snapshot.paths,
                ),
            )
            files = tuple(
                m.Infra.GitWorktreeIndexEntry(
                    path=file.path,
                    mode=file.mode,
                    oid=file.oid,
                )
                for file in observed.files
            )
            if observed.index_entries != baseline or files != baseline:
                msg = "source cleanup did not restore the captured HEAD scope"
                raise ValueError(msg)

    @classmethod
    def git_cleanup_worktree_state(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        destination_root: Path,
        saved_commit: str,
        *,
        publication: m.Infra.GitWorktreeCheckpointPublication,
    ) -> p.Result[bool]:
        """Restore owned source entries only after live remote retention proof.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        try:
            cls._state_cleanup(checkpoint, destination_root, saved_commit, publication)
        except (GitCommandError, OSError, ValueError) as exc:
            return r[bool].fail(str(exc), exception=exc)
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraUtilitiesGitStateCaptureMixin"]
