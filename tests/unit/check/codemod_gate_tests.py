"""Public codemod gate evidence against the real ast-grep scanner."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, m
from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker
from flext_infra.gates.codemod import FlextInfraCodemodGate
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraCodemodGate:
    """Separate native scanner failures from observable policy diagnostics."""

    @staticmethod
    def _project(tmp_path: Path, *, severity: str = "error") -> Path:
        project = tmp_path / "scanner-contract"
        (project / "rules").mkdir(parents=True)
        (project / "src").mkdir()
        (project / c.Infra.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "scanner-contract"\nversion = "1.0.0"\n'
            "dependencies = []\n",
            encoding="utf-8",
        )
        (project / c.Infra.CODEMOD_CONFIG_FILENAME).write_text(
            "ruleDirs: [rules]\n", encoding="utf-8"
        )
        for name in ("first", "second"):
            (project / "rules" / f"{name}.yml").write_text(
                f"id: contract-{name}\nlanguage: Python\nseverity: {severity}\n"
                f"message: Observed {name}\nrule:\n  pattern: {name}($VALUE)\n",
                encoding="utf-8",
            )
        return project

    @pytest.mark.parametrize("severity", ["error", "warning", "info", "hint"])
    def test_native_findings_remain_visible_and_observational(
        self, tmp_path: Path, severity: str
    ) -> None:
        project = self._project(tmp_path, severity=severity)
        source = project / "src" / "subject.py"
        source.write_text("\nsecond(1)\n", encoding="utf-8")

        execution = u.Tests.run_gate_check(FlextInfraCodemodGate, tmp_path, project)

        tm.that(execution.result.passed, eq=True)
        findings = tuple(
            issue
            for issue in execution.observational_issues
            if issue.code == "contract-second"
        )
        tm.that(len(findings), eq=1)
        finding = findings[0]
        tm.that(finding.file.endswith("src/subject.py"), eq=True)
        tm.that((finding.line, finding.column), eq=(2, 1))
        tm.that(finding.severity, eq=severity)
        tm.that(execution.result.errors, empty=True)
        tm.that(execution.error_count, eq=0)
        if severity == "error":
            tm.that(execution.raw_output, has="exit=1")
            tm.that(execution.raw_output, has="error(s) found in code")

    def test_clean_native_scan_has_no_findings(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        (project / "src" / "subject.py").write_text("", encoding="utf-8")

        execution = u.Tests.run_gate_check(FlextInfraCodemodGate, tmp_path, project)

        tm.that(execution.result.passed, eq=True)
        tm.that(execution.issues, empty=True)
        tm.that(execution.observational_issues, empty=True)
        tm.that(execution.raw_output, has="exit=0")

    def test_check_files_uses_every_rule_and_only_requested_files(
        self, tmp_path: Path
    ) -> None:
        project = self._project(tmp_path)
        selected = project / "src" / "selected.py"
        selected.write_text("second(1)\n", encoding="utf-8")
        other = project / "src" / "other.py"
        other.write_text("second(2)\n", encoding="utf-8")

        execution = FlextInfraCodemodGate(tmp_path).check_files(
            (selected,), project, u.Tests.gate_context(tmp_path)
        )

        tm.that(execution.result.passed, eq=True)
        findings = tuple(
            issue
            for issue in execution.observational_issues
            if issue.code == "contract-second"
        )
        tm.that(len(findings), eq=1)
        tm.that(findings[0].file.endswith("src/selected.py"), eq=True)

    def test_missing_requested_file_cannot_be_deselected(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        missing = project / "src" / "missing.py"
        gate = FlextInfraCodemodGate(tmp_path)
        context = u.Tests.gate_context(tmp_path)

        with pytest.raises(FileNotFoundError):
            gate.check_files((missing,), project, context)

    def test_workspace_pipeline_reports_observations_without_functional_errors(
        self, tmp_path: Path
    ) -> None:
        project = self._project(tmp_path)
        (project / "src" / "subject.py").write_text("second(1)\n", encoding="utf-8")
        reports = tmp_path / "reports"

        results = tm.ok(
            FlextInfraWorkspaceChecker(repository_root=tmp_path).run_projects(
                [project.name], ["codemod"], reports_dir=reports
            )
        )

        result = results[0]
        tm.that(result.passed, eq=True)
        tm.that(result.total_errors, eq=0)
        tm.that(result.total_observations > 0, eq=True)
        markdown = (reports / c.Infra.CHECK_REPORT_MARKDOWN_FILENAME).read_text(
            encoding="utf-8"
        )
        tm.that(markdown, has=f"| {project.name} | PASS | 0 |")
        tm.that(markdown, has="Observational [error]")
        sarif = m.Infra.SarifReport.model_validate_json(
            (reports / c.Infra.CHECK_REPORT_SARIF_FILENAME).read_text(encoding="utf-8")
        )
        observed = tuple(
            finding
            for run in sarif.runs
            for finding in run.results
            if finding.rule_id == "contract-second"
        )
        tm.that(len(observed), eq=1)
        tm.that(observed[0].level, eq="note")
        tm.that(observed[0].message, has="Observational [error]")

    def test_invalid_rule_is_a_native_failure(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        (project / "rules" / "second.yml").write_text(
            "id: contract-second\nlanguage: invalid-language\n"
            "rule:\n  pattern: second($VALUE)\n",
            encoding="utf-8",
        )
        (project / "src" / "subject.py").write_text("second(1)\n", encoding="utf-8")

        execution = u.Tests.run_gate_check(FlextInfraCodemodGate, tmp_path, project)

        tm.that(execution.result.passed, eq=False)
        tm.that(any(issue.code == "TOOL_ERROR" for issue in execution.issues), eq=True)
        tm.that(execution.raw_output, has="invalid-language")

    def test_native_traversal_error_cannot_be_hidden_by_a_policy_finding(
        self, tmp_path: Path
    ) -> None:
        """A partial walk remains red even when another file has an error match."""
        project = self._project(tmp_path)
        (project / "src" / "subject.py").write_text("second(1)\n", encoding="utf-8")
        blocked = project / "src" / "unreadable"
        blocked.mkdir()
        (blocked / "hidden.py").write_text("second(2)\n", encoding="utf-8")
        original_mode = blocked.stat().st_mode
        blocked.chmod(0)
        try:
            with pytest.raises(PermissionError):
                tuple(blocked.iterdir())
            execution = u.Tests.run_gate_check(FlextInfraCodemodGate, tmp_path, project)
        finally:
            blocked.chmod(original_mode)

        tm.that(execution.result.passed, eq=False)
        tm.that(any(issue.code == "TOOL_ERROR" for issue in execution.issues), eq=True)
        tm.that(execution.raw_output, has="ERROR:")
        tm.that(execution.raw_output, has="error(s) found in code")

    @pytest.mark.parametrize("payload", ["", "[", "{}", "[{}]", "[null]"])
    def test_native_json_contract_rejects_malformed_output(self, payload: str) -> None:
        """An empty stream or malformed finding cannot be a clean native scan."""
        with pytest.raises(m.ValidationError):
            m.Infra.AstGrepReport.model_validate_json(payload)
