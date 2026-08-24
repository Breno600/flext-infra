"""Worktree ADD creates a checkout and leaves provisioning to the work saga."""

from __future__ import annotations

from pathlib import Path

from flext_infra import FlextInfraWorktreeService, c
from flext_tests import tm
from tests import u


def test_worktree_add_does_not_run_setup(tmp_path: Path) -> None:
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
                workspace_root=repository,
                operation=c.Infra.WorktreeOperation.ADD,
                branch="feature/unprovisioned",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
    )

    tm.that(lane.is_dir(), eq=True)
    tm.that((lane / marker).exists(), eq=False)


__all__: tuple[str, ...] = ()
