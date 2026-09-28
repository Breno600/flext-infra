"""Worktree child containment and removal behavior."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import FlextInfraWorktreeService, c
from tests import u


class TestsFlextInfraWorktreeRemoval(u.Tests.WorktreeFixture):
    """Group cohesive worktree behavior."""

    def test_remove_refuses_an_epic_lane_with_registered_children(
        self, tmp_path: Path
    ) -> None:
        """A registered child keeps its epic lane alive until the child is gone."""
        repository = self._repository(tmp_path)
        epic_branch = "feature/epic-beta"
        epic = Path(self.add_worktree(repository, epic_branch))
        child_branch = "feature/child-two"
        child = Path(
            tm.ok(
                FlextInfraWorktreeService(
                    repository_root=repository,
                    operation=c.Infra.WorktreeOperation.ADD,
                    branch=child_branch,
                    base=epic_branch,
                    epic_lane=epic,
                    apply_changes=True,
                ).execute()
            )
        )

        refused = FlextInfraWorktreeService(
            repository_root=repository,
            operation=c.Infra.WorktreeOperation.REMOVE,
            branch=epic_branch,
            apply_changes=True,
        ).execute()

        tm.fail(refused, has="while children are registered")
        tm.fail(refused, has=str(child))
        tm.that(epic.is_dir(), where=bool)

        tm.that(
            tm.ok(
                FlextInfraWorktreeService(
                    repository_root=repository,
                    operation=c.Infra.WorktreeOperation.REMOVE,
                    branch=child_branch,
                    apply_changes=True,
                ).execute()
            ),
            eq=str(child),
        )
        tm.that(
            tm.ok(
                FlextInfraWorktreeService(
                    repository_root=repository,
                    operation=c.Infra.WorktreeOperation.REMOVE,
                    branch=epic_branch,
                    apply_changes=True,
                ).execute()
            ),
            eq=str(epic),
        )
        tm.that(not epic.exists(), where=bool)

    def test_child_add_refuses_an_unregistered_epic_lane(self, tmp_path: Path) -> None:
        """A child never materializes a container for an epic that does not exist."""
        repository = self._repository(tmp_path)
        missing = tmp_path / "no-such-epic"

        result = FlextInfraWorktreeService(
            repository_root=repository,
            operation=c.Infra.WorktreeOperation.ADD,
            branch="feature/child-orphan",
            base="HEAD",
            epic_lane=missing,
            apply_changes=True,
        ).execute()

        tm.fail(result, has=f"epic lane worktree does not exist: {missing}")
        tm.that(not missing.exists(), where=bool)
