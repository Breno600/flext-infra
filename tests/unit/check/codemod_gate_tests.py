"""Public codemod gate evidence against the real ast-grep scanner.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import config, main
from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker
from flext_infra.gates.codemod import FlextInfraCodemodGate
from tests import c, m, t, u

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

    @staticmethod
    def _rule_files(
        project: Path,
        rule_id: str,
        tmp_path: Path,
    ) -> t.StrSequence:
        """Project-relative files the bundled rule ``rule_id`` reports.

        Returns:
            The sorted project-relative files the real scan reported.
        """
        execution = u.Tests.run_gate_check(FlextInfraCodemodGate, tmp_path, project)
        return sorted(
            (project / issue.file).resolve().relative_to(project.resolve()).as_posix()
            for issue in execution.issues
            if issue.code == rule_id
        )

    def test_flext_tests_import_is_banned_only_in_the_infra_package(
        self,
        tmp_path: Path,
    ) -> None:
        """The project-root scan reports flext_tests only inside flext_infra.

        Premise (operator-ruling-2026-10-08-subprocess-test-imports, item 2):
        the rule fires when flext-infra scans itself (``src/...`` paths), not
        only from the workspace root, and never binds another package.
        """
        project = self._project(tmp_path)
        for relative in ("src/flext_infra/leak.py", "src/flext_tests/tier.py"):
            module = project / relative
            module.parent.mkdir(parents=True)
            module.write_text("import flext_tests\n", encoding="utf-8")

        tm.that(
            self._rule_files(project, "ban-infra-runtime-flext-tests-import", tmp_path),
            eq=["src/flext_infra/leak.py"],
        )

    def test_subprocess_is_banned_outside_the_run_owner_scope(
        self,
        tmp_path: Path,
    ) -> None:
        """Only the Bandit-authorized owner modules may import subprocess.

        Premise (operator-ruling-2026-10-08-subprocess-test-imports, item 1):
        the codemod rule and the Bandit authorized exception share one owner
        scope; every other module runs processes through u.Cli.run.
        """
        project = self._project(tmp_path)
        entry = config.Infra.tooling.tools.bandit.authorized_exceptions[0]
        owners = tuple(
            pattern.replace("**/", "").replace("*", "spawn") for pattern in entry.files
        )
        consumer = "src/consumer/spawn.py"
        for relative in (*owners, consumer):
            module = project / relative
            module.parent.mkdir(parents=True, exist_ok=True)
            module.write_text("import subprocess\n", encoding="utf-8")

        tm.that(
            self._rule_files(project, "ban-subprocess-outside-run-owner", tmp_path),
            eq=[consumer],
        )

    def test_generated_source_tree_is_outside_the_scan(self, tmp_path: Path) -> None:
        """A tracked generated-source module never reaches the policy scan.

        Premise (flext-gknfx): generated trees are tracked, so Git ignore rules
        no longer hide them from ast-grep; the codegen artifact key does.
        """
        names = config.Infra.codegen.generated_sources
        tm.that(names, empty=False)
        project = self._project(tmp_path)
        tree = project / "src" / "pkg" / names[0]
        tree.mkdir(parents=True)
        (tree / "wire_pb2.py").write_text("\nsecond(1)\n", encoding="utf-8")
        (project / "src" / "pkg" / "subject.py").write_text("", encoding="utf-8")

        execution = u.Tests.run_gate_check(FlextInfraCodemodGate, tmp_path, project)

        tm.that(execution.result.passed, eq=True, msg=str(execution.issues))
        tm.that(execution.issues, empty=True)

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
        findings = tm.ok(u.Infra.check_report_findings(project, reports_dir=reports))
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
