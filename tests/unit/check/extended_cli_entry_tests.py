"""Public CLI entry tests for workspace check commands."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import main
from tests import c, u


class TestsFlextInfraExtendedCliEntry:
    """Tests for the check CLI entry points."""

    @staticmethod
    def _workspace(tmp_path: Path) -> Path:
        workspace = tmp_path / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        _ = u.Tests.mk_project(
            workspace,
            "p1",
            pyproject='[project]\nname = "p1"\nversion = "0.1.0"\n',
            with_src=True,
        )
        (workspace / "p1/src/p1/__init__.py").write_text(
            '"""Test package."""\n', encoding="utf-8"
        )
        u.Tests.declare_workspace_projects(workspace, ("p1",))
        return workspace

    def test_empty_workspace_errors(self, tmp_path: Path) -> None:
        tm.that(main(["check", "run", "--repository-root", str(tmp_path)]), eq=1)

    def test_run_accepts_explicit_scope(self, tmp_path: Path) -> None:
        workspace = self._workspace(tmp_path)
        tm.that(
            main([
                "check",
                "run",
                "--repository-root",
                str(workspace),
                "--projects",
                "p1",
                "--gates",
                "lint",
            ]),
            eq=0,
        )

    def test_run_auto_discovers_workspace_projects(self, tmp_path: Path) -> None:
        workspace = self._workspace(tmp_path)
        tm.that(
            main([
                "check",
                "run",
                "--repository-root",
                str(workspace),
                "--gates",
                "lint",
            ]),
            eq=0,
        )

    def test_with_projects_success(self, tmp_path: Path) -> None:
        workspace = self._workspace(tmp_path)
        tm.that(
            main([
                "check",
                "run",
                "--repository-root",
                str(workspace),
                "--projects",
                "p1",
                "--gates",
                "lint",
            ]),
            eq=0,
        )

    def test_with_projects_failure(self, tmp_path: Path) -> None:
        workspace = self._workspace(tmp_path)
        broken_file = workspace / "p1" / "src" / "broken.py"
        broken_file.write_text("def broken(:\n", encoding="utf-8")
        tm.that(
            main([
                "check",
                "run",
                "--repository-root",
                str(workspace),
                "--projects",
                "p1",
                "--gates",
                "lint",
            ]),
            eq=1,
        )

    def test_check_main_routes_real_help(self) -> None:
        tm.that(main(["check", "run", "--help"]), eq=0)

    def test_fix_pyrefly_config_routes_real_help(self) -> None:
        tm.that(main(["check", "fix-pyrefly-settings", "--help"]), eq=0)

    def test_run_cli_anchors_relative_reports_dir_at_repository_root(
        self, tmp_path: Path
    ) -> None:
        """A relative ``--reports-dir`` never lands under the caller's cwd."""
        workspace = self._workspace(tmp_path)
        caller = tmp_path / "caller"
        caller.mkdir(parents=True, exist_ok=True)
        relative_reports = Path("reports/check")
        with tm.scope(cwd=str(caller)):
            exit_code = main([
                "check",
                "run",
                "--repository-root",
                str(workspace),
                "--gates",
                "lint",
                "--projects",
                "p1",
                "--reports-dir",
                str(relative_reports),
            ])
        tm.that(exit_code, eq=0)
        tm.ok(u.Infra.check_report_findings(workspace, reports_dir=relative_reports))
        tm.that(
            (
                workspace / relative_reports / c.Infra.CHECK_REPORT_MARKDOWN_FILENAME
            ).is_file(),
            eq=True,
        )
        tm.that((caller / relative_reports).exists(), eq=False)
