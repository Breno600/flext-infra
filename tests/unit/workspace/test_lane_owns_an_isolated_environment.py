"""Lane provisioning gives every linked worktree its own physical environment.

Premise: tracker memory operator-ruling-2026-10-09-worktree-own-venv (operator
choice "Worktree com .venv proprio"): a linked worktree owns an exclusive
physical environment inside the lane and never shares its primary's.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import FlextInfraWorktreeService
from tests import c, u


class TestsFlextInfraLaneOwnsIsolatedEnvironment:
    """Lane provisioning resolves and builds the lane's own environment."""

    @staticmethod
    def _repository(tmp_path: Path) -> Path:
        repository = tmp_path / "repository"
        repository.mkdir()
        (repository / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "0.1.0"\n'
            'description = "Isolated environment lane fixture"\n',
            encoding="utf-8",
        )
        (repository / "Makefile").write_text(
            "PROJECT_ROOT := $(CURDIR)\n"
            "RUNTIME_ROOT := $(PROJECT_ROOT)\n"
            f"RUNTIME_VENV := $(RUNTIME_ROOT)/{c.Infra.ENVIRONMENT_DIRECTORY}\n"
            ".PHONY: setup\n"
            "setup:\n"
            '\t@test "$(RUNTIME_ROOT)" = "$(PROJECT_ROOT)"\n'
            '\t@test -z "$(WORKSPACE)"\n'
            "\t@git -c protocol.file.allow=always submodule update --init\n"
            "\t@mkdir -p $(RUNTIME_VENV)/bin\n"
            "\t@printf '#!/bin/sh\\n' > $(RUNTIME_VENV)/bin/python\n"
            "\t@chmod +x $(RUNTIME_VENV)/bin/python\n"
            '\t@printf "%s|%s|%s|%s\\n" "$(CURDIR)" "$${MAKEFILES-unset}" '
            '"$${GNUMAKEFLAGS-unset}" "$${PYTHONPATH-unset}" >> setup-runs.log\n',
            encoding="utf-8",
        )
        (repository / ".gitignore").write_text(
            f"setup-runs.log\n{c.Infra.ENVIRONMENT_DIRECTORY}/\n",
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(repository)
        return repository

    @staticmethod
    def _declare_child(tmp_path: Path, repository: Path) -> None:
        child = tmp_path / "child"
        child.mkdir()
        (child / "child.txt").write_text("clean\n", encoding="utf-8")
        u.Tests.initialize_git_repo(child)
        tm.ok(
            u.Cli.run_checked(
                [
                    c.Infra.GIT,
                    "-c",
                    "protocol.file.allow=always",
                    "submodule",
                    "add",
                    str(child),
                    "member",
                ],
                cwd=repository,
            ),
        )
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "commit", "-am", "test: declare member"],
                cwd=repository,
            ),
        )

    @staticmethod
    def _lane(repository: Path, branch: str) -> Path:
        # A native Git lane placed outside the primary's directory: the
        # environment contract must hold wherever Git places the lane.
        lane = repository.parent / "lanes" / branch.replace("/", "-")
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "worktree", "add", "-b", branch, str(lane)],
                cwd=repository,
            ),
        )
        return lane.resolve()

    def test_lane_environment_is_inside_the_lane(
        self,
        tmp_path: Path,
    ) -> None:
        """The lane resolves its own .venv, never the primary worktree's."""
        repository = self._repository(tmp_path)
        lane = self._lane(repository, "feature/own-environment")

        tm.that(
            u.Infra.runtime_environment_dir(lane),
            eq=lane.resolve() / c.Infra.ENVIRONMENT_DIRECTORY,
        )
        tm.that(
            u.Infra.runtime_environment_dir(lane),
            ne=u.Infra.runtime_environment_dir(repository),
        )

    def test_setup_runs_in_lane_and_provisions_its_own_environment(
        self,
        tmp_path: Path,
    ) -> None:
        """Setup runs in the lane and provisions the lane's own environment."""
        repository = self._repository(tmp_path)
        lane = self._lane(repository, "feature/lane-setup")
        with tm.scope(
            env={
                "MAKEFILES": str(tmp_path / "hostile.mk"),
                "GNUMAKEFLAGS": "--eval=hostile",
                "PYTHONPATH": str(tmp_path / "hostile-pythonpath"),
            },
        ):
            tm.ok(FlextInfraWorktreeService.setup_lane(lane))

        lane_venv = u.Infra.runtime_environment_dir(lane)
        tm.that(lane_venv.is_dir(), eq=True)
        tm.that(lane_venv.is_symlink(), eq=False)
        tm.that(u.Infra.runtime_environment_dir(repository).exists(), eq=False)
        assert (lane / "setup-runs.log").read_text(encoding="utf-8") == (
            f"{lane.resolve()}|unset|unset|unset\n"
        )

    def test_foreign_environment_symlink_is_rejected_without_following_target(
        self,
        tmp_path: Path,
    ) -> None:
        """A symlinked environment fails setup and its target stays untouched."""
        repository = self._repository(tmp_path)
        lane = self._lane(repository, "feature/legacy-link")
        target = tmp_path / "foreign-environment"
        target.mkdir()
        sentinel = target / "sentinel"
        sentinel.write_text("protected\n", encoding="utf-8")
        lane_venv = u.Infra.runtime_environment_dir(lane)
        lane_venv.symlink_to(target, target_is_directory=True)

        tm.fail(FlextInfraWorktreeService.setup_lane(lane), has="symlink")

        assert sentinel.read_text(encoding="utf-8") == "protected\n"
        assert lane_venv.is_symlink()

    def test_setup_initializes_lane_gitlink_without_mutating_primary(
        self,
        tmp_path: Path,
    ) -> None:
        """Setup initializes the lane gitlink without mutating the primary."""
        repository = self._repository(tmp_path)
        self._declare_child(tmp_path, repository)
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "submodule", "deinit", "-f", "member"],
                cwd=repository,
            ),
        )
        lane = self._lane(repository, "feature/lane-gitlink")

        tm.ok(FlextInfraWorktreeService.setup_lane(lane))

        assert (lane / "member" / ".git").exists()
        assert not (repository / "member" / ".git").exists()

    def test_lane_setup_never_touches_the_primary_environment(
        self,
        tmp_path: Path,
    ) -> None:
        """Lane setup builds the lane environment and leaves the primary's intact."""
        repository = self._repository(tmp_path)
        lane = self._lane(repository, "feature/preserve-primary")
        primary_sentinel = u.Infra.runtime_environment_dir(repository) / "sentinel"
        primary_sentinel.parent.mkdir(parents=True, exist_ok=True)
        primary_sentinel.write_text("primary\n", encoding="utf-8")

        tm.ok(FlextInfraWorktreeService.setup_lane(lane))

        tm.that(primary_sentinel.read_text(encoding="utf-8"), eq="primary\n")
        tm.that(
            (u.Infra.runtime_environment_dir(lane) / "sentinel").exists(),
            eq=False,
        )

    def test_add_only_creates_git_lane_without_setup(self, tmp_path: Path) -> None:
        """Adding a lane creates the Git lane without provisioning anything."""
        repository = self._repository(tmp_path)

        lane = self._lane(repository, "feature/git-only")

        assert lane.is_dir()
        assert not u.Infra.runtime_environment_dir(lane).exists()
        assert not (lane / "setup-runs.log").exists()
