"""Test extra paths sync behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tf, tm

from flext_infra import main, t
from flext_infra.deps.extra_paths import FlextInfraExtraPathsManager
from tests import u

_TEST_REPOSITORY_ROOT = Path(__file__).resolve().parent


class TestsFlextInfraDepsExtraPathsSync:
    """Behavior contract for test_extra_paths_sync."""

    @pytest.fixture
    def pyright_content(self) -> str:
        """Provide minimal Pyright configuration content."""
        return "[tool.pyright]\nextraPaths = []\n"

    def _create_pyproject(self, directory: Path, content: str) -> Path:
        pyproject_path: Path = tf(base_dir=directory).create(
            content=content, name="pyproject.toml"
        )
        return pyproject_path

    def _manager(
        self, repository_root: Path | None = None
    ) -> FlextInfraExtraPathsManager:
        return FlextInfraExtraPathsManager(
            repository_root=repository_root or _TEST_REPOSITORY_ROOT
        )

    @pytest.mark.parametrize(
        ("mode", "dry_run", "project_dirs", "expect_fail", "expect_has"),
        [
            ("project", False, ["proj"], False, None),
            ("project", True, ["proj"], False, "old"),
            ("root", False, None, False, None),
            ("none", True, [], False, None),
            ("none", True, None, False, None),
        ],
    )
    def test_sync_extra_paths_success_modes(
        self,
        tmp_path: Path,
        pyright_content: str,
        mode: str,
        *,
        dry_run: bool,
        project_dirs: t.StrSequence | None,
        expect_fail: bool,
        expect_has: str | None,
    ) -> None:
        """Verify sync extra paths success modes."""
        project_dirs_arg: t.SequenceOf[Path] | None = None
        if mode == "project":
            project = tmp_path / "proj"
            project.mkdir()
            content = (
                "[tool.pyright]\nextraPaths = ['old']\n" if dry_run else pyright_content
            )
            pyproject = self._create_pyproject(project, content)
            project_dirs_arg = [project] if project_dirs else []
            result = self._manager(tmp_path).sync_extra_paths(
                dry_run=dry_run, project_dirs=project_dirs_arg
            )
            tm.ok(result)
            if expect_has:
                tm.that(pyproject.read_text(encoding="utf-8"), has=expect_has)
            return
        if mode == "root":
            _ = self._create_pyproject(tmp_path, pyright_content)
            tm.ok(self._manager(tmp_path).sync_extra_paths())
            return
        _ = self._create_pyproject(tmp_path, pyright_content)
        result = self._manager(tmp_path).sync_extra_paths(
            dry_run=dry_run, project_dirs=[] if project_dirs == [] else None
        )
        if expect_fail:
            tm.fail(result)
            return
        tm.ok(result)

    def test_sync_extra_paths_missing_root_pyproject(self, tmp_path: Path) -> None:
        """Verify sync extra paths missing root pyproject."""
        tm.fail(self._manager(tmp_path).sync_extra_paths(), has="Missing")

    def test_sync_extra_paths_skips_selected_dirs_without_pyproject(
        self, tmp_path: Path
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
        ("mode", "dry_run", "expected_ok", "expect_fail"),
        [
            ("nonexistent", True, False, False),
            ("invalid", True, False, True),
            ("stubbed", False, True, False),
        ],
    )
    def test_sync_one_edge_cases(
        self,
        tmp_path: Path,
        pyright_content: str,
        mode: str,
        *,
        dry_run: bool,
        expected_ok: bool,
        expect_fail: bool,
    ) -> None:
        """Verify sync one edge cases."""
        if mode == "nonexistent":
            tm.that(
                not self
                ._manager(tmp_path)
                .sync_one(Path("/nonexistent/pyproject.toml"), dry_run=dry_run)
                .success,
                eq=True,
            )
            return
        if mode == "invalid":
            pyproject = self._create_pyproject(tmp_path, "invalid toml {")
            result = self._manager(tmp_path).sync_one(pyproject, dry_run=dry_run)
            if expect_fail:
                tm.fail(result)
                return
            tm.that(result.success, eq=expected_ok)
            return
        pyproject = self._create_pyproject(tmp_path, pyright_content)
        tm.ok(
            self._manager(tmp_path).sync_one(pyproject, is_root=True, dry_run=dry_run)
        )

    def test_sync_doc_is_idempotent_when_paths_already_match(
        self, tmp_path: Path
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
