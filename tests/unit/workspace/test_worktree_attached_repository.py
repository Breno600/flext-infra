"""Attached-repository worktree topology behavior."""

from pathlib import Path

from flext_infra import FlextInfraWorktreeService, c, m
from flext_tests import tm
from tests import u
from tests.unit.workspace.worktree_fixture import WorktreeFixture


class TestsAttachedRepositoryWorktree(WorktreeFixture):
    """Exercise Git's primary registry for an attached repository."""

    def test_attached_submodule_uses_one_primary_local_container(
        self, tmp_path: Path
    ) -> None:
        child_source = tmp_path / "child-source"
        child_source.mkdir()
        (child_source / "README.md").write_text("child\n", encoding="utf-8")
        (child_source / "pyproject.toml").write_text(
            '[project]\nname = "child"\nversion = "0.1.0"\n'
            'description = "Attached child fixture"\n',
            encoding="utf-8",
        )
        (child_source / "Makefile").write_text(
            ".PHONY: setup\nsetup:\n"
            '\t@test "$(WORKSPACE)" = "$(CURDIR)"\n'
            '\t@printf "setting up %s\\n" "$(WORKSPACE)"\n',
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(child_source)
        super_root = tmp_path / "super"
        super_root.mkdir()
        superproject = self._repository(super_root)
        tm.ok(
            u.Cli.run_checked(
                [
                    c.Infra.GIT,
                    "-c",
                    "protocol.file.allow=always",
                    "submodule",
                    "add",
                    str(child_source),
                    "attached",
                ],
                cwd=superproject,
            )
        )
        attached = superproject / "attached"
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "config", "--unset", "core.worktree"], cwd=attached
            )
        )
        tm.that(
            tm.ok(
                u.Infra.git_primary_worktree_root(
                    m.Infra.GitRepoRequest(repo_root=attached)
                )
            ).primary_root,
            eq=attached.resolve(),
        )
        linked = tmp_path / "attached-linked"
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "worktree", "add", "--detach", str(linked), "HEAD"],
                cwd=attached,
            )
        )
        tm.that(
            tm.ok(
                u.Infra.git_primary_worktree_root(
                    m.Infra.GitRepoRequest(repo_root=linked)
                )
            ).primary_root,
            eq=linked.resolve(),
        )
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "worktree", "remove", "--force", str(linked)], cwd=linked
            )
        )
        branch = "feature/attached"
        primary = tm.ok(
            u.Infra.git_primary_worktree_root(
                m.Infra.GitRepoRequest(repo_root=attached)
            )
        ).primary_root
        expected_lane = self._lane(primary, superproject, branch)

        lane = tm.ok(
            FlextInfraWorktreeService(
                workspace_root=attached,
                operation=c.Infra.WorktreeOperation.ADD,
                branch=branch,
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.that(lane, eq=str(expected_lane))
        tm.that(
            f"{c.Infra.WORKTREES_DIRNAME}/{c.Infra.WORKTREES_DIRNAME}"
            not in expected_lane.as_posix(),
            where=bool,
        )
        tm.that(
            tm.ok(
                FlextInfraWorktreeService(
                    workspace_root=attached,
                    operation=c.Infra.WorktreeOperation.REMOVE,
                    branch=branch,
                    apply_changes=True,
                ).execute()
            ),
            eq=str(expected_lane),
        )


__all__: tuple[str, ...] = ()
