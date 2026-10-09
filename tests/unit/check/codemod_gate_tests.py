"""Public codemod gate evidence against the real ast-grep scanner.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

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
    """Block on every policy finding and on every native scanner failure."""

    @staticmethod
    def _project(tmp_path: Path, *, severity: str = "error") -> Path:
        project = tmp_path / "scanner-contract"
        config_path = project / c.Infra.CODEMOD_CONFIG_RELPATH
        rules = config_path.parent / c.Cli.RULES_DIR_NAME
        rules.mkdir(parents=True)
        (project / "src").mkdir()
        (project / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "scanner-contract"\nversion = "1.0.0"\n'
            "dependencies = []\n",
            encoding="utf-8",
        )
        config_path.write_text(
            f"ruleDirs: [{c.Cli.RULES_DIR_NAME}]\n",
            encoding="utf-8",
        )
        for name in ("first", "second"):
            (rules / f"{name}.yml").write_text(
                f"id: contract-{name}\nlanguage: Python\nseverity: {severity}\n"
                f"message: Observed {name}\nrule:\n  pattern: {name}($VALUE)\n",
                encoding="utf-8",
            )
        return project

    @pytest.mark.parametrize("severity", ["error", "warning", "info", "hint"])
    def test_policy_findings_block_at_every_severity(
        self,
        tmp_path: Path,
        severity: str,
    ) -> None:
        """Test policy findings block at every severity."""
        project = self._project(tmp_path, severity=severity)
        source = project / "src" / "subject.py"
        source.write_text("\nsecond(1)\n", encoding="utf-8")

        execution = u.Tests.run_gate_check(FlextInfraCodemodGate, tmp_path, project)

        tm.that(execution.result.passed, eq=False)
        policy_findings = tuple(
            issue for issue in execution.issues if issue.code == "contract-second"
        )
        tm.that(len(policy_findings), eq=1)
        finding = policy_findings[0]
        tm.that(finding.file.endswith("src/subject.py"), eq=True)
        tm.that((finding.line, finding.column), eq=(2, 1))
        tm.that(finding.severity, eq=severity)
        tm.that(
            tuple(execution.result.errors),
            eq=tuple(issue.formatted for issue in execution.issues),
        )
        tm.that(
            execution.finding_count,
            eq=len(execution.issues),
        )
        if severity == "error":
            tm.that(execution.raw_output, has="exit=1")
            tm.that(execution.raw_output, has="error(s) found in code")

    def test_clean_native_scan_has_no_findings(self, tmp_path: Path) -> None:
        """Test clean native scan has no findings."""
        project = self._project(tmp_path)
        (project / "src" / "subject.py").write_text("", encoding="utf-8")

        execution = u.Tests.run_gate_check(FlextInfraCodemodGate, tmp_path, project)

        tm.that(execution.result.passed, eq=True)
        tm.that(execution.issues, empty=True)
        tm.that(execution.raw_output, has="exit=0")

    def test_check_files_uses_every_rule_and_only_requested_files(
        self,
        tmp_path: Path,
    ) -> None:
        """Test check files uses every rule and only requested files."""
        project = self._project(tmp_path)
        selected = project / "src" / "selected.py"
        selected.write_text("second(1)\n", encoding="utf-8")
        other = project / "src" / "other.py"
        other.write_text("second(2)\n", encoding="utf-8")

        execution = FlextInfraCodemodGate(tmp_path).check_files(
            (selected,),
            project,
            u.Tests.gate_context(tmp_path),
        )

        tm.that(execution.result.passed, eq=False)
        policy_findings = tuple(
            issue for issue in execution.issues if issue.code == "contract-second"
        )
        tm.that(len(policy_findings), eq=1)
        tm.that(policy_findings[0].file.endswith("src/selected.py"), eq=True)

    def test_missing_requested_file_cannot_be_deselected(self, tmp_path: Path) -> None:
        """Test missing requested file cannot be deselected."""
        project = self._project(tmp_path)
        missing = project / "src" / "missing.py"
        gate = FlextInfraCodemodGate(tmp_path)
        context = u.Tests.gate_context(tmp_path)

        with pytest.raises(FileNotFoundError):
            gate.check_files((missing,), project, context)

    @pytest.mark.parametrize("finding", [False, True])
    def test_public_file_check_reuses_elected_scanner_scope(
        self,
        tmp_path: Path,
        *,
        finding: bool,
    ) -> None:
        """Public check uses the native configured scanner for exactly one file."""
        project = self._project(tmp_path)
        source_root = project / config.Infra.source_scan.roots[0]
        source_root.mkdir(exist_ok=True)
        selected = source_root / "literal.py"
        selected.write_text("second(1)\n" if finding else "", encoding="utf-8")
        sibling = source_root / "other.py"
        sibling.write_text("second(2)\n", encoding="utf-8")
        before = (selected.read_bytes(), sibling.read_bytes())
        reports = tmp_path / "reports"
        code = main([
            "check",
            "run",
            "--repository-root",
            str(project),
            "--file",
            str(selected.relative_to(project)),
            "--gates",
            "codemod",
            "--reports-dir",
            str(reports),
        ])
        tm.that(code, eq=1 if finding else 0)
        (report_path,) = reports.glob(f"*/{c.Infra.CHECK_REPORT_SARIF_FILENAME}")
        findings = tm.ok(
            u.Infra.check_report_findings(project, reports_dir=report_path.parent),
        )
        # The bundled policy rules also scan the selected file; the fixture
        # rule proves the scope, because the unselected sibling matches it too.
        tm.that(
            [row.rule_id for row in findings].count("contract-second"),
            eq=1 if finding else 0,
        )
        tm.that((selected.read_bytes(), sibling.read_bytes()), eq=before)

    @pytest.mark.parametrize("severity", ["error", "warning", "info", "hint"])
    def test_workspace_pipeline_fails_the_project_on_policy_findings(
        self,
        tmp_path: Path,
        severity: str,
    ) -> None:
        """The public check facade fails the project on any rule finding.

        The gate line, the report row and the SARIF run carry the same finding
        that fails the gate, whatever its native severity.
        """
        project = self._project(tmp_path, severity=severity)
        (project / "src" / "subject.py").write_text("second(1)\n", encoding="utf-8")
        reports = tmp_path / "reports"

        results = tm.ok(
            FlextInfraWorkspaceChecker(repository_root=tmp_path).run_projects(
                [project.name],
                ["codemod"],
                reports_dir=reports,
            ),
        )

        result = results[0]
        tm.that(result.passed, eq=False)
        receipt = result.gates["codemod"].raw_receipt
        assert receipt is not None
        reports = receipt.parent.parent
        markdown = (reports / c.Infra.CHECK_REPORT_MARKDOWN_FILENAME).read_text(
            encoding="utf-8",
        )
        tm.that(markdown, has=f"| {project.name} | FAIL |")
        tm.that(markdown, has="contract-second")
        sarif = m.Infra.SarifReport.model_validate_json(
            (reports / c.Infra.CHECK_REPORT_SARIF_FILENAME).read_text(encoding="utf-8"),
        )
        observed = tuple(
            finding
            for run in sarif.runs
            for finding in run.results
            if finding.rule_id == "contract-second"
        )
        tm.that(len(observed), eq=1)
        tm.that(observed[0].message, has="Observed second")

    def test_invalid_rule_is_a_native_failure(self, tmp_path: Path) -> None:
        """Test invalid rule is a native failure."""
        project = self._project(tmp_path)
        rules = (project / c.Infra.CODEMOD_CONFIG_RELPATH).parent / c.Cli.RULES_DIR_NAME
        (rules / "second.yml").write_text(
            "id: contract-second\nlanguage: invalid-language\n"
            "rule:\n  pattern: second($VALUE)\n",
            encoding="utf-8",
        )
        (project / "src" / "subject.py").write_text("second(1)\n", encoding="utf-8")

        execution = u.Tests.run_gate_check(FlextInfraCodemodGate, tmp_path, project)

        tm.that(execution.result.passed, eq=False)
        tm.that(
            any(issue.code == c.Infra.ToolOutcome.ERROR for issue in execution.issues),
            eq=True,
        )
        # The native ast-grep diagnostic names the rule file it cannot parse;
        # its wording for the bad field is the tool's, not this contract's.
        tm.that(execution.raw_output, has="Cannot parse rule")
        tm.that(execution.raw_output, has="second.yml")

    def test_native_traversal_error_cannot_be_hidden_by_a_policy_finding(
        self,
        tmp_path: Path,
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
        tm.that(
            any(issue.code == c.Infra.ToolOutcome.ERROR for issue in execution.issues),
            eq=True,
        )
        tm.that(execution.raw_output, has="ERROR:")
        tm.that(execution.raw_output, has="error(s) found in code")

    @staticmethod
    @pytest.mark.parametrize("payload", ["", "[", "{}", "[{}]", "[null]"])
    def test_native_json_contract_rejects_malformed_output(payload: str) -> None:
        """An empty stream or malformed finding cannot be a clean native scan."""
        with pytest.raises(m.ValidationError):
            m.Infra.AstGrepReport.model_validate_json(payload)
