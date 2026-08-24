"""Invest-shaped external consumer lane provisioning regression."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from flext_infra import FlextInfraWorkService, FlextInfraWorktreeService, c, config
from flext_tests import tm
from tests import u
from tests.unit.workspace.test_work_start_provisions_every_lane import (
    _install_bd_shim,
    _metadata,
)

_VENV_NAME = config.Infra.tooling.tools.pyright.path_rules.venv_name


def _submodule_source(tmp_path: Path, name: str) -> Path:
    source = tmp_path / f"{name}-source"
    source.mkdir()
    (source / "content.txt").write_text(f"{name}\n", encoding="utf-8")
    u.Tests.initialize_git_repo(source)
    return source


def _external_consumer(tmp_path: Path) -> Path:
    primary = tmp_path / "invest"
    primary.mkdir()
    sibling = tmp_path / "flext"
    sibling.mkdir()
    for dependency in ("flext-core", "flext-cli", "flext-infra"):
        dependency_root = sibling / dependency
        dependency_root.mkdir()
        (dependency_root / "contract.txt").write_text(
            f"{dependency}\n", encoding="utf-8"
        )
    (primary / "pyproject.toml").write_text(
        '[project]\nname = "invest"\nversion = "0.1.0"\n'
        'description = "External consumer fixture"\n'
        "[tool.uv.sources]\n"
        'flext-core = { path = "../flext/flext-core" }\n'
        'flext-cli = { path = "../flext/flext-cli" }\n'
        'flext-infra = { path = "../flext/flext-infra" }\n',
        encoding="utf-8",
    )
    (primary / "Makefile").write_text(
        ".PHONY: setup\n"
        "setup:\n"
        '\t@test -z "$(WORKSPACE)"\n'
        '\t@test -z "$(VIRTUAL_ENV)$(UV_PROJECT)$(UV_PROJECT_ENVIRONMENT)"\n'
        f"\t@mkdir -p {_VENV_NAME}/bin\n"
        f"\t@printf '#!/bin/sh\\n' > {_VENV_NAME}/bin/python\n"
        f"\t@chmod +x {_VENV_NAME}/bin/python\n"
        '\t@printf "%s\\n" "$(CURDIR)" > setup-owner.log\n',
        encoding="utf-8",
    )
    (primary / ".gitignore").write_text(
        f"{_VENV_NAME}\nsetup-owner.log\n", encoding="utf-8"
    )
    u.Tests.declare_workspace_ledger(primary, "mro")
    u.Tests.initialize_git_repo(primary)
    submodules = (("mt5linux", "master"), ("vectorbt.pro", "main"))
    for name, branch in submodules:
        source = _submodule_source(tmp_path, name)
        tm.ok(
            u.Cli.run_checked(
                [
                    c.Infra.GIT,
                    "-c",
                    "protocol.file.allow=always",
                    "submodule",
                    "add",
                    str(source),
                    name,
                ],
                cwd=primary,
            )
        )
        tm.ok(
            u.Cli.run_checked(
                [
                    c.Infra.GIT,
                    "config",
                    "-f",
                    c.Infra.GITMODULES,
                    f"submodule.{name}.branch",
                    branch,
                ],
                cwd=primary,
            )
        )
    tm.ok(
        u.Cli.run_checked(
            [c.Infra.GIT, "commit", "-am", "declare gitlinks"], cwd=primary
        )
    )
    for name, _branch in submodules:
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "submodule", "deinit", "-f", name], cwd=primary
            )
        )
    return primary


def test_start_adopts_and_provisions_an_invest_shaped_lane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    primary = _external_consumer(tmp_path)
    bead_id = "mro-test-invest-topology"
    shim_dir = _install_bd_shim(tmp_path, bead_id)
    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "foreign-environment"))
    monkeypatch.setenv("UV_PROJECT", str(tmp_path / "foreign-project"))
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", str(tmp_path / "foreign-uv-env"))
    branch = "bugfix/external-consumer"
    lane = Path(
        tm.ok(
            FlextInfraWorktreeService(
                workspace_root=primary,
                operation=c.Infra.WorktreeOperation.ADD,
                branch=branch,
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
    )
    assert _metadata(tmp_path) == {}

    started = tm.ok(
        FlextInfraWorkService(
            workspace_root=primary,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            kind=c.Infra.WorkKind.BUGFIX,
            name="external-consumer",
            base="HEAD",
            apply_changes=True,
        ).execute()
    )

    metadata = _metadata(tmp_path)
    tm.that(started, has=f"receipt.worktree={lane}")
    tm.that(metadata["worktree"], eq=str(lane))
    tm.that(
        (lane / "setup-owner.log").read_text(encoding="utf-8"), eq=f"{lane.resolve()}\n"
    )
    tm.that((lane / _VENV_NAME).is_symlink(), eq=False)
    for name in ("mt5linux", "vectorbt.pro"):
        tm.that((primary / name / ".git").exists(), eq=False)


__all__: tuple[str, ...] = ()
