"""Reachable two-layer checkpoints for operator-authorized WIP capture.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from pathlib import Path

from flext_cli import u
from git import GitCommandError

from flext_infra import c, m, p, r, t
from flext_infra._utilities import (
    FlextInfraUtilitiesCodegenFilePlan,
    FlextInfraUtilitiesGitStateTreesMixin,
    FlextInfraUtilitiesGitWorktreeIO,
)


class FlextInfraUtilitiesGitStateCheckpointMixin(FlextInfraUtilitiesGitStateTreesMixin):
    """Keep index-only and working-byte versions reachable after a save commit."""

    @classmethod
    @contextmanager
    def _state_leases(cls, roots: t.SequenceOf[Path]) -> Generator[None]:
        journals = {
            Path(cls._repo(root).git_dir) / c.Infra.JOURNAL_NAME for root in roots
        }
        with ExitStack() as stack:
            for journal in sorted(journals):
                u.Cli.atomic_read_binary_file_state(
                    journal.with_name(f"{journal.name}.lock"),
                    required=False,
                ).unwrap()
                stack.enter_context(
                    FlextInfraUtilitiesCodegenFilePlan.codegen_transaction_lease(
                        journal,
                    ),
                )
            yield

    @classmethod
    def _state_require_original(
        cls,
        snapshot: m.Infra.GitWorktreeStateSnapshot,
    ) -> None:
        actual = cls._state_snapshot(
            m.Infra.GitWorktreeStateRequest(
                repo_root=snapshot.repo_root,
                paths=snapshot.paths,
                retained_commits=snapshot.retained_commits,
            ),
        )
        if actual != snapshot:
            msg = "source changed since the capture snapshot"
            raise ValueError(msg)

    @classmethod
    def _state_checkpoint(
        cls,
        snapshot: m.Infra.GitWorktreeStateSnapshot,
        checkpoint_ref: str,
    ) -> m.Infra.GitWorktreeStateCheckpoint:

        cls._state_require_original(snapshot)
        repo = cls._repo(snapshot.repo_root)
        if not checkpoint_ref.startswith("refs/") or checkpoint_ref.startswith((
            c.Infra.GIT_REFS_HEADS,
            c.Infra.GIT_REFS_TAGS,
            c.Infra.GIT_REFS_REMOTES,
        )):
            msg = "checkpoint requires a dedicated non-branch Git reference"
            raise ValueError(msg)
        repo.git.check_ref_format(checkpoint_ref)
        existing = repo.git.for_each_ref(
            "--format=%(refname)",
            checkpoint_ref,
        ).splitlines()
        if checkpoint_ref in existing:
            commit = repo.commit(checkpoint_ref)
            match commit.parents:
                case [_, indexed, *_]:
                    checkpoint = m.Infra.GitWorktreeStateCheckpoint(
                        snapshot=snapshot,
                        checkpoint_ref=checkpoint_ref,
                        index_commit=indexed.hexsha,
                        worktree_commit=commit.hexsha,
                    )
                case _:
                    msg = "existing checkpoint has incompatible parent topology"
                    raise ValueError(msg)
            cls._state_validate_checkpoint(checkpoint)
            return checkpoint
        for file in snapshot.files:
            if file.mode == c.Infra.GIT_GITLINK_MODE_TEXT:
                continue
            with FlextInfraUtilitiesGitWorktreeIO.git_stdin(
                cls._state_file_bytes(snapshot.repo_root / file.path),
            ) as stream:
                oid = repo.git.hash_object("-w", "--stdin", istream=stream)
            if oid != file.oid:
                msg = f"source changed while retaining captured bytes: {file.path}"
                raise ValueError(msg)
        index_tree = cls._state_tree(snapshot, snapshot.index_entries)
        worktree_tree = cls._state_tree(snapshot, cls._state_working_entries(snapshot))
        index_commit = repo.git.commit_tree(
            index_tree,
            "-p",
            snapshot.head,
            "-m",
            "Captured index",
        )
        retained_parents = tuple(
            part for oid in snapshot.retained_commits for part in ("-p", oid)
        )
        worktree_commit = repo.git.commit_tree(
            worktree_tree,
            "-p",
            snapshot.head,
            "-p",
            index_commit,
            *retained_parents,
            "-m",
            snapshot.model_dump_json(),
        )
        cls._state_require_original(snapshot)
        repo.git.update_ref("--no-deref", checkpoint_ref, worktree_commit, "")
        checkpoint = m.Infra.GitWorktreeStateCheckpoint(
            snapshot=snapshot,
            checkpoint_ref=checkpoint_ref,
            index_commit=index_commit,
            worktree_commit=worktree_commit,
        )
        cls._state_validate_checkpoint(checkpoint)
        return checkpoint

    @classmethod
    def git_checkpoint_worktree_state(
        cls,
        snapshot: m.Infra.GitWorktreeStateSnapshot,
        checkpoint_ref: str,
    ) -> p.Result[m.Infra.GitWorktreeStateCheckpoint]:
        """Create a dedicated checkpoint, or verify an identical prior receipt.

        Returns:
            The resulting ``p.Result[m.Infra.GitWorktreeStateCheckpoint]``.

        """
        try:
            checkpoint = cls._state_checkpoint(snapshot, checkpoint_ref)
        except (GitCommandError, OSError, ValueError) as exc:
            return r[m.Infra.GitWorktreeStateCheckpoint].fail(str(exc), exception=exc)
        return r[m.Infra.GitWorktreeStateCheckpoint].ok(checkpoint)

    @classmethod
    def _state_verify_saved(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        destination_root: Path,
        saved_commit: str,
    ) -> None:
        cls._state_validate_checkpoint(checkpoint)
        repo = cls._repo(destination_root)
        snapshot = checkpoint.snapshot
        if (
            Path(repo.common_dir).resolve() != snapshot.common_dir
            or repo.head.commit.hexsha != saved_commit
        ):
            msg = "save commit or destination repository identity does not match"
            raise ValueError(msg)
        if not repo.is_ancestor(repo.commit(snapshot.head), repo.commit(saved_commit)):
            msg = "save commit is not descended from the captured HEAD"
            raise ValueError(msg)
        if snapshot.paths and repo.git.status(
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *cls._state_pathspecs(snapshot.paths),
        ):
            msg = "destination still has unsaved changes in the captured scope"
            raise ValueError(msg)

    @classmethod
    def git_verify_worktree_checkpoint_commit(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        destination_root: Path,
        saved_commit: str,
    ) -> p.Result[bool]:
        """Verify original retention and an independently saved descendant.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        try:
            cls._state_verify_saved(checkpoint, destination_root, saved_commit)
        except (GitCommandError, OSError, ValueError) as exc:
            return r[bool].fail(str(exc), exception=exc)
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraUtilitiesGitStateCheckpointMixin"]
