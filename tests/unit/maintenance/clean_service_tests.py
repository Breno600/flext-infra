"""Public behavior tests for disposable-artifact cleanup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import FlextInfraCleanService, c

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraCleanService:
    """Validate cleanup through its public service contract."""

    def test_apply_removes_broken_managed_worktree_links(self, tmp_path: Path) -> None:
        """A failed test lane cannot leave a dangling workspace entry."""
        worktrees = tmp_path / c.Infra.WORKTREES_DIRNAME
        worktrees.mkdir()
        broken = worktrees / "broken-lane"
        broken.symlink_to(tmp_path / "missing-lane", target_is_directory=True)

        result = FlextInfraCleanService(
            repository_root=tmp_path, apply_changes=True
        ).execute()

        tm.that(result.success, eq=True)
        tm.that(broken.is_symlink(), eq=False)
