"""Security contracts for real Git worktree boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraWorktreeService, c, m, p, u
from tests import u as test_u


class TestsFlextInfraWorktreeSecurityBoundaries:
    """Security contracts for real Git worktree boundaries."""

    @staticmethod
    def _repository(tmp_path: Path) -> Path:
        repository = tmp_path / "repository"
        repository.mkdir()
        (repository / "README.md").write_text("fixture\n", encoding="utf-8")
        (repository / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        (repository / "Makefile").write_text(
            ".PHONY: setup\nsetup:\n\t@printf 'setup\\n'\n", encoding="utf-8"
        )
        test_u.Tests.initialize_git_repo(repository)
        return repository

    @staticmethod
    def _add(
        repository: Path, branch: str, base: str = "HEAD", *, epic: Path | None = None
    ) -> p.Result[str]:
        return FlextInfraWorktreeService(
            repository_root=repository,
            operation=c.Infra.WorktreeOperation.ADD,
            branch=branch,
            base=base,
            epic_lane=epic,
            apply_changes=True,
        ).execute()

    @pytest.mark.parametrize("base", ["--help", "-C", "--upload-pack=payload"])
    def test_option_like_base_fails_before_lane_mutation(
        self, tmp_path: Path, base: str
    ) -> None:
        repository = self._repository(tmp_path)

        result = self._add(repository, "feature/option-base", base)

        tm.fail(result, has="invalid base commitish")
        assert (
            len(
                tm.ok(
                    u.Infra.git_list_worktrees(
                        m.Infra.GitRepoRequest(repo_root=repository)
                    )
                ).text.split("worktree ")
            )
            == 2
        )

    def test_unresolved_base_fails_before_lane_mutation(self, tmp_path: Path) -> None:
        repository = self._repository(tmp_path)

        result = self._add(repository, "feature/missing-base", "missing/base")

        tm.fail(result, has="cannot resolve worktree base")
        assert (
            "feature/missing-base"
            not in tm.ok(
                u.Infra.git_list_worktrees(m.Infra.GitRepoRequest(repo_root=repository))
            ).text
        )

    @pytest.mark.parametrize("entry", ["epic", "container"])
    def test_symlinked_epic_topology_fails_closed(
        self, tmp_path: Path, entry: str
    ) -> None:
        repository = self._repository(tmp_path)
        epic = Path(tm.ok(self._add(repository, "feature/secure-epic")))
        outside = tmp_path / "outside"
        outside.mkdir()
        target = epic
        if entry == "container":
            target = epic / c.Infra.WORKTREES_DIRNAME
            target.symlink_to(outside, target_is_directory=True)
        else:
            tm.ok(u.Infra.git_remove_clean_worktree(repository, epic))
            epic.symlink_to(outside, target_is_directory=True)

        try:
            result = self._add(repository, f"feature/{entry}-child", epic=epic)

            tm.fail(result, has="symlink")
            assert list(outside.iterdir()) == []
        finally:
            if epic.is_symlink():
                epic.unlink()

    def test_epic_path_must_match_git_registry(self, tmp_path: Path) -> None:
        repository = self._repository(tmp_path)
        tm.ok(self._add(repository, "feature/registry-epic"))
        alias = tmp_path / "unregistered-epic"
        alias.mkdir()

        result = self._add(repository, "feature/registry-child", epic=alias)

        tm.fail(result, has="registered epic lane")

    def test_same_child_branch_cannot_be_reused_under_another_epic(
        self, tmp_path: Path
    ) -> None:
        repository = self._repository(tmp_path)
        first = Path(tm.ok(self._add(repository, "feature/first-epic")))
        second = Path(tm.ok(self._add(repository, "feature/second-epic")))
        tm.ok(self._add(repository, "feature/shared-child", epic=first))

        result = self._add(repository, "feature/shared-child", epic=second)

        tm.fail(result, has="already registered")
