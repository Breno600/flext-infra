from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraUtilitiesSafety:
    def _run_git(self, repo: Path, *args: str) -> None:
        result = u.Cli.run_raw([c.Infra.GIT, *args], cwd=repo)
        tm.ok(result)
        tm.that(u.Cli.process_succeeded(result.value.outcome), eq=True)

    def _init_git_repo(self, repo: Path) -> None:
        self._run_git(repo, "init")
        self._run_git(repo, "config", "user.email", "tests@flext.local")
        self._run_git(repo, "config", "user.name", "Flext Tests")
        (repo / "README.md").write_text("# test repo\n", encoding="utf-8")
        self._run_git(repo, "add", "README.md")
        self._run_git(repo, "commit", "-m", "initial commit")

    def test_create_checkpoint_returns_empty_for_clean_repo(
        self, tmp_path: Path
    ) -> None:
        self._init_git_repo(tmp_path)

        result = u.Infra.create_checkpoint(tmp_path)

        tm.ok(result)
        tm.that(result.value, eq="")

    def test_create_checkpoint_fails_for_dirty_repo(self, tmp_path: Path) -> None:
        self._init_git_repo(tmp_path)
        (tmp_path / "notes.txt").write_text("dirty\n", encoding="utf-8")

        result = u.Infra.create_checkpoint(tmp_path, label="test-checkpoint")

        tm.fail(result)
        tm.that((result.error or ""), has="dirty git worktree")

    def test_create_checkpoint_returns_empty_for_non_git_folder(
        self, tmp_path: Path
    ) -> None:
        result = u.Infra.create_checkpoint(tmp_path)

        tm.ok(result)
        tm.that(result.value, eq="")

    def test_rollback_to_checkpoint_rejects_repository_checkpoint(
        self, tmp_path: Path
    ) -> None:
        self._init_git_repo(tmp_path)

        result = u.Infra.rollback_to_checkpoint(tmp_path, "checkpoint-ref")

        tm.fail(result)
        tm.that(
            (result.error or ""),
            has="repository-wide checkpoint rollback is unsupported",
        )

    def test_rollback_to_checkpoint_succeeds_for_non_repo(self, tmp_path: Path) -> None:
        result = u.Infra.rollback_to_checkpoint(tmp_path, "checkpoint-ref")

        tm.ok(result)
        tm.that(result.value, eq=True)
