"""Regression coverage for real Git fixture process isolation."""

from __future__ import annotations

from pathlib import Path

import pytest

from flext_infra import u
from flext_tests import tm
from tests import c, u as test_u


def test_initialize_git_repo_ignores_inherited_git_local_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    poison = tmp_path / "poison"
    poison.mkdir()
    tm.ok(u.Cli.run_checked(["git", "init", "-b", "main"], cwd=poison))
    target = tmp_path / "target"
    target.mkdir()
    for key, value in {
        "GIT_DIR": str(poison / ".git"),
        "GIT_WORK_TREE": str(poison),
        "GIT_INDEX_FILE": str(poison / ".git" / "index"),
        "GIT_COMMON_DIR": str(poison / ".git"),
    }.items():
        monkeypatch.setenv(key, value)

    test_u.Tests.initialize_git_repo(target)

    tm.that((target / ".git").is_dir(), eq=True)
    resolved = tm.ok(
        u.Cli.capture(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=target,
            remove_env_keys=c.Tests.GIT_LOCAL_ENV_KEYS,
        )
    )
    tm.that(Path(resolved).resolve(), eq=target.resolve())


__all__: list[str] = []
