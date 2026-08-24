"""Hostile coverage for governed gitlink materialization during lane setup."""

from __future__ import annotations

from pathlib import Path

from flext_infra import FlextInfraWorktreeService, c, config
from flext_tests import tm
from tests import u

_VENV_NAME = config.Infra.tooling.tools.pyright.path_rules.venv_name


def _git(root: Path, *arguments: str) -> str:
    return tm.ok(u.Cli.capture([c.Infra.GIT, *arguments], cwd=root)).strip()


def _source(tmp_path: Path, name: str) -> Path:
    source = tmp_path / f"{name}-source"
    source.mkdir()
    (source / "content.txt").write_text(f"{name}\n", encoding="utf-8")
    u.Tests.initialize_git_repo(source)
    return source


def _lane(tmp_path: Path, *, managed: bool = True) -> tuple[Path, Path, str]:
    lane = tmp_path / "lane"
    lane.mkdir()
    (lane / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (lane / "Makefile").write_text(
        ".PHONY: setup\n"
        "setup:\n"
        f"\t@mkdir -p {_VENV_NAME}/bin\n"
        f"\t@printf '#!/bin/sh\\n' > {_VENV_NAME}/bin/python\n"
        f"\t@chmod +x {_VENV_NAME}/bin/python\n",
        encoding="utf-8",
    )
    u.Tests.initialize_git_repo(lane)
    source = _source(tmp_path, "member")
    _git(
        lane,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        "-b",
        "main",
        str(source),
        "member",
    )
    _git(
        lane,
        "config",
        "-f",
        c.Infra.GITMODULES,
        "submodule.member.flext-managed",
        str(managed).lower(),
    )
    _git(lane, "add", c.Infra.GITMODULES, "member")
    _git(lane, "commit", "-q", "-m", "declare member")
    recorded = _git(lane, "rev-parse", "HEAD:member")
    return lane, source, recorded


def test_absent_governed_gitlink_is_materialized_at_recorded_oid(
    tmp_path: Path,
) -> None:
    lane, _source_root, recorded = _lane(tmp_path)
    _git(lane, "submodule", "deinit", "-q", "-f", "member")

    tm.ok(FlextInfraWorktreeService.setup_lane(lane))

    tm.that(_git(lane / "member", "rev-parse", "HEAD"), eq=recorded)


def test_governed_gitlink_head_mismatch_fails_untouched(tmp_path: Path) -> None:
    lane, source, _recorded = _lane(tmp_path)
    (source / "advanced.txt").write_text("advanced\n", encoding="utf-8")
    _git(source, "add", "advanced.txt")
    _git(source, "commit", "-q", "-m", "advance")
    _git(lane / "member", "fetch", "-q", "origin")
    _git(lane / "member", "checkout", "-q", "origin/main")
    advanced = _git(lane / "member", "rev-parse", "HEAD")

    result = FlextInfraWorktreeService.setup_lane(lane)

    tm.fail(result, has=["member", "recorded"])
    tm.that(_git(lane / "member", "rev-parse", "HEAD"), eq=advanced)


def test_governed_gitlink_origin_identity_mismatch_fails(tmp_path: Path) -> None:
    lane, _source_root, _recorded = _lane(tmp_path)
    _git(
        lane,
        "config",
        "-f",
        c.Infra.GITMODULES,
        "submodule.member.url",
        "https://example.test/other.git",
    )

    tm.fail(FlextInfraWorktreeService.setup_lane(lane), has=["member", "identity"])


def test_dirty_governed_gitlink_fails_untouched(tmp_path: Path) -> None:
    lane, _source_root, _recorded = _lane(tmp_path)
    marker = lane / "member" / "content.txt"
    marker.write_text("dirty\n", encoding="utf-8")

    tm.fail(FlextInfraWorktreeService.setup_lane(lane), has=["member", "dirty"])

    tm.that(marker.read_text(encoding="utf-8"), eq="dirty\n")


def test_content_only_gitlink_is_never_materialized(tmp_path: Path) -> None:
    lane, _source_root, _recorded = _lane(tmp_path, managed=False)
    _git(lane, "submodule", "deinit", "-q", "-f", "member")

    tm.ok(FlextInfraWorktreeService.setup_lane(lane))

    tm.that((lane / "member" / ".git").exists(), eq=False)


def test_symlinked_git_marker_is_rejected(tmp_path: Path) -> None:
    lane, _source_root, _recorded = _lane(tmp_path)
    marker = lane / "member" / ".git"
    marker.unlink()
    marker.symlink_to(tmp_path / "foreign-git")

    tm.fail(FlextInfraWorktreeService.setup_lane(lane), has=["member", ".git"])


__all__: tuple[str, ...] = ()
