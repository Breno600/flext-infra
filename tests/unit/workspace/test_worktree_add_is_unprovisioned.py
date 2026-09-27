"""Worktree ADD creates a checkout without owning project lane lifecycle."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import FlextInfraWorktreeService, c
from tests import u


class TestsFlextInfraWorktreeAddIsUnprovisioned:
    """ADD materializes a checkout only; it never runs the lane's own setup."""

    def test_worktree_add_does_not_run_setup(self, tmp_path: Path) -> None:
        repository = tmp_path / "repository"
        repository.mkdir()
        (repository / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        marker = "setup-ran"
        (repository / "Makefile").write_text(
            ".PHONY: setup\nsetup:\n\t@touch $(CURDIR)/setup-ran\n", encoding="utf-8"
        )
        u.Tests.initialize_git_repo(repository)

        lane = Path(
            tm.ok(
                FlextInfraWorktreeService(
                    repository_root=repository,
                    operation=c.Infra.WorktreeOperation.ADD,
                    branch="feature/unprovisioned",
                    base="HEAD",
                    apply_changes=True,
                ).execute()
            )
        )

        tm.that(lane.is_dir(), eq=True)
        tm.that((lane / marker).exists(), eq=False)
