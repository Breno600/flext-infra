"""Public u.Infra Git facet — GitPython-backed behavior."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import FlextInfraGitService, c, m, u
from tests import u as test_u


class TestsFlextInfraGitFacet:
    """Exercise the public Git facade against a real repository worktree."""

    def _add_submodule(self, repository: Path, source: Path, name: str) -> None:
        """Add and commit ``source`` as a file-protocol submodule named ``name``."""
        _ = test_u.Tests.git_run(
            repository,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(source),
            name,
        )
        _ = test_u.Tests.git_run(repository, "commit", "-am", name)

    def _add_lane(self, tmp_path: Path, repository: Path, branch: str) -> Path:
        """Create one branch and check it out as a worktree lane under ``tmp_path``."""
        lane = tmp_path / branch
        _ = test_u.Tests.git_run(repository, "branch", branch)
        _ = test_u.Tests.git_run(repository, "worktree", "add", str(lane), branch)
        return lane

    def _update_submodules(self, lane: Path) -> None:
        """Initialize every declared submodule inside the lane checkout."""
        _ = test_u.Tests.git_run(
            lane,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "update",
            "--init",
            "--recursive",
        )

    def test_tracked_scope_refreshes_after_filesystem_mutation(
        self, tmp_path: Path
    ) -> None:
        """Tracked-scope discovery must not retain a stale dirty-file inventory."""
        repository = test_u.Tests.git_repository(tmp_path)
        scope = repository / "src"
        scope.mkdir()

        tm.that(u.Infra.git_tracked_scope_paths(scope), eq=[])
        created = scope / "created.py"
        created.write_text("VALUE = 1\n", encoding="utf-8")

        tm.that(u.Infra.git_tracked_scope_paths(scope), eq=[created])

    def test_invalid_nested_git_marker_does_not_borrow_parent_index(
        self, tmp_path: Path
    ) -> None:
        """An explicit invalid Git boundary falls back to filesystem discovery."""
        repository = test_u.Tests.git_repository(tmp_path)
        project = repository / "project"
        project.mkdir()
        (project / ".git").mkdir()
        source = project / "src" / "package"
        source.mkdir(parents=True)
        created = source / "module.py"
        created.write_text("VALUE = 1\n", encoding="utf-8")

        tracked = u.Infra.git_tracked_scope_paths(project / "src")

        tm.that(tracked, eq=[created])

    def test_tracked_scope_does_not_borrow_an_ignoring_parent_repository(
        self, tmp_path: Path
    ) -> None:
        """An explicitly selected ignored scope remains excluded by its repository."""
        repository = test_u.Tests.git_repository(tmp_path)
        (repository / ".gitignore").write_text("scratch/\n", encoding="utf-8")
        ignored_scope = repository / "scratch" / "project"
        ignored_scope.mkdir(parents=True)
        (ignored_scope / "README.md").write_text("# Project\n", encoding="utf-8")

        tracked = u.Infra.git_tracked_scope_paths(ignored_scope)

        tm.that(tracked, eq=[])

    def test_merge_no_edit_requires_a_non_fast_forward_merge(
        self, tmp_path: Path
    ) -> None:
        repository = test_u.Tests.git_repository(tmp_path)
        tm.ok(test_u.Cli.run_checked([c.Infra.GIT, "branch", "topic"], cwd=repository))
        tm.ok(test_u.Cli.run_checked([c.Infra.GIT, "switch", "topic"], cwd=repository))
        (repository / "topic.txt").write_text("topic\n", encoding="utf-8")
        tm.ok(test_u.Cli.run_checked([c.Infra.GIT, "add", "topic.txt"], cwd=repository))
        tm.ok(
            test_u.Cli.run_checked(
                [c.Infra.GIT, "commit", "-m", "topic"], cwd=repository
            )
        )
        topic = tm.ok(
            u.Infra.git_repository_head(m.Infra.GitRepoRequest(repo_root=repository))
        ).oid
        tm.ok(test_u.Cli.run_checked([c.Infra.GIT, "switch", "main"], cwd=repository))
        tm.ok(
            u.Infra.git_merge_no_edit(
                m.Infra.GitCommitishRequest(repo_root=repository, commitish=topic)
            )
        )
        parents = tm.ok(
            u.Cli.capture(
                [c.Infra.GIT, "rev-list", "--parents", "-n", "1", "HEAD"],
                cwd=repository,
            )
        ).split()
        assert len(parents) == 3

    def test_repository_head_and_status_and_service(self, real_git_repo: Path) -> None:
        """Head, porcelain status, and FlextInfraGitService share one typed path."""
        head = u.Infra.git_repository_head(
            m.Infra.GitRepoRequest(repo_root=real_git_repo)
        )
        assert head.success
        assert len(head.value.oid) == 40
        status = u.Infra.git_status(m.Infra.GitStatusRequest(repo_root=real_git_repo))
        assert status.success
        assert isinstance(status.value.porcelain, str)
        assert status.value.dirty is False
        primary = u.Infra.git_primary_worktree_root(
            m.Infra.GitRepoRequest(repo_root=real_git_repo)
        )
        assert primary.success
        assert primary.value.primary_root == real_git_repo.resolve()
        report = FlextInfraGitService(repository_root=real_git_repo).execute()
        assert report.success
        assert isinstance(report.value, m.Infra.GitStatusReport)
        assert report.value.repo_root == real_git_repo.resolve()
        assert report.value.dirty is False

    def test_git_init_bare_on_non_repo_cwd(self, tmp_path: Path) -> None:
        """cwd-bound execute must allow git init --bare outside a worktree."""
        bare_root = tmp_path / "bare"
        bare_root.mkdir()
        init_result = u.Cli.run_checked([c.Infra.GIT, "init", "--bare"], cwd=bare_root)
        assert init_result.success
        assert (bare_root / "HEAD").is_file()
        captured = u.Cli.capture([c.Infra.GIT, "rev-parse", "--git-dir"], cwd=bare_root)
        assert captured.success
        assert captured.value.strip() in {".", str(bare_root.resolve())}

    def test_service_status_reports_dirty_tree(self, real_git_repo: Path) -> None:
        """The status-only service flips dirty when the worktree changes."""
        clean = FlextInfraGitService(repository_root=real_git_repo).execute()
        assert clean.success
        assert clean.value.dirty is False
        (real_git_repo / "dirty.txt").write_text("x", encoding="utf-8")
        dirty = FlextInfraGitService(repository_root=real_git_repo).execute()
        assert dirty.success
        assert dirty.value.dirty is True
        assert "dirty.txt" in dirty.value.porcelain

    def test_changed_paths_reports_tracked_and_untracked_files(
        self, real_git_repo: Path
    ) -> None:
        """The public Git facade returns the complete existing worktree delta."""
        readme = real_git_repo / "README.md"
        readme.write_text("changed\n", encoding="utf-8")
        created = real_git_repo / "created.py"
        created.write_text("VALUE = 1\n", encoding="utf-8")

        changed = tm.ok(
            u.Infra.git_changed_paths(m.Infra.GitRepoRequest(repo_root=real_git_repo))
        )

        tm.that(set(changed), eq={readme.resolve(), created.resolve()})

    def test_status_classifies_registered_nested_worktrees_as_administrative(
        self, tmp_path: Path
    ) -> None:
        repository = test_u.Tests.git_repository(tmp_path)
        container = repository / ".worktrees"
        first = container / "first"
        second = container / "second"
        container.mkdir()
        tm.ok(test_u.Cli.run_checked([c.Infra.GIT, "branch", "first"], cwd=repository))
        tm.ok(test_u.Cli.run_checked([c.Infra.GIT, "branch", "second"], cwd=repository))
        tm.ok(
            test_u.Cli.run_checked(
                [c.Infra.GIT, "worktree", "add", str(first), "first"], cwd=repository
            )
        )
        tm.ok(
            test_u.Cli.run_checked(
                [c.Infra.GIT, "worktree", "add", str(second), "second"], cwd=repository
            )
        )
        clean = tm.ok(
            u.Infra.git_status(m.Infra.GitStatusRequest(repo_root=repository))
        )
        assert clean.dirty is False
        (repository / "rogue.txt").write_text("rogue", encoding="utf-8")
        rogue = tm.ok(
            u.Infra.git_status(m.Infra.GitStatusRequest(repo_root=repository))
        )
        assert rogue.dirty is True
        (repository / "rogue.txt").unlink()
        (container / "rogue.txt").write_text("rogue", encoding="utf-8")
        nested_rogue = tm.ok(
            u.Infra.git_status(m.Infra.GitStatusRequest(repo_root=repository))
        )
        assert nested_rogue.dirty is True
        (container / "rogue.txt").unlink()
        (repository / "README.md").write_text("changed", encoding="utf-8")
        tracked = tm.ok(
            u.Infra.git_status(m.Infra.GitStatusRequest(repo_root=repository))
        )
        assert tracked.dirty is True
        (repository / "README.md").write_text("# Test Repository\n", encoding="utf-8")
        tm.ok(
            test_u.Cli.run_checked(
                [c.Infra.GIT, "worktree", "remove", str(second)], cwd=repository
            )
        )
        second.mkdir(parents=True)
        (second / "stale.txt").write_text("stale", encoding="utf-8")
        stale = tm.ok(
            u.Infra.git_status(m.Infra.GitStatusRequest(repo_root=repository))
        )
        assert stale.dirty is True

    def test_missing_git_binary_fails_closed(self, tmp_path: Path) -> None:
        """Missing git on PATH must Result.fail without raising."""
        empty_path = tmp_path / "empty-path"
        empty_path.mkdir()
        with tm.scope(env={"PATH": str(empty_path)}):
            result = u.Infra.git_status(m.Infra.GitStatusRequest(repo_root=tmp_path))
        assert result.failure
        assert result.error is not None
        assert "git executable not found" in result.error

    def test_refresh_binary_reports_the_resolved_executable(self) -> None:
        """The public facet refreshes the Git binary it will then use."""
        refreshed = u.Infra.refresh_binary()
        tm.ok(refreshed)
        tm.that(refreshed.value, eq=True)

    def test_remove_clean_worktree_preserves_primary_submodule_state(
        self, tmp_path: Path
    ) -> None:
        repository = test_u.Tests.git_repository(tmp_path)
        source = test_u.Tests.git_repository(tmp_path, "member-source")
        self._add_submodule(repository, source, "member")
        lane = self._add_lane(tmp_path, repository, "fixture-lane")
        self._update_submodules(lane)
        gitmodules = (repository / ".gitmodules").read_text(encoding="utf-8")
        gitlink = tm.ok(
            u.Cli.capture(
                (c.Infra.GIT, "ls-files", "--stage", "member"), cwd=repository
            )
        )
        configured = tm.ok(
            u.Cli.capture(
                (c.Infra.GIT, "config", "--get", "submodule.member.url"), cwd=repository
            )
        )

        tm.ok(u.Infra.git_remove_clean_worktree(repository, lane))

        assert not lane.exists()
        assert (repository / "member").is_dir()
        assert (repository / ".gitmodules").read_text(encoding="utf-8") == gitmodules
        assert (
            tm.ok(
                u.Cli.capture(
                    (c.Infra.GIT, "ls-files", "--stage", "member"), cwd=repository
                )
            )
            == gitlink
        )
        assert (
            tm.ok(
                u.Cli.capture(
                    (c.Infra.GIT, "config", "--get", "submodule.member.url"),
                    cwd=repository,
                )
            )
            == configured
        )

    def test_remove_clean_worktree_refuses_dirty_nested_submodule(
        self, tmp_path: Path
    ) -> None:
        repository = test_u.Tests.git_repository(tmp_path)
        nested_source = test_u.Tests.git_repository(tmp_path, "nested-source")
        member_source = test_u.Tests.git_repository(tmp_path, "member-source")
        self._add_submodule(member_source, nested_source, "nested")
        self._add_submodule(repository, member_source, "member")
        lane = self._add_lane(tmp_path, repository, "dirty-lane")
        self._update_submodules(lane)
        (lane / "member" / "nested" / "dirty.txt").write_text(
            "dirty\n", encoding="utf-8"
        )

        result = u.Infra.git_remove_clean_worktree(repository, lane)

        tm.fail(result, has="dirty nested submodule")
        assert lane.is_dir()

    def test_remove_clean_worktree_refuses_locked_worktree(
        self, tmp_path: Path
    ) -> None:
        repository = test_u.Tests.git_repository(tmp_path)
        lane = self._add_lane(tmp_path, repository, "locked-lane")
        _ = test_u.Tests.git_run(repository, "worktree", "lock", str(lane))

        result = u.Infra.git_remove_clean_worktree(repository, lane)

        tm.fail(result, has="locked worktree")
        assert lane.is_dir()
