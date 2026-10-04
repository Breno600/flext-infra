"""Real Git state boundaries for nested repositories and path-kind changes.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
from pathlib import Path

from flext_tests import tm

from flext_infra import m
from tests import u


class TestsFlextInfraGitStateBoundaries:
    """Keep unsupported flags explicit and retain independently owned gitlinks."""

    @staticmethod
    def test_cleanup_rejects_unsupported_baseline_symlink_before_effects(
        tmp_path: Path,
    ) -> None:
        source = u.Tests.git_repository(tmp_path)
        original = source / "shape"
        original.symlink_to(os.fsdecode(b"non-utf8-\xff"))
        u.Tests.git_run(source, "add", "shape")
        u.Tests.git_run(source, "commit", "-m", "baseline raw symlink")
        lane = tmp_path / "lane"
        u.Tests.git_run(source, "worktree", "add", "--detach", str(lane))
        original.unlink()
        original.write_bytes(b"captured regular file")
        snapshot = tm.ok(
            u.Infra.git_snapshot_worktree_state(
                m.Infra.GitWorktreeStateRequest(
                    repo_root=source,
                    paths=(Path("shape"),),
                ),
            ),
        )
        checkpoint = tm.ok(
            u.Infra.git_checkpoint_worktree_state(
                snapshot,
                "refs/captures/raw-symlink",
            ),
        )
        candidate = lane / "shape"
        candidate.unlink()
        candidate.write_bytes(original.read_bytes())
        u.Tests.git_run(lane, "add", "shape")
        u.Tests.git_run(lane, "commit", "-m", "save regular file")
        saved = u.Tests.git_capture(lane, "rev-parse", "HEAD").strip()
        remote = tmp_path / "remote.git"
        u.Tests.git_run(source, "init", "--bare", str(remote))
        u.Tests.git_run(source, "remote", "add", "retained", str(remote))
        publication = tm.ok(
            u.Infra.git_publish_worktree_checkpoint(checkpoint, "retained"),
        )

        result = u.Infra.git_cleanup_worktree_state(
            checkpoint,
            lane,
            saved,
            publication=publication,
        )

        tm.that(result.failure, eq=True)
        tm.that(original.read_bytes(), eq=b"captured regular file")
        tm.that(
            tm.ok(
                u.Infra.git_snapshot_worktree_state(
                    m.Infra.GitWorktreeStateRequest(
                        repo_root=source,
                        paths=snapshot.paths,
                    ),
                ),
            ),
            eq=snapshot,
        )

    @staticmethod
    def test_scope_rejects_unowned_symlink_ancestor(tmp_path: Path) -> None:
        source = u.Tests.git_repository(tmp_path)
        directory = source / "shape"
        directory.mkdir()
        child = directory / "child.txt"
        child.write_text("original child", encoding="utf-8")
        u.Tests.git_run(source, "add", "shape")
        u.Tests.git_run(source, "commit", "-m", "baseline directory")
        child.unlink()
        directory.rmdir()
        directory.symlink_to("README.md")
        for owned in (Path("shape/child.txt"), Path("shape/unknown.txt")):
            request = m.Infra.GitWorktreeStateRequest(repo_root=source, paths=(owned,))
            tm.that(u.Infra.git_snapshot_worktree_state(request).failure, eq=True)
        snapshot = tm.ok(
            u.Infra.git_snapshot_worktree_state(
                m.Infra.GitWorktreeStateRequest(
                    repo_root=source,
                    paths=(Path("shape"),),
                ),
            ),
        )
        tm.that(tuple(file.path for file in snapshot.files), eq=(Path("shape"),))
        tm.that(snapshot.files[0].mode, eq="120000")
        tm.ok(
            u.Infra.git_checkpoint_worktree_state(
                snapshot,
                "refs/captures/symlink-shape",
            ),
        )

    @staticmethod
    def test_index_flags_fail_without_clearing_them(tmp_path: Path) -> None:
        source = u.Tests.git_repository(tmp_path)
        (source / "README.md").write_text("tracked baseline\n", encoding="utf-8")
        u.Tests.git_run(source, "add", "README.md")
        u.Tests.git_run(source, "commit", "-m", "track index flag fixture")
        request = m.Infra.GitWorktreeStateRequest(
            repo_root=source,
            paths=(Path("README.md"),),
        )
        for flag in ("assume-unchanged", "skip-worktree"):
            u.Tests.git_run(source, "update-index", f"--{flag}", "README.md")
            before = u.Tests.git_capture(source, "ls-files", "-v")
            tm.that(u.Infra.git_snapshot_worktree_state(request).failure, eq=True)
            tm.that(u.Tests.git_capture(source, "ls-files", "-v"), eq=before)
            u.Tests.git_run(source, "update-index", f"--no-{flag}", "README.md")

    @staticmethod
    def test_file_directory_roundtrip_preserves_partial_index(
        tmp_path: Path,
    ) -> None:
        source = u.Tests.git_repository(tmp_path)
        path = source / "shape"
        path.write_bytes(b"original file\n")
        u.Tests.git_run(source, "add", "shape")
        u.Tests.git_run(source, "commit", "-m", "baseline shape")
        lane = tmp_path / "lane"
        u.Tests.git_run(source, "worktree", "add", "--detach", str(lane))
        path.unlink()
        path.mkdir()
        (path / "child.bin").write_bytes(b"\x00child\xff")
        snapshot = tm.ok(
            u.Infra.git_snapshot_worktree_state(
                m.Infra.GitWorktreeStateRequest(
                    repo_root=source,
                    paths=(Path("shape"),),
                ),
            ),
        )
        checkpoint = tm.ok(
            u.Infra.git_checkpoint_worktree_state(snapshot, "refs/captures/shape"),
        )

        tm.ok(u.Infra.git_apply_worktree_checkpoint(checkpoint, lane))
        tm.ok(u.Infra.git_apply_worktree_checkpoint(checkpoint, lane))

        tm.that(tm.ok(u.Infra.git_verify_worktree_state(snapshot, lane)), eq=True)
        tm.that(
            (lane / "shape/child.bin").read_bytes(),
            eq=(path / "child.bin").read_bytes(),
        )
        u.Tests.git_run(lane, "add", "shape")
        u.Tests.git_run(lane, "commit", "-m", "save directory shape")
        saved = u.Tests.git_capture(lane, "rev-parse", "HEAD").strip()
        remote = tmp_path / "remote.git"
        u.Tests.git_run(source, "init", "--bare", str(remote))
        u.Tests.git_run(source, "remote", "add", "retained", str(remote))
        publication = tm.ok(
            u.Infra.git_publish_worktree_checkpoint(checkpoint, "retained"),
        )
        tm.ok(
            u.Infra.git_cleanup_worktree_state(
                checkpoint,
                lane,
                saved,
                publication=publication,
            ),
        )
        tm.that(path.read_bytes(), eq=b"original file\n")
        tm.ok(
            u.Infra.git_cleanup_worktree_state(
                checkpoint,
                lane,
                saved,
                publication=publication,
            ),
        )
        tm.that(path.read_bytes(), eq=b"original file\n")
        tm.that(u.Tests.git_capture(source, "status", "--porcelain=v1"), eq="")

    @staticmethod
    def test_gitlink_staging_is_retained_and_unreconciled_child_refuses_apply(
        tmp_path: Path,
    ) -> None:
        source = u.Tests.git_repository(tmp_path)
        child = u.Tests.git_repository(tmp_path, "child-origin")
        u.Tests.git_run(
            source,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(child),
            "member",
        )
        u.Tests.git_run(source, "commit", "-am", "nested baseline")
        lane = tmp_path / "lane"
        u.Tests.git_run(source, "worktree", "add", "--detach", str(lane))
        nested = source / "member"
        u.Tests.configure_git_identity(nested)
        (nested / "README.md").write_text("staged child\n", encoding="utf-8")
        u.Tests.git_run(nested, "add", "README.md")
        u.Tests.git_run(nested, "commit", "-am", "staged child")
        indexed = u.Tests.git_capture(nested, "rev-parse", "HEAD").strip()
        u.Tests.git_run(source, "add", "member")
        (nested / "README.md").write_text("working child\n", encoding="utf-8")
        u.Tests.git_run(nested, "commit", "-am", "working child")
        working = u.Tests.git_capture(nested, "rev-parse", "HEAD").strip()
        snapshot = tm.ok(
            u.Infra.git_snapshot_worktree_state(
                m.Infra.GitWorktreeStateRequest(
                    repo_root=source,
                    paths=(Path("member"),),
                ),
            ),
        )
        checkpoint = tm.ok(
            u.Infra.git_checkpoint_worktree_state(snapshot, "refs/captures/parent"),
        )

        tm.that(snapshot.index_entries[0].oid, eq=indexed)
        tm.that(snapshot.files[0].oid, eq=working)
        tm.that(snapshot.files[0].mode, eq="160000")
        tm.that(
            u.Infra.git_apply_worktree_checkpoint(checkpoint, lane).failure,
            eq=True,
        )
        tm.that(u.Tests.git_capture(lane, "status", "--porcelain=v1"), eq="")
        child_snapshot = tm.ok(
            u.Infra.git_snapshot_worktree_state(
                m.Infra.GitWorktreeStateRequest(
                    repo_root=nested,
                    paths=(),
                    retained_commits=(snapshot.head_entries[0].oid, indexed),
                ),
            ),
        )
        child_checkpoint = tm.ok(
            u.Infra.git_checkpoint_worktree_state(
                child_snapshot,
                "refs/captures/child",
            ),
        )
        reachable = u.Tests.git_capture(
            nested,
            "rev-list",
            child_checkpoint.checkpoint_ref,
        ).splitlines()
        tm.that(indexed in reachable, eq=True)
        tm.that(snapshot.head_entries[0].oid in reachable, eq=True)

    @staticmethod
    def test_remote_drift_refuses_source_cleanup(tmp_path: Path) -> None:
        source = u.Tests.git_repository(tmp_path)
        (source / "README.md").write_text("baseline\n", encoding="utf-8")
        u.Tests.git_run(source, "add", "README.md")
        u.Tests.git_run(source, "commit", "-m", "baseline")
        (source / "README.md").write_text("owned change\n", encoding="utf-8")
        snapshot = tm.ok(
            u.Infra.git_snapshot_worktree_state(
                m.Infra.GitWorktreeStateRequest(
                    repo_root=source,
                    paths=(Path("README.md"),),
                ),
            ),
        )
        checkpoint = tm.ok(
            u.Infra.git_checkpoint_worktree_state(snapshot, "refs/captures/drift"),
        )
        lane = tmp_path / "lane"
        u.Tests.git_run(source, "worktree", "add", "--detach", str(lane))
        tm.ok(u.Infra.git_apply_worktree_checkpoint(checkpoint, lane))
        u.Tests.git_run(lane, "commit", "-am", "saved")
        saved = u.Tests.git_capture(lane, "rev-parse", "HEAD").strip()
        remote = tmp_path / "retained.git"
        u.Tests.git_run(source, "init", "--bare", str(remote))
        u.Tests.git_run(source, "remote", "add", "retained", str(remote))
        publication = tm.ok(
            u.Infra.git_publish_worktree_checkpoint(checkpoint, "retained"),
        )
        u.Tests.git_run(remote, "update-ref", "-d", checkpoint.checkpoint_ref)

        result = u.Infra.git_cleanup_worktree_state(
            checkpoint,
            lane,
            saved,
            publication=publication,
        )

        tm.that(result.failure, eq=True)
        tm.that((source / "README.md").read_text(), eq="owned change\n")
        other = tmp_path / "other.git"
        u.Tests.git_run(source, "init", "--bare", str(other))
        u.Tests.git_run(source, "remote", "set-url", "retained", str(other))
        tm.that(
            u.Infra.git_verify_worktree_checkpoint_publication(
                checkpoint,
                publication,
            ).failure,
            eq=True,
        )
