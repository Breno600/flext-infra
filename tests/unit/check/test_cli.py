"""Public CLI tests for workspace quality checks.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, config, m, main
from flext_infra.check import FlextInfraWorkspaceChecker
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraWorkspaceCheckCli:
    """Exercise the public check CLI without patching internal services."""

    @staticmethod
    def _create_workspace(
        tmp_path: Path,
        *,
        project_names: t.StrSequence = ("flext-core",),
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
                f'"""{project_name} fixture package."""\n',
                encoding="utf-8",
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

    @staticmethod
    def test_resolve_gates_rejects_duplicate_explicit_gate() -> None:
        """Test resolve gates rejects duplicate explicit gate."""
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
        self,
        tmp_path: Path,
        source: str,
        expected_exit: int,
    ) -> None:
        """Test run cli lint exit code matches source validity."""
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
        self,
        tmp_path: Path,
    ) -> None:
        """Test run cli returns one for report directory error."""
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
        self,
        tmp_path: Path,
        reports_directory: str | None,
    ) -> None:
        """Test run cli handles multiple projects."""
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
        default_reports = m.Infra.RunCommand(repository_root=workspace).reports_dir
        relative_reports = reports_directory or default_reports
        report_name = c.Infra.CHECK_REPORT_MARKDOWN_FILENAME
        caller_report = caller / relative_reports / report_name
        caller_report.parent.mkdir(parents=True)
        caller_report.write_text("Caller report must survive.\n", encoding="utf-8")

        with tm.scope(cwd=str(caller)):
            exit_code = main(arguments)

        tm.that(exit_code, eq=0)
        (report_path,) = (workspace / relative_reports).glob(f"*/{report_name}")
        report = report_path.read_text(
            encoding="utf-8",
        )
        tm.that(report, has=["proj1", "proj2"])
        tm.that(
            caller_report.read_text(encoding="utf-8"),
            eq="Caller report must survive.\n",
        )

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize("parallel", [False, True])
    @pytest.mark.parametrize("directory_option", [None, "--reports-dir"])
    def test_real_cli_invocations_preserve_independent_reports(
        tmp_path: Path,
        *,
        parallel: bool,
        directory_option: str | None,
    ) -> None:
        """Real native failures retain both runs, including concurrent CLI calls."""
        workspace = TestsFlextInfraWorkspaceCheckCli._create_workspace(
            tmp_path,
            project_names=("proj1",),
        )
        TestsFlextInfraWorkspaceCheckCli._write_module(
            workspace,
            "proj1",
            "def broken(:\n",
        )
        request = m.Infra.RunCommand(repository_root=workspace)
        reports_root = request.reports_dir_path
        command = [
            sys.executable,
            "-m",
            "flext_infra",
            "check",
            "run",
            "--repository-root",
            str(workspace),
            "--projects",
            "proj1",
            "--gates",
            c.Infra.LINT,
        ]
        if directory_option is not None:
            reports_root = tmp_path / "reports with spaces"
            command.extend([directory_option, str(reports_root)])
        reports_root.mkdir(parents=True)
        historical = reports_root / c.Infra.CHECK_REPORT_MARKDOWN_FILENAME
        historical.write_text("Unowned history.\n", encoding="utf-8")
        if parallel:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(u.Cli.run_raw, command) for _ in range(2)]
                outputs = [tm.ok(future.result()) for future in futures]
        else:
            outputs = [tm.ok(u.Cli.run_raw(command)) for _ in range(2)]
        reports = tuple(
            reports_root.glob(f"*/{c.Infra.CHECK_REPORT_MARKDOWN_FILENAME}"),
        )
        tm.that(len(reports), eq=2)
        tm.that(historical.read_text(encoding="utf-8"), eq="Unowned history.\n")
        for output in outputs:
            tm.that(output.outcome.raw_return_code, eq=1)
            tm.that(output.stdout + output.stderr, lacks="published another identity")
            tm.that(
                sum(str(report) in output.stdout + output.stderr for report in reports),
                eq=1,
            )
        for report in reports:
            tm.that(report.read_text(encoding="utf-8"), has=f"- {c.Infra.LINT}: FAIL")
            findings = tm.ok(
                u.Infra.check_report_findings(workspace, reports_dir=report.parent),
            )
            tm.that(findings, empty=False)
            (receipt,) = report.parent.glob(
                f"*/{c.Infra.LINT}{config.Infra.tooling.raw_check_receipt_suffix}",
            )
            tm.that(receipt.read_text(encoding="utf-8"), has=findings[0].message)

    def test_run_cli_fix_completes_and_keeps_remaining_findings(
        self,
        tmp_path: Path,
    ) -> None:
        """A repair run completes; what it cannot repair stays for check."""
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
            "--select unused-import",
            "--projects",
            "flext-core",
        ])

        # Ruff completes and reports the syntax error as a finding of the
        # code: the verb does not break, and the module is never rewritten.
        tm.that(exit_code, eq=0)
        tm.that(
            module_path.read_text(encoding="utf-8"),
            eq='"""Fixture module."""\n\ndef broken(:\n',
        )

    @staticmethod
    def test_run_cli_fix_declares_static_methods_beside_an_unparsable_module(
        tmp_path: Path,
    ) -> None:
        """A no-self-use repair completes when another module cannot parse."""
        workspace = TestsFlextInfraWorkspaceCheckCli._create_workspace(tmp_path)
        broken = TestsFlextInfraWorkspaceCheckCli._write_module(
            workspace,
            "flext-core",
            "def broken(:\n",
        )
        sample = broken.with_name("sample.py")
        sample.write_text(
            '"""Fixture sample."""\n'
            "\n"
            "\n"
            "class Sample:\n"
            '    """Sample owner."""\n'
            "\n"
            "    def value(self) -> int:\n"
            '        """Return one."""\n'
            "        return 1\n",
            encoding="utf-8",
        )

        exit_code = main([
            "check",
            "run",
            "--repository-root",
            str(workspace),
            "--gates",
            "lint",
            "--apply",
            "--ruff-args",
            "--select no-self-use",
            "--projects",
            "flext-core",
        ])

        tm.that(exit_code, eq=0)
        tm.that(
            sample.read_text(encoding="utf-8"),
            has="    @staticmethod\n    def value() -> int:\n",
        )
        tm.that(
            broken.read_text(encoding="utf-8"),
            eq='"""Fixture module."""\n\ndef broken(:\n',
        )

    def test_run_cli_fix_fails_on_a_tool_error(self, tmp_path: Path) -> None:
        """A status the tool does not declare breaks the repair verb."""
        workspace = self._create_workspace(tmp_path)
        self._write_module(workspace, "flext-core", "VALUE = 1\n")

        exit_code = main([
            "check",
            "run",
            "--repository-root",
            str(workspace),
            "--gates",
            "lint",
            "--apply",
            "--ruff-args",
            "--line-length not-a-number",
            "--projects",
            "flext-core",
        ])

        tm.that(exit_code, eq=1)

    def test_run_cli_check_only_preserves_source(self, tmp_path: Path) -> None:
        """Test run cli check only preserves source."""
        workspace = self._create_workspace(tmp_path)
        module_path = self._write_module(
            workspace,
            "flext-core",
            "import os\n\nvalue = 1\n",
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
        """Test run cli accepts shared dry run flag."""
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
