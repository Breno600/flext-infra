"""Hostile coverage for governed gitlink materialization during lane setup.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import FlextInfraWorktreeService, c
from tests import t, u


class TestsFlextInfraWorktreeProvisioningGitlinks:
    """Prove governed gitlink materialization behaves under hostile lane state."""

    @staticmethod
    def _git(root: Path, *arguments: str) -> str:
        return tm.ok(u.Cli.capture([c.Infra.GIT, *arguments], cwd=root)).strip()

    @staticmethod
    def _source(tmp_path: Path, name: str) -> Path:
        source = tmp_path / f"{name}-source"
        source.mkdir()
        (source / "content.txt").write_text(f"{name}\n", encoding="utf-8")
        u.Tests.initialize_git_repo(source)
        return source

    def _lane(
        self,
        tmp_path: Path,
        *,
        managed: bool = True,
    ) -> t.Triple[Path, Path, str]:
        lane = tmp_path / "lane"
        lane.mkdir()
        (lane / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        (lane / "Makefile").write_text(
            f"RUNTIME_VENV := $(CURDIR)/{c.Infra.ENVIRONMENT_DIRECTORY}\n"
            ".PHONY: setup\n"
            "setup:\n"
            "\t@mkdir -p $(RUNTIME_VENV)/bin\n"
            "\t@printf '#!/bin/sh\\n' > $(RUNTIME_VENV)/bin/python\n"
            "\t@chmod +x $(RUNTIME_VENV)/bin/python\n",
            encoding="utf-8",
        )
        (lane / ".gitignore").write_text(
            f"{c.Infra.ENVIRONMENT_DIRECTORY}/\n",
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(lane)
        source = self._source(tmp_path, "member")
        self._git(
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
        self._git(
            lane,
            "config",
            "-f",
            c.Infra.GITMODULES,
            "submodule.member.flext-managed",
            str(managed).lower(),
        )
        self._git(lane, "add", c.Infra.GITMODULES, "member")
        self._git(lane, "commit", "-q", "-m", "declare member")
        recorded = self._git(lane, "rev-parse", "HEAD:member")
        return lane, source, recorded

    def test_absent_governed_gitlink_is_materialized_at_recorded_oid(
        self,
        tmp_path: Path,
    ) -> None:
        """Test absent governed gitlink is materialized at recorded oid."""
        lane, _source_root, recorded = self._lane(tmp_path)
        self._git(lane, "submodule", "deinit", "-q", "-f", "member")

        tm.ok(FlextInfraWorktreeService.setup_lane(lane))

        tm.that(self._git(lane / "member", "rev-parse", "HEAD"), eq=recorded)

    def test_governed_gitlink_head_mismatch_fails_untouched(
        self,
        tmp_path: Path,
    ) -> None:
        """Test governed gitlink head mismatch fails untouched."""
        lane, source, _recorded = self._lane(tmp_path)
        (source / "advanced.txt").write_text("advanced\n", encoding="utf-8")
        self._git(source, "add", "advanced.txt")
        self._git(source, "commit", "-q", "-m", "advance")
        self._git(lane / "member", "fetch", "-q", "origin")
        self._git(lane / "member", "checkout", "-q", "origin/main")
        advanced = self._git(lane / "member", "rev-parse", "HEAD")

        result = FlextInfraWorktreeService.setup_lane(lane)

        tm.fail(result, has=["member", "recorded"])
        tm.that(self._git(lane / "member", "rev-parse", "HEAD"), eq=advanced)

    def test_governed_gitlink_origin_identity_mismatch_fails(
        self,
        tmp_path: Path,
    ) -> None:
        """Test governed gitlink origin identity mismatch fails."""
        lane, _source_root, _recorded = self._lane(tmp_path)
        self._git(
            lane,
            "config",
            "-f",
            c.Infra.GITMODULES,
            "submodule.member.url",
            "https://example.test/other.git",
        )

        tm.fail(FlextInfraWorktreeService.setup_lane(lane), has=["member", "identity"])

    def test_dirty_governed_gitlink_fails_untouched(self, tmp_path: Path) -> None:
        """Test dirty governed gitlink fails untouched."""
        lane, _source_root, _recorded = self._lane(tmp_path)
        marker = lane / "member" / "content.txt"
        marker.write_text("dirty\n", encoding="utf-8")

        tm.fail(FlextInfraWorktreeService.setup_lane(lane), has=["member", "dirty"])

        tm.that(marker.read_text(encoding="utf-8"), eq="dirty\n")

    def test_content_only_gitlink_is_never_materialized(self, tmp_path: Path) -> None:
        """Test content only gitlink is never materialized."""
        lane, _source_root, _recorded = self._lane(tmp_path, managed=False)
        self._git(lane, "submodule", "deinit", "-q", "-f", "member")

        tm.ok(FlextInfraWorktreeService.setup_lane(lane))

        tm.that((lane / "member" / ".git").exists(), eq=False)

    def test_symlinked_git_marker_is_rejected(self, tmp_path: Path) -> None:
        """Test symlinked git marker is rejected."""
        lane, _source_root, _recorded = self._lane(tmp_path)
        marker = lane / "member" / ".git"
        marker.unlink()
        marker.symlink_to(tmp_path / "foreign-git")

        tm.fail(FlextInfraWorktreeService.setup_lane(lane), has=["member", ".git"])
