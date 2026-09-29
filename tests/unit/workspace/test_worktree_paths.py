"""Worktree path and namespace behavior."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import FlextInfraWorktreeService, c, m
from tests import u


class TestsFlextInfraWorktreePaths(u.Tests.WorktreeFixture):
    """Group cohesive worktree behavior."""

    def test_list_reports_the_primary_worktree(self, tmp_path: Path) -> None:
        """List is read-only and reports Git's canonical registry."""
        repository = self._repository(tmp_path)

        listed = tm.ok(
            FlextInfraWorktreeService(
                repository_root=repository, operation=c.Infra.WorktreeOperation.LIST
            ).execute()
        )

        tm.that(listed, has=f"worktree {repository}")

    def test_add_and_remove_use_the_isolated_lane_path(self, tmp_path: Path) -> None:
        """A valid PEP 621 string survives typed setup in the isolated lane."""
        repository = self._repository(tmp_path)
        branch = "feature/example"
        lane = tm.ok(FlextInfraWorktreeService.canonical_lane_path(repository, branch))

        added = self.add_worktree(repository, branch)

        tm.that(added, eq=str(lane))
        tm.that(lane.is_dir(), where=bool)
        tm.that(not lane.is_relative_to(repository), where=bool)
        tm.that(
            tm.ok(
                u.Infra.git_list_worktrees(m.Infra.GitRepoRequest(repo_root=repository))
            ).text,
            has=f"worktree {lane}",
        )

        removed = tm.ok(
            FlextInfraWorktreeService(
                repository_root=repository,
                operation=c.Infra.WorktreeOperation.REMOVE,
                branch=branch,
                apply_changes=True,
            ).execute()
        )

        tm.that(removed, eq=str(lane))
        tm.that(not lane.exists(), where=bool)

    def test_add_reads_the_lane_instead_of_dirty_primary_metadata(
        self, tmp_path: Path
    ) -> None:
        """Setup never inherits the primary checkout as its workspace owner."""
        repository = self._repository(tmp_path)
        branch = "feature/isolated-metadata"
        lane = tm.ok(FlextInfraWorktreeService.canonical_lane_path(repository, branch))
        (repository / "pyproject.toml").write_text(
            '[dependency-groups]\ndescription = "dirty primary WIP"\n', encoding="utf-8"
        )

        added = self.add_worktree(repository, branch)

        tm.that(added, eq=str(lane))
        tm.that(
            (repository / "pyproject.toml").read_text(encoding="utf-8"),
            eq='[dependency-groups]\ndescription = "dirty primary WIP"\n',
        )
        tm.that(
            (lane / "pyproject.toml").read_text(encoding="utf-8"),
            has='description = "A standard PEP 621 description string"',
        )

    def test_add_escapes_a_dirty_outer_project_ancestor(self, tmp_path: Path) -> None:
        """The lane container sits outside every project uv could discover."""
        outer_project = tmp_path / "outer"
        outer_project.mkdir()
        (outer_project / "pyproject.toml").write_text(
            '[dependency-groups]\ndescription = "dirty outer WIP"\n', encoding="utf-8"
        )
        nested = outer_project / "nested"
        nested.mkdir()
        repository = self._repository(nested)
        branch = "feature/outer-isolation"
        lane = self._lane(repository, outer_project, branch)

        added = self.add_worktree(repository, branch)

        tm.that(added, eq=str(lane))
        tm.that(not lane.is_relative_to(outer_project), where=bool)
        tm.that(
            (outer_project / "pyproject.toml").read_text(encoding="utf-8"),
            eq='[dependency-groups]\ndescription = "dirty outer WIP"\n',
        )

    def test_same_named_repositories_use_distinct_lane_namespaces(
        self, tmp_path: Path
    ) -> None:
        """Repository names never collide inside one outer lane container."""
        outer_project = tmp_path / "outer"
        outer_project.mkdir()
        (outer_project / "pyproject.toml").write_text(
            '[project]\nname = "outer"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        first_parent = outer_project / "first"
        second_parent = outer_project / "second"
        first_parent.mkdir()
        second_parent.mkdir()
        first = self._repository(first_parent)
        second = self._repository(second_parent)
        branch = "feature/same-name"

        first_lane = self._lane(first, outer_project, branch)
        tm.that(
            tm.ok(
                FlextInfraWorktreeService(
                    repository_root=first,
                    operation=c.Infra.WorktreeOperation.ADD,
                    branch=branch,
                    base="HEAD",
                    apply_changes=True,
                ).execute()
            ),
            eq=str(first_lane),
        )
        second_lane = self._lane(second, outer_project, branch)
        tm.that(
            tm.ok(
                FlextInfraWorktreeService(
                    repository_root=second,
                    operation=c.Infra.WorktreeOperation.ADD,
                    branch=branch,
                    base="HEAD",
                    apply_changes=True,
                ).execute()
            ),
            eq=str(second_lane),
        )

        tm.that(first.name, eq=second.name)
        tm.that(first_lane != second_lane, where=bool)
        tm.that(first_lane.parent.parent != second_lane.parent.parent, where=bool)
