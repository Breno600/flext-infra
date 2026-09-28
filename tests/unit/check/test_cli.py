"""Public CLI tests for workspace quality checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, main
from flext_infra.check import FlextInfraWorkspaceChecker
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraWorkspaceCheckCli:
    """Exercise the public check CLI without patching internal services."""

    @staticmethod
    def _create_workspace(
        tmp_path: Path, *, project_names: t.StrSequence = ("flext-core",)
    ) -> Path:
        workspace = tmp_path / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        for project_name in project_names:
            project = u.Tests.mk_project(
                workspace,
                project_name,
                pyproject=(f'[project]\nname = "{project_name}"\nversion = "0.1.0"\n'),
                with_src=True,
            )
            package = project / "src" / project_name.replace("-", "_")
            package.joinpath("__init__.py").write_text(
                f'"""{project_name} fixture package."""\n', encoding="utf-8"
            )
        return workspace

    @staticmethod
    def _write_module(workspace: Path, project_name: str, content: str) -> Path:
        module_path = (
            workspace
            / project_name
            / "src"
            / project_name.replace("-", "_")
            / "module.py"
        )
        module_path.write_text(f'"""Fixture module."""\n\n{content}', encoding="utf-8")
        return module_path

    def test_resolve_gates_rejects_duplicate_explicit_gate(self) -> None:
        result = FlextInfraWorkspaceChecker.resolve_gates([
            c.Infra.LINT,
            c.Infra.PYREFLY,
            c.Infra.LINT,
        ])
        tm.fail(result, has=f"duplicate gate '{c.Infra.LINT}'")

    @pytest.mark.parametrize(
        ("source", "expected_exit"),
        [("value = 1\n", 0), ("def broken(:\n", 1)],
        ids=["passing_project", "failing_project"],
    )
    def test_run_cli_lint_exit_code_matches_source_validity(
        self, tmp_path: Path, source: str, expected_exit: int
    ) -> None:
        workspace = self._create_workspace(tmp_path)
        _ = self._write_module(workspace, "flext-core", source)

        exit_code = main([
            "check",
            "run",
            "--repository-root",
            str(workspace),
            "--gates",
            "lint",
            "--projects",
            "flext-core",
        ])

        tm.that(exit_code, eq=expected_exit)

    def test_run_cli_returns_one_for_report_directory_error(
        self, tmp_path: Path
    ) -> None:
        workspace = self._create_workspace(tmp_path)
        _ = self._write_module(workspace, "flext-core", "value = 1\n")
        blocked = tmp_path / "blocked"
        blocked.write_text("not a directory\n", encoding="utf-8")

        exit_code = main([
            "check",
            "run",
            "--repository-root",
            str(workspace),
            "--gates",
            "lint",
            "--projects",
            "flext-core",
            "--reports-dir",
            str(blocked / "check"),
        ])

        tm.that(exit_code, eq=1)

    @pytest.mark.parametrize("reports_directory", [None, "artifacts/check"])
    def test_run_cli_handles_multiple_projects(
        self, tmp_path: Path, reports_directory: str | None
    ) -> None:
        workspace = self._create_workspace(tmp_path, project_names=("proj1", "proj2"))
        _ = self._write_module(workspace, "proj1", "value = 1\n")
        _ = self._write_module(workspace, "proj2", "other = 2\n")

        arguments = [
            "check",
            "run",
            "--repository-root",
            str(workspace),
            "--gates",
            "lint",
            "--projects",
            "proj1",
            "--projects",
            "proj2",
        ]
        if reports_directory is not None:
            arguments.extend(["--reports-dir", reports_directory])
        caller = tmp_path / "caller"
        caller.mkdir()
        relative_reports = reports_directory or f"{c.Infra.REPORTS_DIR_NAME}/check"
        report_name = c.Infra.CHECK_REPORT_MARKDOWN_FILENAME
        caller_report = caller / relative_reports / report_name
        caller_report.parent.mkdir(parents=True)
        caller_report.write_text("Caller report must survive.\n", encoding="utf-8")

        with tm.scope(cwd=str(caller)):
            exit_code = main(arguments)

        tm.that(exit_code, eq=0)
        report = (workspace / relative_reports / report_name).read_text(
            encoding="utf-8"
        )
        tm.that(report, has=["proj1", "proj2"])
        tm.that(
            caller_report.read_text(encoding="utf-8"),
            eq="Caller report must survive.\n",
        )

    def test_run_cli_fix_contract_preserves_failure_when_reporting(
        self, tmp_path: Path
    ) -> None:
        workspace = self._create_workspace(tmp_path)
        module_path = self._write_module(workspace, "flext-core", "def broken(:\n")

        exit_code = main([
            "check",
            "run",
            "--repository-root",
            str(workspace),
            "--gates",
            "lint",
            "--apply",
            "--report-findings",
            "--ruff-args",
            "--select F401",
            "--projects",
            "flext-core",
        ])

        # Reporting cannot turn remaining gate failures into success;
        # an unparsable module is never rewritten.
        tm.that(exit_code, eq=1)
        tm.that(
            module_path.read_text(encoding="utf-8"),
            eq='"""Fixture module."""\n\ndef broken(:\n',
        )

    def test_run_cli_check_contract_fails_on_remaining_findings(
        self, tmp_path: Path
    ) -> None:
        """Apply without ``--report-findings`` still fails on remaining findings."""
        workspace = self._create_workspace(tmp_path)
        module_path = self._write_module(workspace, "flext-core", "def broken(:\n")

        exit_code = main([
            "check",
            "run",
            "--repository-root",
            str(workspace),
            "--gates",
            "lint",
            "--apply",
            "--ruff-args",
            "--select F401",
            "--projects",
            "flext-core",
        ])

        # No --report-findings: apply mode still fails while findings remain,
        # and the unparsable module is never rewritten.
        tm.that(exit_code, eq=1)
        tm.that(
            module_path.read_text(encoding="utf-8"),
            eq='"""Fixture module."""\n\ndef broken(:\n',
        )

    def test_run_cli_check_only_preserves_source(self, tmp_path: Path) -> None:
        workspace = self._create_workspace(tmp_path)
        module_path = self._write_module(
            workspace, "flext-core", "import os\n\nvalue = 1\n"
        )

        exit_code = main([
            "check",
            "run",
            "--repository-root",
            str(workspace),
            "--gates",
            "lint",
            "--apply",
            "--check-only",
            "--ruff-args",
            "--select F401",
            "--projects",
            "flext-core",
        ])

        tm.that(exit_code, eq=1)
        tm.that(
            module_path.read_text(encoding="utf-8"),
            eq='"""Fixture module."""\n\nimport os\n\nvalue = 1\n',
        )

    def test_run_cli_accepts_shared_dry_run_flag(self, tmp_path: Path) -> None:
        workspace = self._create_workspace(tmp_path)
        _ = self._write_module(workspace, "flext-core", "value = 1\n")

        exit_code = main([
            "check",
            "--dry-run",
            "run",
            "--repository-root",
            str(workspace),
            "--gates",
            "lint",
            "--projects",
            "flext-core",
        ])

        tm.that(exit_code, eq=0)
