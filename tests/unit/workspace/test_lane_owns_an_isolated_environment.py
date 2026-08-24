"""Lane provisioning owns a real local environment."""

from __future__ import annotations

from pathlib import Path

import pytest

from flext_infra import FlextInfraWorktreeService, c, config
from flext_tests import tm
from tests import u

_VENV_NAME = config.Infra.tooling.tools.pyright.path_rules.venv_name


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.1.0"\n'
        'description = "Isolated lane fixture"\n',
        encoding="utf-8",
    )
    (repository / "Makefile").write_text(
        "PROJECT_ROOT := $(CURDIR)\n"
        "RUNTIME_ROOT := $(PROJECT_ROOT)\n"
        ".PHONY: setup\n"
        "setup:\n"
        '\t@test "$(RUNTIME_ROOT)" = "$(PROJECT_ROOT)"\n'
        '\t@test -z "$(WORKSPACE)"\n'
        "\t@git -c protocol.file.allow=always submodule update --init\n"
        f"\t@mkdir -p {_VENV_NAME}/bin\n"
        f"\t@printf '#!/bin/sh\\n' > {_VENV_NAME}/bin/python\n"
        f"\t@chmod +x {_VENV_NAME}/bin/python\n"
        '\t@printf "%s|%s|%s|%s\\n" "$(CURDIR)" "$${MAKEFILES-unset}" '
        '"$${GNUMAKEFLAGS-unset}" "$${PYTHONPATH-unset}" >> setup-runs.log\n',
        encoding="utf-8",
    )
    (repository / ".gitignore").write_text(
        f"{_VENV_NAME}\nsetup-runs.log\n", encoding="utf-8"
    )
    u.Tests.initialize_git_repo(repository)
    return repository


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
        )
    )
    tm.ok(
        u.Cli.run_checked(
            [c.Infra.GIT, "commit", "-am", "test: declare member"], cwd=repository
        )
    )


def _lane(repository: Path, branch: str) -> Path:
    return Path(
        tm.ok(
            FlextInfraWorktreeService(
                workspace_root=repository,
                operation=c.Infra.WorktreeOperation.ADD,
                branch=branch,
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
    )


def test_setup_runs_in_lane_and_creates_real_local_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _repository(tmp_path)
    primary_sentinel = repository / _VENV_NAME / "primary-sentinel"
    primary_sentinel.parent.mkdir()
    primary_sentinel.write_text("untouched\n", encoding="utf-8")
    lane = _lane(repository, "feature/isolated-environment")
    monkeypatch.setenv("MAKEFILES", str(tmp_path / "hostile.mk"))
    monkeypatch.setenv("GNUMAKEFLAGS", "--eval=hostile")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "hostile-pythonpath"))

    tm.ok(FlextInfraWorktreeService.setup_lane(lane))

    lane_venv = lane / _VENV_NAME
    assert lane_venv.is_dir()
    assert not lane_venv.is_symlink()
    assert primary_sentinel.read_text(encoding="utf-8") == "untouched\n"
    assert (lane / "setup-runs.log").read_text(encoding="utf-8") == (
        f"{lane.resolve()}|unset|unset|unset\n"
    )


def test_foreign_environment_symlink_is_unlinked_without_following_target(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    lane = _lane(repository, "feature/legacy-link")
    target = tmp_path / "foreign-environment"
    target.mkdir()
    sentinel = target / "sentinel"
    sentinel.write_text("protected\n", encoding="utf-8")
    (lane / _VENV_NAME).symlink_to(target, target_is_directory=True)

    tm.ok(FlextInfraWorktreeService.setup_lane(lane))

    assert sentinel.read_text(encoding="utf-8") == "protected\n"
    assert (lane / _VENV_NAME).is_dir()
    assert not (lane / _VENV_NAME).is_symlink()


def test_setup_initializes_lane_gitlink_without_mutating_primary(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    _declare_child(tmp_path, repository)
    tm.ok(
        u.Cli.run_checked(
            [c.Infra.GIT, "submodule", "deinit", "-f", "member"], cwd=repository
        )
    )
    lane = _lane(repository, "feature/lane-gitlink")

    tm.ok(FlextInfraWorktreeService.setup_lane(lane))

    assert (lane / "member" / ".git").exists()
    assert not (repository / "member" / ".git").exists()


def test_existing_real_lane_environment_is_preserved(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    lane = _lane(repository, "feature/preserve-local")
    sentinel = lane / _VENV_NAME / "sentinel"
    sentinel.parent.mkdir()
    sentinel.write_text("local\n", encoding="utf-8")

    tm.ok(FlextInfraWorktreeService.setup_lane(lane))

    assert sentinel.read_text(encoding="utf-8") == "local\n"


def test_beads_symlink_fails_without_altering_target(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    lane = _lane(repository, "feature/beads-link")
    target = tmp_path / "foreign-ledger"
    target.mkdir(mode=0o755)
    (lane / ".beads").symlink_to(target, target_is_directory=True)

    result = FlextInfraWorktreeService.setup_lane(lane)

    tm.fail(result, has=".beads")
    assert target.stat().st_mode & 0o777 == 0o755


def test_beads_regular_file_fails_through_result(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    lane = _lane(repository, "feature/beads-file")
    (lane / ".beads").write_text("not a directory\n", encoding="utf-8")

    result = FlextInfraWorktreeService.setup_lane(lane)

    tm.fail(result, has=".beads")


def test_add_only_creates_git_lane_without_setup(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    lane = _lane(repository, "feature/git-only")

    assert lane.is_dir()
    assert not (lane / _VENV_NAME).exists()
    assert not (lane / "setup-runs.log").exists()


__all__: tuple[str, ...] = ()
