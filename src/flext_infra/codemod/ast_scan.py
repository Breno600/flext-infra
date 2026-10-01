"""Standalone ast engine verb (``refactor ast`` / ``make ast``).

Runs the two mechanical cascades of ``make mod`` (ADR-017): the ast-grep rule
cascade and the sed-by-list cascade from the rules tree (``config/rules/ast``
patterns plus ``config/rules/mod/sed.yaml``). Scan-only by default; ``--apply``
drives both cascades to a verified fixed point with exact receipts. Rope
phases, the enforcement component, and the lint gates belong to ``mod``.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import override

from flext_cli import cli

from flext_core import r

from .. import FlextInfraServiceBase, p, t, u
from . import FlextInfraModGateEngine, FlextInfraModTextGateEngine


class FlextInfraCodemodAstScan(FlextInfraServiceBase[t.Cli.ResultValue]):
    """Run the ast-grep cascade and the sed-by-list cascade of the rules tree."""

    @override
    def execute(self) -> p.Result[t.Cli.ResultValue]:
        """Report or apply both mechanical cascades of the ast engine."""
        planned = u.Infra.codemod_rule_plan(self.repository_root)
        if planned.failure:
            return r[t.Cli.ResultValue].from_failure(planned)
        rules = tuple(dict.fromkeys(rule.resource for rule in planned.value.rules))
        if self.apply_changes:
            return self._execute_apply(self.repository_root, rules)
        ast_report = FlextInfraModGateEngine.scan(
            self.repository_root, fix=False
        ).unwrap()
        text_report = FlextInfraModTextGateEngine.scan(
            self.repository_root, fix=False, validate_receipts=True
        ).unwrap()
        for entry in ast_report.entries:
            cli.display_text(
                f"ast: {entry.rule_id} {entry.file.as_posix()} "
                f"[{entry.text!r}] "
                f"{'actionable' if entry.actionable else 'detection-only'}"
            )
        for entry in text_report.entries:
            cli.display_text(
                f"sed: {entry.rule_id} {entry.file.as_posix()}:{entry.line} "
                f"[{entry.text!r}]"
            )
        cli.display_text(
            f"ast: scanned {len(rules)} rule file(s) from "
            f"{len(planned.value.rulesets)} provider(s); "
            f"{ast_report.findings} ast-grep finding(s) "
            f"({ast_report.actionable} actionable), "
            f"{text_report.findings} sed-by-list finding(s) "
            f"({text_report.actionable} actionable)"
        )
        if ast_report.findings or text_report.findings:
            return r[t.Cli.ResultValue].fail(
                f"{ast_report.findings} ast-grep finding(s) "
                f"({ast_report.actionable} actionable, "
                f"{ast_report.detection_only} detection-only) plus "
                f"{text_report.findings} sed-by-list finding(s) "
                f"({text_report.actionable} actionable)"
            )
        cli.display_text("ast: zero findings in both cascades")
        return r[t.Cli.ResultValue].ok(True)

    @classmethod
    def _execute_apply(
        cls, root: Path, rules: t.SequenceOf[Path]
    ) -> p.Result[t.Cli.ResultValue]:
        """Drive both mechanical cascades to a fixed point, retaining failures."""
        cli.display_text("ast: validate ast-grep rule fixtures")
        FlextInfraModGateEngine.validate_rule_fixtures(root, rules).unwrap()
        current = FlextInfraModGateEngine.scan(root, fix=False).unwrap()
        seen: set[t.VariadicTuple[t.Quad[str, str, str, str | None]]] = set()
        iteration = 0
        while current.actionable:
            iteration += 1
            fingerprint = tuple(
                sorted(
                    (
                        finding.rule_id,
                        finding.file.as_posix(),
                        finding.text,
                        finding.replacement,
                    )
                    for finding in current.entries
                    if finding.actionable
                )
            )
            if fingerprint in seen:
                return r[t.Cli.ResultValue].fail(
                    f"ast apply iteration {iteration} made no progress; "
                    "changes retained for mandatory owner repair"
                )
            seen.add(fingerprint)
            cli.display_text(f"ast: apply iteration {iteration}")
            FlextInfraModGateEngine.scan(root, fix=True).unwrap()
            current = FlextInfraModGateEngine.scan(root, fix=False).unwrap()
        text = FlextInfraModTextGateEngine.scan(
            root, fix=False, validate_receipts=True
        ).unwrap()
        while text.actionable:
            cli.display_text("ast: apply sed-by-list cascade")
            FlextInfraModTextGateEngine.scan(root, fix=True).unwrap()
            text = FlextInfraModTextGateEngine.scan(
                root, fix=False, validate_receipts=True
            ).unwrap()
        remaining_ast = FlextInfraModGateEngine.scan(root, fix=False).unwrap()
        if remaining_ast.actionable or text.findings:
            return r[t.Cli.ResultValue].fail(
                f"ast fixed point retains findings: {remaining_ast.findings} "
                f"ast-grep ({remaining_ast.actionable} actionable), "
                f"{text.findings} sed-by-list; run make mod for the "
                "semantic phases"
            )
        cli.display_text("ast: mechanical fixed point verified")
        return r[t.Cli.ResultValue].ok(True)


__all__: list[str] = ["FlextInfraCodemodAstScan"]
