"""Codemod enforcement quality gate.

Runs ``ast-grep scan`` with the codemod rules discovered via
``importlib.resources`` cascade (ADR-014). Valid policy findings remain
observable; incomplete scans and native machinery failures block the build.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, u

from .base_gate import FlextInfraGate

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraCodemodGate(FlextInfraGate):
    """Report codemod rule findings observationally across every project."""

    gate_id: ClassVar[str] = "codemod"
    gate_name: ClassVar[str] = "Codemod Enforcement"
    can_fix: ClassVar[bool] = False
    tool_name: ClassVar[str] = c.Infra.SARIF_TOOL_INFO["codemod"][0]
    tool_url: ClassVar[str] = c.Infra.SARIF_TOOL_INFO["codemod"][1]

    @override
    def check(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Run ast-grep scan with cascaded codemod rules."""
        return self._execute_check_command(project_dir, ctx, (".",), time.monotonic())

    @override
    def check_files(
        self, files: t.SequenceOf[Path], project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Scan every requested file against every elected provider ruleset."""
        if not files:
            return self.check(project_dir, ctx)
        for path in files:
            if not path.is_file():
                raise FileNotFoundError(path)
        return self._execute_check_command(
            project_dir,
            ctx,
            tuple(str(path.relative_to(project_dir)) for path in files),
            time.monotonic(),
        )

    @override
    def _execute_check_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        targets: t.StrSequence,
        started: float,
    ) -> m.Infra.GateExecution:
        """Keep whole-project and file-scoped scans on the same native contract."""
        planned = u.Infra.codemod_rule_plan(project_dir)
        if planned.failure:
            failure = planned.error
            if not failure:
                msg = "codemod rule planning failed without a diagnostic"
                raise RuntimeError(msg)
            return self._build_check_gate_execution(
                project_dir,
                passed=False,
                issues=(
                    m.Infra.Issue(
                        file=c.PYPROJECT_FILENAME,
                        line=1,
                        column=0,
                        code=self.gate_id,
                        message=failure,
                        severity=str(c.Infra.GateSeverity.ERROR.value),
                    ),
                ),
                raw_output=failure,
                started=started,
            )

        findings: list[m.Infra.Issue] = []
        failures: list[m.Infra.Issue] = []
        raw_output: list[str] = []
        for ruleset in planned.value.rulesets:
            scan = self._run(
                self._scan_command(ruleset, targets),
                project_dir,
                timeout=self._check_timeout(project_dir, ctx),
            )
            outcome = scan.outcome
            raw_output.extend((
                (
                    f"{ruleset.provider}: exit={outcome.raw_return_code}, "
                    f"timed_out={outcome.timed_out}, signal={outcome.forwarded_signal}"
                ),
                self._raw_output(scan),
            ))
            if (
                outcome.timed_out
                or outcome.forwarded_signal is not None
                or outcome.raw_return_code not in {0, 1}
                or (outcome.raw_return_code == 0 and bool(scan.stderr.strip()))
            ):
                failures.append(
                    self._command_error_issue(
                        scan,
                        tool=c.Infra.SG,
                        file=str(ruleset.config),
                        line=1,
                        column=1,
                    )
                )
                break
            # DiagnosticError (exit 1) requires a valid RuleMatch array,
            # matching error count and the exact terminal diagnostic below.
            # Additional native diagnostics make that scan incomplete.
            report, expected_stderr = self._validated_scan_report(scan, ruleset)
            if scan.stderr != expected_stderr:
                # ast-grep can continue after a traversal error and still return
                # DiagnosticError because another file has an error match.
                # Only the complete terminal diagnostic proves a clean walk.
                failures.append(
                    self._command_error_issue(
                        scan,
                        tool=c.Infra.SG,
                        file=str(ruleset.config),
                        line=1,
                        column=1,
                    )
                )
                break
            findings.extend(
                m.Infra.Issue(
                    file=finding.file,
                    line=finding.line + 1,
                    column=finding.column + 1,
                    code=finding.rule_id,
                    message=finding.message,
                    severity=finding.severity,
                )
                for finding in report.root
            )

        return self._build_check_gate_execution(
            project_dir,
            # Operator order (2026-09-24): codemod policy findings are
            # observational. Native scanner failures remain blocking.
            passed=not failures,
            issues=failures,
            observational_issues=findings,
            raw_output="\n".join((
                (
                    f"{len(findings)} observational findings; "
                    f"{len(failures)} native failures"
                ),
                *raw_output,
            )),
            started=started,
        )

    @staticmethod
    def _validated_scan_report(
        scan: p.Cli.CommandOutput, ruleset: m.Infra.CodemodRuleset
    ) -> t.Pair[m.Infra.AstGrepReport, str]:
        """Validate findings and derive their exact native terminal diagnostic."""
        report = m.Infra.AstGrepReport.model_validate_json(scan.stdout)
        error_count = sum(finding.severity == "error" for finding in report.root)
        if (scan.outcome.raw_return_code == 1) != bool(error_count):
            msg = (
                f"{ruleset.provider}: ast-grep exit {scan.outcome.raw_return_code} "
                "disagrees with the native diagnostic severities"
            )
            raise ValueError(msg)
        if any(finding.rule_id not in ruleset.rule_ids for finding in report.root):
            msg = f"{ruleset.provider}: ast-grep reported an unelected rule"
            raise ValueError(msg)
        expected_stderr = (
            f"Error: {error_count} error(s) found in code.\n"
            "Help: Scan succeeded and found error level diagnostics in the codebase.\n\n"
            if error_count
            else ""
        )
        return report, expected_stderr

    @staticmethod
    def _scan_command(
        ruleset: m.Infra.CodemodRuleset, targets: t.StrSequence
    ) -> t.StrSequence:
        """Canonical ast-grep invocation for one composed provider ruleset."""
        globs: t.StrSequence = tuple(
            f"!{dir_name}/" for dir_name in c.Infra.CHECK_EXCLUDED_DIRS
        )
        cmd: list[str] = [
            c.Infra.SG,
            c.Infra.SCAN,
            "--config",
            str(ruleset.config),
            "--filter",
            u.Infra.codemod_rule_filter(ruleset.rule_ids),
            "--json=compact",
        ]
        for glob in globs:
            cmd.extend([c.Infra.SG_GLOBS_FLAG, glob])
        cmd.extend(targets)
        return tuple(cmd)
