"""Tests for extra workspace checker gates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, r
from flext_infra.gates.bandit import FlextInfraBanditGate
from flext_infra.gates.markdown import FlextInfraMarkdownGate
from flext_infra.gates.pyright import FlextInfraPyrightGate
from flext_tests import tm
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestExtendedRunnerExtras:
    """Declarative public-gate tests."""

    def test_pyright_skips_when_project_has_no_python_files(
        self, tmp_path: Path
    ) -> None:
        _, project_dir = u.Tests.create_checker_project(tmp_path)

        result = u.Tests.run_gate_check(FlextInfraPyrightGate, tmp_path, project_dir)

        tm.that(result.result.passed, eq=True)
        tm.that(len(result.issues), eq=0)

    def test_pyright_parses_json_diagnostics(self, tmp_path: Path) -> None:
        _, project_dir = u.Tests.create_checker_project(tmp_path, with_src=True)
        _ = (project_dir / "src" / "main.py").write_text("# code\n", encoding="utf-8")
        runner = u.Tests.command_runner(
            stdout='{"generalDiagnostics": [{"file": "a.py", "range": {"start": {"line": 0, "character": 0}}, "rule": "E001", "message": "Error", "severity": "error"}]}',
            returncode=1,
        )

        result = u.Tests.run_gate_check(
            FlextInfraPyrightGate, tmp_path, project_dir, runner=runner
        )

        tm.that(not result.result.passed, eq=True)
        tm.that(len(result.issues), eq=1)

    def test_pyright_uses_project_config_target_when_configured(
        self, tmp_path: Path
    ) -> None:
        project_dir = u.Tests.mk_project(
            tmp_path,
            "pyright-project",
            pyproject="[tool.pyright]\ninclude = ['src']\n",
            with_src=True,
        )
        _ = (project_dir / "src" / "main.py").write_text("# code\n", encoding="utf-8")
        runner = u.Tests.SequenceRunner([
            r.ok(u.Tests.stub_run(stdout='{"generalDiagnostics": []}'))
        ])

        result = u.Tests.run_gate_check(
            FlextInfraPyrightGate, tmp_path, project_dir, runner=runner
        )

        tm.that(result.result.passed, eq=True)
        command = runner.commands[0]
        tm.that(
            command[1:],
            eq=(
                "-m",
                c.Infra.PYRIGHT,
                c.Infra.PYRIGHT_PROJECT_ARG,
                c.Infra.PYRIGHT_PROJECT_CONFIG_TARGET,
                "--outputjson",
            ),
        )

    def test_pyright_handles_invalid_json(self, tmp_path: Path) -> None:
        _, project_dir = u.Tests.create_checker_project(tmp_path, with_src=True)
        _ = (project_dir / "src" / "main.py").write_text("# code\n", encoding="utf-8")
        runner = u.Tests.command_runner(stdout="invalid json", returncode=1)

        result = u.Tests.run_gate_check(
            FlextInfraPyrightGate, tmp_path, project_dir, runner=runner
        )

        tm.that(not result.result.passed, eq=True)

    def test_bandit_skips_without_src_dir(self, tmp_path: Path) -> None:
        _, project_dir = u.Tests.create_checker_project(tmp_path)

        result = u.Tests.run_gate_check(FlextInfraBanditGate, tmp_path, project_dir)

        tm.that(result.result.passed, eq=True)
        tm.that(len(result.issues), eq=0)

    def test_bandit_parses_json_output(self, tmp_path: Path) -> None:
        _, project_dir = u.Tests.create_checker_project(tmp_path, with_src=True)
        runner = u.Tests.command_runner(
            stdout='{"results": [{"filename": "a.py", "line_number": 1, "test_id": "B101", "issue_text": "Assert used", "issue_severity": "MEDIUM"}]}',
            returncode=1,
        )

        result = u.Tests.run_gate_check(
            FlextInfraBanditGate, tmp_path, project_dir, runner=runner
        )

        tm.that(not result.result.passed, eq=True)
        tm.that(len(result.issues), eq=1)

    def test_bandit_handles_invalid_json(self, tmp_path: Path) -> None:
        _, project_dir = u.Tests.create_checker_project(tmp_path, with_src=True)
        runner = u.Tests.command_runner(stdout="invalid json", returncode=1)

        result = u.Tests.run_gate_check(
            FlextInfraBanditGate, tmp_path, project_dir, runner=runner
        )

        tm.that(not result.result.passed, eq=True)
        tm.that(len(result.issues), eq=1)
        tm.that(result.issues[0].code, eq="PARSE_ERROR")

    def test_bandit_reports_tool_failure_without_json(self, tmp_path: Path) -> None:
        _, project_dir = u.Tests.create_checker_project(tmp_path, with_src=True)
        runner = u.Tests.command_runner(stderr="Failed to spawn: bandit", returncode=1)

        result = u.Tests.run_gate_check(
            FlextInfraBanditGate, tmp_path, project_dir, runner=runner
        )

        tm.that(not result.result.passed, eq=True)
        tm.that(len(result.issues), eq=1)
        tm.that(result.issues[0].code, eq="TOOL_ERROR")
        tm.that(result.issues[0].message, contains="Failed to spawn: bandit")

    def test_markdown_skips_without_markdown_files(self, tmp_path: Path) -> None:
        _, project_dir = u.Tests.create_checker_project(tmp_path)

        result = u.Tests.run_gate_check(FlextInfraMarkdownGate, tmp_path, project_dir)

        tm.that(result.result.passed, eq=True)
        tm.that(len(result.issues), eq=0)

    def test_markdown_parses_cli_errors(self, tmp_path: Path) -> None:
        _, project_dir = u.Tests.create_checker_project(tmp_path)
        _ = (project_dir / "README.md").write_text("# Test\n", encoding="utf-8")
        runner = u.Tests.command_runner(
            stdout="README.md:1:1: [MD001] Heading level", returncode=1
        )

        result = u.Tests.run_gate_check(
            FlextInfraMarkdownGate, tmp_path, project_dir, runner=runner
        )

        tm.that(not result.result.passed, eq=True)
        tm.that(len(result.issues), eq=1)

    def test_markdown_reports_tool_failure_without_diagnostics(
        self, tmp_path: Path
    ) -> None:
        _, project_dir = u.Tests.create_checker_project(tmp_path)
        _ = (project_dir / "README.md").write_text("# Test\n", encoding="utf-8")
        runner = u.Tests.command_runner(
            stderr="execution error: missing rumdl", returncode=1
        )

        result = u.Tests.run_gate_check(
            FlextInfraMarkdownGate, tmp_path, project_dir, runner=runner
        )

        tm.that(not result.result.passed, eq=True)
        tm.that(len(result.issues), eq=1)
        tm.that(result.issues[0].code, eq="TOOL_ERROR")
        tm.that(result.issues[0].message, contains="missing rumdl")
