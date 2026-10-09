"""Test extra paths sync behavior.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from flext_tests import tf, tm

from flext_infra import main, t
from flext_infra.deps.extra_paths import FlextInfraExtraPathsManager
from tests import u

_TEST_REPOSITORY_ROOT = Path(__file__).resolve().parent


@dataclasses.dataclass(frozen=True)
class SyncScenario:
    """One parametrized extra-paths sync scenario bundle."""

    mode: str
    dry_run: bool = False
    project_dirs: t.StrSequence | None = None
    expect_fail: bool = False
    expect_has: str | None = None


@dataclasses.dataclass(frozen=True)
class SyncOneEdgeScenario:
    """One parametrized ``sync_one`` edge-case bundle."""

    mode: str
    dry_run: bool = False
    expected_ok: bool = False
    expect_fail: bool = False


class TestsFlextInfraDepsExtraPathsSync:
    """Behavior contract for test_extra_paths_sync."""

    @staticmethod
    @pytest.fixture
    def pyright_content() -> str:
        """Provide minimal Pyright configuration content.

        Returns:
            The resulting ``str``.

        """
        return "[tool.pyright]\nextraPaths = []\n"

    @staticmethod
    def _create_pyproject(directory: Path, content: str) -> Path:
        pyproject_path: Path = tf(base_dir=directory).create(
            content=content,
            name="pyproject.toml",
        )
        return pyproject_path

    @staticmethod
    def _manager(
        repository_root: Path | None = None,
    ) -> FlextInfraExtraPathsManager:
        return FlextInfraExtraPathsManager(
            repository_root=repository_root or _TEST_REPOSITORY_ROOT,
        )

    @pytest.mark.parametrize(
        "scenario",
        [
            SyncScenario("project", project_dirs=["proj"]),
            SyncScenario(
                "project",
                dry_run=True,
                project_dirs=["proj"],
                expect_has="old",
            ),
            SyncScenario("root"),
            SyncScenario("none", dry_run=True, project_dirs=[]),
            SyncScenario("none", dry_run=True),
        ],
    )
    def test_sync_extra_paths_success_modes(
        self,
        tmp_path: Path,
        pyright_content: str,
        scenario: SyncScenario,
    ) -> None:
        """Verify sync extra paths success modes."""
        project_dirs_arg: t.SequenceOf[Path] | None = None
        if scenario.mode == "project":
            project = tmp_path / "proj"
            project.mkdir()
            content = (
                "[tool.pyright]\nextraPaths = ['old']\n"
                if scenario.dry_run
                else pyright_content
            )
            pyproject = self._create_pyproject(project, content)
            project_dirs_arg = [project] if scenario.project_dirs else []
            result = self._manager(tmp_path).sync_extra_paths(
                dry_run=scenario.dry_run,
                project_dirs=project_dirs_arg,
            )
            tm.ok(result)
            if scenario.expect_has:
                tm.that(pyproject.read_text(encoding="utf-8"), has=scenario.expect_has)
            return
        if scenario.mode == "root":
            _ = self._create_pyproject(tmp_path, pyright_content)
            tm.ok(self._manager(tmp_path).sync_extra_paths())
            return
        _ = self._create_pyproject(tmp_path, pyright_content)
        result = self._manager(tmp_path).sync_extra_paths(
            dry_run=scenario.dry_run,
            project_dirs=[] if scenario.project_dirs == [] else None,
        )
        if scenario.expect_fail:
            tm.fail(result)
            return
        tm.ok(result)

    def test_sync_extra_paths_missing_root_pyproject(self, tmp_path: Path) -> None:
        """Verify sync extra paths missing root pyproject."""
        tm.fail(self._manager(tmp_path).sync_extra_paths(), has="Missing")

    def test_sync_extra_paths_skips_selected_dirs_without_pyproject(
        self,
        tmp_path: Path,
    ) -> None:
        """Selected dirs without pyproject are skipped (worktree-safe), not failed."""
        project = tmp_path / "proj"
        project.mkdir()
        result = self._manager(tmp_path).sync_extra_paths(project_dirs=[project])
        tm.ok(result)
        tm.that(result.value, eq=0)

    @pytest.mark.parametrize(
        ("mode", "argv", "expected_exit"),
        [
            ("root", ["extra_paths.py"], 0),
            ("root", ["extra_paths.py", "--dry-run"], 0),
            ("project", ["extra_paths.py", "--projects", "proj"], 0),
            ("multi", ["extra_paths.py", "--projects", "proj-a,proj-b"], 0),
            ("abs-project", ["prog", "--projects", "project", "--dry-run"], 0),
        ],
    )
    def test_main_success_modes(
        self,
        tmp_path: Path,
        pyright_content: str,
        mode: str,
        argv: t.StrSequence,
        expected_exit: int,
    ) -> None:
        """Verify main success modes."""
        if mode == "root":
            _ = self._create_pyproject(tmp_path, pyright_content)
        if mode == "project":
            project = tmp_path / "proj"
            project.mkdir()
            _ = self._create_pyproject(project, pyright_content)
        if mode == "multi":
            for name in ["proj-a", "proj-b"]:
                project = tmp_path / name
                project.mkdir()
                _ = self._create_pyproject(project, pyright_content)
        if mode == "abs-project":
            project = tmp_path / "project"
            project.mkdir()
            _ = self._create_pyproject(project, pyright_content)
            argv = ["prog", "--projects", str(project), "--dry-run"]
        u.Tests.initialize_git_repo(tmp_path)
        argv = [argv[0], "--repository-root", str(tmp_path), *argv[1:]]
        tm.that(main(["deps", "extra-paths", *argv[1:]]), eq=expected_exit)

    @pytest.mark.parametrize(
        "scenario",
        [
            SyncOneEdgeScenario("nonexistent", dry_run=True),
            SyncOneEdgeScenario("invalid", dry_run=True, expect_fail=True),
            SyncOneEdgeScenario("stubbed"),
        ],
    )
    def test_sync_one_edge_cases(
        self,
        tmp_path: Path,
        pyright_content: str,
        scenario: SyncOneEdgeScenario,
    ) -> None:
        """Verify sync one edge cases."""
        if scenario.mode == "nonexistent":
            tm.that(
                not self
                ._manager(tmp_path)
                .sync_one(Path("/nonexistent/pyproject.toml"), dry_run=scenario.dry_run)
                .success,
                eq=True,
            )
            return
        if scenario.mode == "invalid":
            pyproject = self._create_pyproject(tmp_path, "invalid toml {")
            result = self._manager(tmp_path).sync_one(
                pyproject,
                dry_run=scenario.dry_run,
            )
            if scenario.expect_fail:
                tm.fail(result)
                return
            tm.that(result.success, eq=scenario.expected_ok)
            return
        pyproject = self._create_pyproject(tmp_path, pyright_content)
        tm.ok(
            self._manager(tmp_path).sync_one(
                pyproject,
                is_root=True,
                dry_run=scenario.dry_run,
            ),
        )

    def test_sync_doc_is_idempotent_when_paths_already_match(
        self,
        tmp_path: Path,
    ) -> None:
        """Equal path content must not report changes across list/tuple forms."""
        (tmp_path / "src").mkdir()
        manager = self._manager(tmp_path)
        expected_extra = manager.pyright_extra_paths(project_dir=tmp_path, is_root=True)
        # mypy derives independently of pyrefly since cosmos-45hiv: mypy must
        # not receive the project root (it enumerates roots and aborts on the
        # same file resolving under two module names).
        expected_mypy = manager.mypy_search_paths(project_dir=tmp_path, is_root=True)
        tm.that(isinstance(expected_extra, tuple), eq=True)
        tm.that(isinstance(expected_mypy, tuple), eq=True)
        doc = u.Cli.toml_document()
        tool = u.Cli.toml_table()
        pyright = u.Cli.toml_table()
        mypy = u.Cli.toml_table()
        pyright["extraPaths"] = list(expected_extra)
        mypy["mypy_path"] = list(expected_mypy)
        tool["pyright"] = pyright
        tool["mypy"] = mypy
        doc["tool"] = tool
        changes = manager.sync_doc(doc, project_dir=tmp_path, is_root=True)
        tm.that(changes, eq=[])
        changes_again = manager.sync_doc(doc, project_dir=tmp_path, is_root=True)
        tm.that(changes_again, eq=[])
