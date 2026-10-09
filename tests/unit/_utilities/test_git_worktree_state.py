"""Real Git round trips through the public worktree state-copy boundary.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import u


class TestsFlextInfraGitWorktreeState:
    """Preserve both Git layers and reject destructive destination states."""

    @staticmethod
    def _lane(parent: Path, source: Path) -> Path:
        lane = parent / "lane"
        u.Tests.git_run(source, "worktree", "add", "--detach", str(lane))
        return lane

    @staticmethod
    def _assert_layers_match(source: Path, lane: Path) -> None:
        for args in (
            ("status", "--porcelain=v1", "--untracked-files=all"),
            ("diff", "--binary", "HEAD"),
            ("diff", "--cached", "--binary", "HEAD"),
            ("ls-files", "--stage"),
        ):
            tm.that(
                u.Tests.git_capture(lane, *args),
                eq=u.Tests.git_capture(source, *args),
            )

    def test_partial_staging_binary_modes_deletions_and_untracked(
        self,
        tmp_path: Path,
    ) -> None:
        source = u.Tests.git_repository(tmp_path)
        partial = source / "partial.txt"
        partial.write_text("base\n", encoding="utf-8")
        binary = source / "binary.dat"
        binary.write_bytes(b"\x00base\xff")
        deleted = source / "deleted.txt"
        deleted.write_text("base\n", encoding="utf-8")
        recreated = source / "recreated.txt"
        recreated.write_text("base\n", encoding="utf-8")
        u.Tests.git_run(
            source,
            "add",
            "partial.txt",
            "binary.dat",
            "deleted.txt",
            "recreated.txt",
        )
        u.Tests.git_run(source, "commit", "-m", "tracked fixtures")
        lane = self._lane(tmp_path, source)
        partial.write_text("staged\n", encoding="utf-8")
        binary.write_bytes(b"\x00staged\xff")
        deleted.unlink()
        u.Tests.git_run(source, "add", "partial.txt", "binary.dat", "deleted.txt")
        u.Tests.git_run(source, "rm", "recreated.txt")
        recreated.write_text("untracked replacement\n", encoding="utf-8")
        partial.write_text("unstaged without final newline", encoding="utf-8")
        partial.chmod(0o751)
        binary.write_bytes(b"\x00unstaged\xfe")
        binary.chmod(0o600)
        added = source / "added.txt"
        added.write_text("index content\n", encoding="utf-8")
        u.Tests.git_run(source, "add", "added.txt")
        added.unlink()
        untracked = source / "untracked.dat"
        untracked.write_bytes(b"\xff\x00untracked")
        untracked.chmod(untracked.stat().st_mode | 0o111)
        (source / "link").symlink_to("missing-target")
        (source / "directory-link").symlink_to(".", target_is_directory=True)

        tm.ok(u.Infra.git_copy_worktree_state(source, lane))

        self._assert_layers_match(source, lane)
        for path in (partial, binary, recreated, untracked):
            copied = lane / path.name
            tm.that(copied.read_bytes(), eq=path.read_bytes())
            tm.that(copied.stat().st_mode, eq=path.stat().st_mode)
        tm.that((lane / "link").readlink(), eq=(source / "link").readlink())
        tm.that((lane / "directory-link").readlink(), eq=Path())
        tm.that((lane / deleted.name).exists(), eq=False)
        tm.that((lane / added.name).exists(), eq=False)

    def test_exclusions_are_literal_subtrees(self, tmp_path: Path) -> None:
        source = u.Tests.git_repository(tmp_path)
        excluded = source / "[private]"
        excluded.mkdir()
        (excluded / "tracked.txt").write_text("base\n", encoding="utf-8")
        u.Tests.git_run(source, "add", "[private]/tracked.txt")
        u.Tests.git_run(source, "commit", "-m", "excluded fixture")
        lane = self._lane(tmp_path, source)
        (excluded / "tracked.txt").write_text("staged\n", encoding="utf-8")
        u.Tests.git_run(source, "add", "[private]/tracked.txt")
        (excluded / "untracked.txt").write_text("untracked\n", encoding="utf-8")
        (source / "public.txt").write_text("public\n", encoding="utf-8")

        tm.ok(
            u.Infra.git_copy_worktree_state(
                source,
                lane,
                excluded=(Path("[private]"),),
            ),
        )

        tm.that((lane / "[private]/tracked.txt").read_text(), eq="base\n")
        tm.that((lane / "[private]/untracked.txt").exists(), eq=False)
        tm.that((lane / "public.txt").read_text(), eq="public\n")

    def test_dirty_destination_is_rejected_before_any_effect(
        self,
        tmp_path: Path,
    ) -> None:
        source = u.Tests.git_repository(tmp_path)
        lane = self._lane(tmp_path, source)
        (source / "new.txt").write_text("source\n", encoding="utf-8")
        (lane / "owned.txt").write_text("destination\n", encoding="utf-8")
        before = u.Tests.git_capture(lane, "status", "--porcelain=v1")

        result = u.Infra.git_copy_worktree_state(source, lane)

        tm.that(result.failure, eq=True)
        tm.that(u.Tests.git_capture(lane, "status", "--porcelain=v1"), eq=before)
        tm.that((lane / "owned.txt").read_text(), eq="destination\n")
        tm.that((lane / "new.txt").exists(), eq=False)

    @staticmethod
    def test_other_repository_is_rejected(tmp_path: Path) -> None:
        source = u.Tests.git_repository(tmp_path)
        destination = u.Tests.git_repository(tmp_path, "other")
        (source / "new.txt").write_text("source\n", encoding="utf-8")

        result = u.Infra.git_copy_worktree_state(source, destination)

        tm.that(result.failure, eq=True)
        tm.that((destination / "new.txt").exists(), eq=False)

    def test_ignored_destination_collision_is_rejected(self, tmp_path: Path) -> None:
        source = u.Tests.git_repository(tmp_path)
        (source / ".gitignore").write_text("hidden.txt\n", encoding="utf-8")
        u.Tests.git_run(source, "add", ".gitignore")
        u.Tests.git_run(source, "commit", "-m", "ignore fixture")
        lane = self._lane(tmp_path, source)
        (source / "hidden.txt").write_text("source\n", encoding="utf-8")
        u.Tests.git_run(source, "add", "-f", "hidden.txt")
        (lane / "hidden.txt").write_text("destination\n", encoding="utf-8")

        result = u.Infra.git_copy_worktree_state(source, lane)

        tm.that(result.failure, eq=True)
        tm.that((lane / "hidden.txt").read_text(), eq="destination\n")
