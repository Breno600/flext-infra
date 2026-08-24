"""Worktree update and nested-child topology behavior."""

from __future__ import annotations

from pathlib import Path

from flext_infra import FlextInfraWorktreeService, c, m
from flext_tests import tm
from tests import u
from tests.unit.workspace.worktree_fixture import WorktreeFixture


class TestsWorktreeTopology(WorktreeFixture):
    """Group cohesive worktree behavior."""

    def test_update_fast_forwards_a_lane_to_the_requested_base(
        self, tmp_path: Path
    ) -> None:
        """Update advances an existing lane only through a fast-forward."""
        repository = self._repository(tmp_path)
        branch = "feature/update"
        lane = self._lane(repository, repository, branch)
        tm.ok(
            FlextInfraWorktreeService(
                workspace_root=repository,
                operation=c.Infra.WorktreeOperation.ADD,
                branch=branch,
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        (repository / "owner.txt").write_text("owner\n", encoding="utf-8")
        tm.ok(u.Cli.run_checked([c.Infra.GIT, "add", "owner.txt"], cwd=repository))
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "commit", "-m", "test: advance update base"],
                cwd=repository,
            )
        )
        base = tm.ok(
            u.Infra.git_repository_head(m.Infra.GitRepoRequest(repo_root=repository))
        ).oid
        tm.that(
            tm.ok(
                u.Infra.git_primary_worktree_root(
                    m.Infra.GitRepoRequest(repo_root=lane)
                )
            ).primary_root,
            eq=repository.resolve(),
        )

        updated = tm.ok(
            FlextInfraWorktreeService(
                workspace_root=lane,
                operation=c.Infra.WorktreeOperation.UPDATE,
                branch=branch,
                base=base,
                apply_changes=True,
            ).execute()
        )

        tm.that(updated, eq=str(lane))
        updated_head = tm.ok(
            u.Infra.git_repository_head(m.Infra.GitRepoRequest(repo_root=lane))
        ).oid
        tm.that(updated_head, ne=base)
        parents = tm.ok(
            u.Cli.capture(
                [c.Infra.GIT, "rev-list", "--parents", "-n", "1", updated_head],
                cwd=lane,
            )
        ).split()
        tm.that(len(parents), eq=3)

    def test_child_lane_nests_under_its_epic_container(self, tmp_path: Path) -> None:
        """A child lane is namespaced by the epic lane that owns it."""
        repository = self._repository(tmp_path)
        epic_branch = "feature/epic-alpha"
        epic = Path(
            tm.ok(
                FlextInfraWorktreeService(
                    workspace_root=repository,
                    operation=c.Infra.WorktreeOperation.ADD,
                    branch=epic_branch,
                    base="HEAD",
                    apply_changes=True,
                ).execute()
            )
        )
        child_branch = "feature/child-one"

        child = tm.ok(
            FlextInfraWorktreeService(
                workspace_root=repository,
                operation=c.Infra.WorktreeOperation.ADD,
                branch=child_branch,
                base=epic_branch,
                epic_lane=epic,
                apply_changes=True,
            ).execute()
        )

        container = epic / c.Infra.WORKTREES_DIRNAME
        tm.that(child, eq=str(container / "child-one"))
        tm.that(Path(child).is_relative_to(container), where=bool)
        tm.that(
            tm.ok(
                u.Infra.git_list_worktrees(m.Infra.GitRepoRequest(repo_root=repository))
            ).text,
            has=f"worktree {child}",
        )


__all__: tuple[str, ...] = ()
