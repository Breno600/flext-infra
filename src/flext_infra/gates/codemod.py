"""Codemod enforcement quality gate.

Runs ``ast-grep scan`` with the codemod rules discovered via
``importlib.resources`` cascade (ADR-014). Policy findings are observational:
they are reported for migration tracking and never block the build (operator
order 2026-09-24). Machinery failures — a broken rule plan or an ast-grep
crash — remain blocking, because silent scrutiny loss is never acceptable.

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
        _ = ctx
        started = time.monotonic()
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
                        file=c.Infra.PYPROJECT_FILENAME,
                        line=1,
                        column=0,
                        code=self.gate_id,
                        message=planned.error or "ast-grep rule discovery failed",
                        severity=str(c.Infra.GateSeverity.ERROR.value),
                    ),
                ),
                raw_output=planned.error or "ast-grep rule discovery failed",
                started=started,
            )

        findings: list[m.Infra.Issue] = []
        failures: list[m.Infra.Issue] = []
        for ruleset in planned.value.rulesets:
            scan = self._run(
                self._scan_command(ruleset, project_dir),
                project_dir,
                timeout=self._check_timeout(project_dir, ctx),
            )
            # ast-grep exits non-zero when it finds error-severity
            # diagnostics, so an exit code alone never means a crash: the
            # crash contract is a failed process with NO output at all.
            crashed = (
                not u.Cli.process_succeeded(scan.outcome) and not scan.stdout.strip()
            )
            if crashed:
                # A crashed scanner is a machinery failure: it stays blocking
                # and is never observable debt.
                failures.append(
                    m.Infra.Issue(
                        file=c.Infra.PYPROJECT_FILENAME,
                        line=1,
                        column=0,
                        code=self.gate_id,
                        message=(
                            f"{ruleset.provider}: ast-grep execution failed — "
                            f"{scan.stderr or 'unknown error'}"
                        ),
                        severity=str(c.Infra.GateSeverity.ERROR.value),
                    )
                )
            findings.extend(self._observational_findings(scan, ruleset.provider))

        return self._build_check_gate_execution(
            project_dir,
            # Operator order (2026-09-24): codemod policy findings are
            # observational — they are reported for migration tracking and
            # never block the build. Machinery failures (a broken rule plan
            # or an ast-grep crash) remain blocking above.
            passed=not failures,
            issues=[*failures, *findings],
            raw_output=(
                f"{len(planned.value.rules)} rules from "
                f"{len(planned.value.rulesets)} providers scanned, "
                f"{len(findings)} violations"
            ),
            started=started,
        )

    @staticmethod
    def _observational_findings(
        scan: p.Cli.CommandOutput, provider: str
    ) -> t.SequenceOf[m.Infra.Issue]:
        """Turn one scan's stdout into reported policy findings."""
        return tuple(
            m.Infra.Issue(
                file=provider,
                line=1,
                column=0,
                code=FlextInfraCodemodGate.gate_id,
                message=line.strip(),
                severity=str(c.Infra.GateSeverity.ERROR.value),
            )
            for line in scan.stdout.splitlines()
            if line.strip()
        )

    @staticmethod
    def _scan_command(
        ruleset: m.Infra.CodemodRuleset, project_dir: Path
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
        ]
        for glob in globs:
            cmd.extend([c.Infra.SG_GLOBS_FLAG, glob])
        cmd.append(str(project_dir))
        return tuple(cmd)

    def _rule_paths(self, project_dir: Path) -> t.SequenceOf[Path]:
        """Resolve the composed ast-grep rule files for one project."""
        planned = u.Infra.codemod_rule_plan(project_dir)
        if planned.failure:
            # A failed rule plan must never read as "no rules to scan" — that
            # would let the codemod gate pass on absent scrutiny.
            raise ValueError(planned.error or "codemod rule plan failed")
        return tuple(dict.fromkeys(rule.resource for rule in planned.value.rules))

    @override
    def _build_check_command(
        self, project_dir: Path, ctx: m.Infra.GateContext, check_dirs: t.StrSequence
    ) -> t.StrSequence:
        """Per-rule scans are issued by check(); expose the first rule command."""
        _ = ctx, check_dirs
        rules = self._rule_paths(project_dir)
        if not rules:
            return (c.Infra.SG, c.Infra.SCAN, ".")
        return u.Infra.ast_grep_scan_command(rules[0])

    @override
    def _parse_check_output(
        self, result: p.Cli.CommandOutput, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse a single ast-grep scan result into issues."""
        _ = ctx
        rules = self._rule_paths(project_dir)
        rule_path = rules[0] if rules else project_dir
        issues = self._observational_findings(result, rule_path.name)
        return not issues, issues
