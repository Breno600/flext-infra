"""Codemod enforcement quality gate.

Runs ``ast-grep scan`` with the codemod rules discovered via
``importlib.resources`` cascade (ADR-014). Policy findings block the final
check; incomplete scans and native machinery failures remain distinct errors.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, config, m, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraCodemodGate(FlextInfraGate):
    """Report codemod rule findings for the selected repository."""

    gate_id: ClassVar[str] = "codemod"
    gate_name: ClassVar[str] = "Codemod Enforcement"
    can_fix: ClassVar[bool] = False
    tool_name: ClassVar[str] = c.Infra.SARIF_TOOL_INFO["codemod"][0]
    tool_url: ClassVar[str] = c.Infra.SARIF_TOOL_INFO["codemod"][1]

    @override
    def check(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.GateExecution:
        """Run ast-grep only on this repository's first-class source roots.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        Raises:
            FileNotFoundError: If ``not targets``.

        """
        targets = (
            *self._existing_check_dirs(project_dir),
            *(path.name for path in project_dir.glob("*.py") if path.is_file()),
        )
        if not targets:
            raise FileNotFoundError(project_dir)
        return self._execute_check_command(project_dir, ctx, targets, time.monotonic())

    @override
    def check_files(
        self,
        files: t.SequenceOf[Path],
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.GateExecution:
        """Scan every requested file against every elected provider ruleset.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        Raises:
            FileNotFoundError: If ``not path.is_file()``.

        """
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
        """Keep whole-project and file-scoped scans on the same native contract.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        Raises:
            RuntimeError: If codemod rule planning failed without a diagnostic.

        """
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

        rules_by_id = {rule.id: rule for rule in planned.value.rules}
        binary = u.Infra.managed_mise_binary(c.Infra.SG, self._repository_root)
        if binary.failure:
            failure = binary.error
            if not failure:
                msg = "managed scanner resolution failed without a diagnostic"
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
                self._scan_command(ruleset, targets, binary.value),
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
                    ),
                )
                break
            # DiagnosticError (exit 1) requires a valid RuleMatch array,
            # matching error count and the exact terminal diagnostic below.
            # Additional native diagnostics make that scan incomplete.
            report, expected_stderr = self._validated_scan_report(scan, ruleset)
            if scan.stderr.strip() != expected_stderr:
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
                    ),
                )
                break
            facts = u.Infra.codemod_project_facts(
                project_dir,
                tuple(rules_by_id[finding.rule_id] for finding in report.root),
            )
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
                if u.Infra.codemod_context_admits(
                    project_dir,
                    rules_by_id[finding.rule_id],
                    Path(finding.file),
                    {**finding.captures, **finding.transformed},
                    facts,
                )
            )

        # A completed scan still blocks when elected policy rules find code.
        # Native scanner failures retain their distinct failure diagnostics.
        issues = (*failures, *findings)
        return m.Infra.GateExecution(
            result=self._gate_result(
                project_dir,
                passed=not issues,
                errors=[issue.formatted for issue in issues],
                started=started,
            ),
            issues=issues,
            outcome=(
                c.Infra.ToolOutcome.ERROR
                if failures
                else c.Infra.ToolOutcome.FINDINGS
                if findings
                else c.Infra.ToolOutcome.CLEAN
            ),
            raw_output="\n".join((
                (f"{len(findings)} policy findings; {len(failures)} native failures"),
                *raw_output,
            )),
        )

    @staticmethod
    def _validated_scan_report(
        scan: p.Cli.CommandOutput,
        ruleset: m.Infra.CodemodRuleset,
    ) -> t.Pair[m.Infra.AstGrepReport, str]:
        """Validate findings and derive their exact native terminal diagnostic.

        Returns:
            The resulting ``t.Pair[m.Infra.AstGrepReport, str]``.

        Raises:
            ValueError: If ``(scan.outcome.raw_return_code == 1) != bool(error_count)``;
                or if ``any((finding.rule_id not in ruleset.rule_ids for finding in
                report.root))``.

        """
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
            "\n".join((
                c.Infra.AST_GREP_ERROR_FINDING_RECEIPT.format(count=error_count),
                c.Infra.AST_GREP_ERROR_FINDING_HELP,
            ))
            if error_count
            else ""
        )
        return report, expected_stderr

    @staticmethod
    def _scan_command(
        ruleset: m.Infra.CodemodRuleset,
        targets: t.StrSequence,
        binary: Path,
    ) -> t.StrSequence:
        """Canonical ast-grep invocation for one composed provider ruleset.

        Returns:
            The resulting ``t.StrSequence``.

        """
        # The gate scans the same inventory `make mod` rewrites: trees the
        # codegen artifact SSOT ignores for source scans (generated sources
        # included) stay outside it even when Git tracks them.
        globs: t.StrSequence = tuple(
            f"!{dir_name}/"
            for dir_name in sorted({
                *c.Infra.CHECK_EXCLUDED_DIRS,
                *config.Infra.codegen.source_scan_ignored,
            })
        )
        cmd: list[str] = [
            str(binary),
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
