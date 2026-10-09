"""Behavior: git_copy_worktree_state preserves the staged/unstaged split.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraGitCopyWorktreeState:
    """The copy keeps the source's index/worktree distinction, never collapsing."""

    @staticmethod
    def test_copy_preserves_staged_and_unstaged_state(tmp_path: Path) -> None:
        source = u.Tests.git_repository(tmp_path, "source")
        (source / "staged.txt").write_text("base\n", encoding="utf-8")
        (source / "unstaged.txt").write_text("base\n", encoding="utf-8")
        u.Tests.git_bootstrap(source, ("add", "-A"))
        u.Tests.git_bootstrap(source, ("commit", "-m", "base"))
        (source / "staged.txt").write_text("staged-change\n", encoding="utf-8")
        u.Tests.git_bootstrap(source, ("add", "staged.txt"))
        (source / "unstaged.txt").write_text("unstaged-change\n", encoding="utf-8")

        # The real use case copies into a linked worktree of the same
        # repository, so the target shares the source baseline (HEAD).
        target = tmp_path / "target"
        u.Tests.git_bootstrap(source, ("worktree", "add", "-b", "target", str(target)))
        tm.ok(u.Infra.git_copy_worktree_state(source, target))

        source_status = u.Tests.git_capture(source, "status", "--porcelain")
        target_status = u.Tests.git_capture(target, "status", "--porcelain")
        tm.that(target_status, eq=source_status)
        tm.that(target_status, has="M  staged.txt")
        tm.that(target_status, has=" M unstaged.txt")
