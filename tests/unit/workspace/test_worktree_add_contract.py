"""Private worktree ADD owner behavior."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import FlextInfraWorktreeService, c, m
from tests import u


class TestsFlextInfraWorktreeAddContract(u.Tests.WorktreeFixture):
    """Group cohesive worktree behavior."""

    def test_invalid_lane_metadata_fails_precisely_and_rolls_back(
        self, tmp_path: Path
    ) -> None:
        """The typed lane ingress rejects a non-string PEP 621 description."""
        repository = self._repository(tmp_path)
        branch = "feature/invalid-metadata"
        lane = self._lane(repository, repository, branch)
        (repository / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "0.1.0"\n'
            'description = ["not", "a", "string"]\n',
            encoding="utf-8",
        )
        self._commit_fixture(repository, "test: invalid project metadata")

        result = FlextInfraWorktreeService(
            repository_root=repository,
            operation=c.Infra.WorktreeOperation.ADD,
            branch=branch,
            base="HEAD",
            apply_changes=True,
        ).execute()

        tm.fail(result, has="description")
        tm.fail(result, has="clean lane rolled back")
        tm.that(not lane.exists(), where=bool)
        tm.that(
            tm.ok(
                u.Infra.git_ref_exists(
                    m.Infra.GitRefRequest(
                        repo_root=repository, reference=f"refs/heads/{branch}"
                    )
                )
            ).value,
            eq=False,
        )

    def test_private_add_does_not_execute_clean_failing_setup(
        self, tmp_path: Path
    ) -> None:
        """Raw ADD leaves setup execution to the public work-start saga."""
        repository = self._repository(tmp_path)
        branch = "feature/clean-setup-failure"
        lane = self._lane(repository, repository, branch)
        (repository / "Makefile").write_text(
            ".PHONY: setup\nsetup:\n\t@printf 'visible setup progress\\n'\n\t@exit 17\n",
            encoding="utf-8",
        )
        self._commit_fixture(repository, "test: clean setup failure")

        result = self.add_worktree(repository, branch)

        tm.that(result, eq=str(lane))
        tm.that(lane.is_dir(), eq=True)

    def test_private_add_does_not_execute_dirty_failing_setup(
        self, tmp_path: Path
    ) -> None:
        """Raw ADD cannot create setup work before saga provisioning."""
        repository = self._repository(tmp_path)
        branch = "feature/dirty-setup-failure"
        lane = self._lane(repository, repository, branch)
        (repository / "Makefile").write_text(
            ".PHONY: setup\n"
            "setup:\n"
            "\t@printf 'visible setup progress\\n'\n"
            "\t@printf 'preserve me\\n' > setup-wip.txt\n"
            "\t@exit 19\n",
            encoding="utf-8",
        )
        self._commit_fixture(repository, "test: dirty setup failure")

        result = self.add_worktree(repository, branch)

        tm.that(result, eq=str(lane))
        tm.that(not (lane / "setup-wip.txt").exists(), where=bool)

    def test_mutation_without_apply_fails_closed(self, tmp_path: Path) -> None:
        """A branch alone never authorizes repository mutation."""
        repository = self._repository(tmp_path)

        result = FlextInfraWorktreeService(
            repository_root=repository,
            operation=c.Infra.WorktreeOperation.ADD,
            branch="feature/no-apply",
            base="HEAD",
        ).execute()

        tm.fail(result, has="requires --apply")

    def test_add_without_base_fails_loud(self, tmp_path: Path) -> None:
        """A mutating caller must explicitly select its integration base."""
        repository = self._repository(tmp_path)

        result = FlextInfraWorktreeService(
            repository_root=repository,
            operation=c.Infra.WorktreeOperation.ADD,
            branch="feature/no-base",
            apply_changes=True,
        ).execute()

        tm.fail(result, has="requires --base")
