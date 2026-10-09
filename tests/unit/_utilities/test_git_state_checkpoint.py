"""Durable WIP capture through public Git boundaries and real repositories.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import m
from tests import u


class TestsFlextInfraGitStateCheckpoint:
    """Checkpoints retain original staging while saved candidates evolve."""

    @staticmethod
    def _publish(
        parent: Path,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
    ) -> m.Infra.GitWorktreeCheckpointPublication:
        source = checkpoint.snapshot.repo_root
        remote = parent / "checkpoint-remote.git"
        u.Tests.git_run(source, "init", "--bare", str(remote))
        u.Tests.git_run(source, "remote", "add", "checkpoint-remote", str(remote))
        return tm.ok(
            u.Infra.git_publish_worktree_checkpoint(checkpoint, "checkpoint-remote"),
        )

    @staticmethod
    def _blob_text(root: Path, revision: str) -> str:
        execution = tm.ok(u.Cli.run_raw(["git", "show", revision], cwd=root))
        tm.that(u.Cli.process_succeeded(execution.outcome), eq=True)
        return execution.stdout

    @staticmethod
    def _capture(parent: Path) -> m.Infra.GitWorktreeStateCheckpoint:
        source = u.Tests.git_repository(parent)
        tracked = source / "README.md"
        tracked.write_text("baseline\n", encoding="utf-8")
        u.Tests.git_run(source, "add", "README.md")
        u.Tests.git_run(source, "commit", "-m", "tracked checkpoint baseline")
        tracked.write_bytes(b"staged\n")
        u.Tests.git_run(source, "add", "README.md")
        tracked.write_bytes(b"working\x00\xff")
        tracked.chmod(0o600)
        (source / "added.txt").write_text("staged addition\n", encoding="utf-8")
        u.Tests.git_run(source, "add", "added.txt")
        (source / "untracked").symlink_to("README.md")
        snapshot = tm.ok(
            u.Infra.git_snapshot_worktree_state(
                m.Infra.GitWorktreeStateRequest(
                    repo_root=source,
                    paths=(Path("README.md"), Path("added.txt"), Path("untracked")),
                ),
            ),
        )
        return tm.ok(
            u.Infra.git_checkpoint_worktree_state(
                snapshot,
                "refs/captures/test/original",
            ),
        )

    @staticmethod
    def _lane(
        parent: Path,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
    ) -> Path:
        lane = parent / "lane"
        u.Tests.git_run(
            checkpoint.snapshot.repo_root,
            "worktree",
            "add",
            "--detach",
            str(lane),
        )
        return lane

    def test_capture_reapply_save_cleanup_and_gc(self, tmp_path: Path) -> None:
        checkpoint = self._capture(tmp_path)
        source = checkpoint.snapshot.repo_root
        lane = self._lane(tmp_path, checkpoint)
        (lane / "README.md").chmod(0o640)
        tm.that(
            tm.ok(u.Infra.git_verify_worktree_state(checkpoint.snapshot, lane)),
            eq=False,
        )
        tm.ok(u.Infra.git_apply_worktree_checkpoint(checkpoint, lane))
        tm.that((lane / "README.md").stat().st_mode & 0o777, eq=0o600)
        tm.ok(u.Infra.git_apply_worktree_checkpoint(checkpoint, lane))
        tm.that(
            tm.ok(u.Infra.git_verify_worktree_state(checkpoint.snapshot, lane)),
            eq=True,
        )
        (lane / "README.md").write_text(
            "intentionally evolved candidate\n",
            encoding="utf-8",
        )
        u.Tests.git_run(lane, "add", "README.md", "added.txt", "untracked")
        u.Tests.git_run(lane, "commit", "-m", "save evolved candidate")
        saved = u.Tests.git_capture(lane, "rev-parse", "HEAD").strip()

        publication = self._publish(tmp_path, checkpoint)
        tm.ok(
            u.Infra.git_cleanup_worktree_state(
                checkpoint,
                lane,
                saved,
                publication=publication,
            ),
        )
        tm.ok(
            u.Infra.git_cleanup_worktree_state(
                checkpoint,
                lane,
                saved,
                publication=publication,
            ),
        )
        tm.that(u.Tests.git_capture(source, "status", "--porcelain=v1"), eq="")
        tm.that((source / "README.md").stat().st_mode & 0o777, eq=0o600)
        u.Tests.git_run(source, "reflog", "expire", "--expire=now", "--all")
        u.Tests.git_run(source, "gc", "--prune=now")
        tm.that(
            self._blob_text(source, f"{checkpoint.index_commit}:README.md"),
            eq="staged\n",
        )
        tm.ok(u.Infra.git_verify_worktree_checkpoint_commit(checkpoint, lane, saved))

    def test_checkpoint_rejects_source_change_and_ref_reuse(
        self,
        tmp_path: Path,
    ) -> None:
        checkpoint = self._capture(tmp_path)
        tm.that(
            tm.ok(
                u.Infra.git_checkpoint_worktree_state(
                    checkpoint.snapshot,
                    checkpoint.checkpoint_ref,
                ),
            ),
            eq=checkpoint,
        )
        source = checkpoint.snapshot.repo_root
        (source / "README.md").write_text("new concurrent change\n", encoding="utf-8")

        changed = u.Infra.git_checkpoint_worktree_state(
            checkpoint.snapshot,
            "refs/captures/test/changed",
        )

        tm.that(changed.failure, eq=True)
        snapshot = tm.ok(
            u.Infra.git_snapshot_worktree_state(
                m.Infra.GitWorktreeStateRequest(
                    repo_root=source,
                    paths=checkpoint.snapshot.paths,
                ),
            ),
        )
        conflict = u.Infra.git_checkpoint_worktree_state(
            snapshot,
            checkpoint.checkpoint_ref,
        )
        tm.that(conflict.failure, eq=True)
        tm.that(
            u.Tests.git_capture(
                source,
                "rev-parse",
                checkpoint.checkpoint_ref,
            ).strip(),
            eq=checkpoint.worktree_commit,
        )

    def test_cleanup_rejects_concurrent_source_changes_before_effects(
        self,
        tmp_path: Path,
    ) -> None:
        checkpoint = self._capture(tmp_path)
        source = checkpoint.snapshot.repo_root
        lane = self._lane(tmp_path, checkpoint)
        tm.ok(u.Infra.git_apply_worktree_checkpoint(checkpoint, lane))
        u.Tests.git_run(lane, "add", "README.md", "added.txt", "untracked")
        u.Tests.git_run(lane, "commit", "-m", "saved")
        saved = u.Tests.git_capture(lane, "rev-parse", "HEAD").strip()
        (source / "README.md").write_text("new concurrent change\n", encoding="utf-8")
        before = u.Tests.git_capture(source, "status", "--porcelain=v1")

        publication = self._publish(tmp_path, checkpoint)
        result = u.Infra.git_cleanup_worktree_state(
            checkpoint,
            lane,
            saved,
            publication=publication,
        )

        tm.that(result.failure, eq=True)
        tm.that(u.Tests.git_capture(source, "status", "--porcelain=v1"), eq=before)
        tm.that((source / "README.md").read_text(), eq="new concurrent change\n")
        tm.that((source / "added.txt").exists(), eq=True)

    def test_publish_retains_both_layers_on_remote(self, tmp_path: Path) -> None:
        checkpoint = self._capture(tmp_path)
        source = checkpoint.snapshot.repo_root
        remote = tmp_path / "remote.git"
        u.Tests.git_run(source, "init", "--bare", str(remote))
        u.Tests.git_run(source, "remote", "add", "capture-remote", str(remote))

        tm.ok(u.Infra.git_publish_worktree_checkpoint(checkpoint, "capture-remote"))
        tm.ok(u.Infra.git_publish_worktree_checkpoint(checkpoint, "capture-remote"))

        tm.that(
            u.Tests.git_capture(
                source,
                "ls-remote",
                "--refs",
                "capture-remote",
                checkpoint.checkpoint_ref,
            ).strip(),
            eq=f"{checkpoint.worktree_commit}\t{checkpoint.checkpoint_ref}",
        )
        tm.that(
            self._blob_text(remote, f"{checkpoint.index_commit}:README.md"),
            eq="staged\n",
        )

    @staticmethod
    def test_empty_scope_is_explicit_and_intent_to_add_is_rejected(
        tmp_path: Path,
    ) -> None:
        source = u.Tests.git_repository(tmp_path)
        (source / "pending.txt").write_text("pending\n", encoding="utf-8")
        u.Tests.git_run(source, "add", "--intent-to-add", "pending.txt")
        empty = tm.ok(
            u.Infra.git_snapshot_worktree_state(
                m.Infra.GitWorktreeStateRequest(repo_root=source, paths=()),
            ),
        )
        tm.that(empty.files, eq=())
        tm.that(empty.index_entries, eq=())
        rejected = u.Infra.git_snapshot_worktree_state(
            m.Infra.GitWorktreeStateRequest(
                repo_root=source,
                paths=(Path("pending.txt"),),
            ),
        )
        tm.that(rejected.failure, eq=True)

    @staticmethod
    def _diverge_remote(checkpoint: m.Infra.GitWorktreeStateCheckpoint) -> str:
        """Force-move the published remote ref to an unrelated capture.

        Returns:
            The resulting ``str``.

        """
        source = checkpoint.snapshot.repo_root
        tree = u.Tests.git_capture(
            source,
            "rev-parse",
            f"{checkpoint.worktree_commit}^{{tree}}",
        ).strip()
        divergent = u.Tests.git_capture(
            source,
            "commit-tree",
            tree,
            "-p",
            checkpoint.snapshot.head,
            "-m",
            "unrelated capture",
        ).strip()
        u.Tests.git_run(
            source,
            "push",
            "--force",
            "checkpoint-remote",
            f"{divergent}:{checkpoint.checkpoint_ref}",
        )
        return divergent

    @staticmethod
    def _remote_advertisement(
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
    ) -> str:
        return u.Tests.git_capture(
            checkpoint.snapshot.repo_root,
            "ls-remote",
            "--refs",
            "checkpoint-remote",
            checkpoint.checkpoint_ref,
        ).strip()

    def test_publish_refuses_a_remote_ref_owned_by_another_capture(
        self,
        tmp_path: Path,
    ) -> None:
        """A remote checkpoint ref is never overwritten by a foreign capture."""
        checkpoint = self._capture(tmp_path)
        self._publish(tmp_path, checkpoint)
        divergent = self._diverge_remote(checkpoint)

        republished = u.Infra.git_publish_worktree_checkpoint(
            checkpoint,
            "checkpoint-remote",
        )

        tm.that(republished.failure, eq=True)
        tm.that(
            self._remote_advertisement(checkpoint),
            eq=f"{divergent}\t{checkpoint.checkpoint_ref}",
        )

    def test_verify_fails_once_the_remote_stops_advertising_the_checkpoint(
        self,
        tmp_path: Path,
    ) -> None:
        """A remote ref moved off the checkpoint proves nothing and fails closed."""
        checkpoint = self._capture(tmp_path)
        publication = self._publish(tmp_path, checkpoint)
        self._diverge_remote(checkpoint)

        verified = u.Infra.git_verify_worktree_checkpoint_publication(
            checkpoint,
            publication,
        )

        tm.that(verified.failure, eq=True)
