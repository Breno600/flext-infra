"""Fix-forward ast-grep batch application for ``make mod``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import override

from flext_infra import FlextInfraServiceBase, m, p, r, t, u
from flext_infra.codemod import (
    FlextInfraCodemodSemanticApply,
    FlextInfraModGateEngine,
    FlextInfraModTextGateEngine,
)
from flext_infra.codemod.batch_replacements import FlextInfraModReplacements


class FlextInfraCodemodBatchApply(FlextInfraServiceBase[t.Cli.ResultValue]):
    """Apply every discovered AST rewrite without destructive rollback."""

    rename_runner: t.Port[p.Infra.RenameCampaignRunner] = m.Field(
        exclude=True,
        description="Injected CSV campaign execution port",
    )
    progress: t.Port[p.Infra.ModProgress] = m.Field(
        exclude=True,
        description="Injected mod progress transport port",
    )
    rope: t.Port[p.Infra.RopeWorkspaceDsl] = m.Field(
        exclude=True,
        description="Injected Rope workspace port",
    )
    rename_inputs: t.VariadicTuple[m.Infra.ApplyRenamesInput] = m.Field(
        exclude=True,
        default=(),
        description="Typed declared CSV campaigns",
    )

    @override
    def execute(self) -> p.Result[t.Cli.ResultValue]:
        """Inspect or apply the complete rule cascade with visible phases.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        planned = u.Infra.codemod_rule_plan(self.repository_root)
        if planned.failure:
            return r[t.Cli.ResultValue].from_failure(planned)
        rules = tuple(dict.fromkeys(rule.resource for rule in planned.value.rules))
        if self.effective_dry_run:
            self.progress.emit(f"mod: scan {len(rules)} discovered rule file(s)")
            pending = FlextInfraModGateEngine.scan(
                self.repository_root,
                fix=False,
            ).unwrap()
            pending_count = pending.findings
            text_pending = FlextInfraModTextGateEngine.scan(
                self.repository_root,
                fix=False,
                validate_receipts=True,
            ).unwrap()
            pending_count += text_pending.findings
            renames_pending = self._pending_renames()
            if renames_pending.failure:
                return r[t.Cli.ResultValue].from_failure(renames_pending)
            if pending_count or renames_pending.value:
                return r[t.Cli.ResultValue].fail(
                    f"{pending.findings} pending ast-grep finding(s), "
                    f"{pending.actionable} actionable and "
                    f"{pending.detection_only} detection-only and "
                    f"{pending.non_actionable_with_fix} non-actionable with fix, plus "
                    f"{text_pending.findings} pending sed-by-list finding(s) "
                    f"({text_pending.actionable} actionable) and "
                    f"{renames_pending.value} pending CSV-rename occurrence(s), "
                    f"across {len(rules)} rule file(s)",
                )
            self.progress.emit("mod: no pending ast-grep or sed-by-list fixes")
            return r[t.Cli.ResultValue].ok(value=True)
        return self._execute_apply(rules)

    def _execute_apply(self, rules: t.SequenceOf[Path]) -> p.Result[t.Cli.ResultValue]:
        """Converge AST, semantic, and text phases over the same source state.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        self.progress.emit("mod: validate ast-grep rule fixtures")
        FlextInfraModGateEngine.validate_rule_fixtures(
            self.repository_root,
            rules,
        ).unwrap()
        return self._execute_apply_cycle()

    def _execute_apply_cycle(self) -> p.Result[t.Cli.ResultValue]:
        """Converge every mod phase through one shared Rope workspace.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        root = self.repository_root
        rope_workspace = self.rope
        current = FlextInfraModGateEngine.scan(root, fix=False).unwrap()
        fingerprint = FlextInfraCodemodSemanticApply.source_fingerprint
        seen: MutableMapping[t.VariadicTuple[t.Pair[str, str]], int] = {}
        iteration = 0
        text_precondition_pending = True
        while True:
            iteration += 1
            before = fingerprint(root, current)
            if before in seen:
                return r[t.Cli.ResultValue].fail(
                    f"mod cross-phase cycle at iteration {iteration}; "
                    f"source state repeats iteration {seen[before]}; "
                    "changes retained for mandatory owner repair",
                )
            seen[before] = iteration
            self.progress.emit(
                f"mod: joint iteration {iteration} — "
                f"{current.actionable} actionable, "
                f"{current.detection_only} detection-only",
            )
            after_ast = current
            if current.actionable:
                FlextInfraModGateEngine.scan(root, fix=True).unwrap()
                rope_workspace.refresh()
                after_ast = FlextInfraModGateEngine.scan(root, fix=False).unwrap()
            self.validate_fix_match(current, after_ast)
            phase_states = [fingerprint(root, after_ast)]
            transaction_paths = FlextInfraCodemodSemanticApply.plan_transaction_paths(
                root,
                after_ast,
                rope_workspace,
            )
            if transaction_paths:
                FlextInfraCodemodSemanticApply.apply_transaction_paths(
                    root,
                    transaction_paths,
                )
                rope_workspace.refresh()
                after_ast = FlextInfraModGateEngine.scan(root, fix=False).unwrap()
            phase_states.append(fingerprint(root, after_ast))
            # Detection-only findings and configured import alignment select
            # semantic work even when no AST rule has a textual replacement.
            # A generated source is never a semantic target: its findings are
            # its generator's, judged once the authored sources converge.
            semantic = FlextInfraCodemodSemanticApply.apply(
                root,
                FlextInfraModGateEngine.authored(after_ast),
                rope_workspace,
            )
            if semantic.failure:
                return r[t.Cli.ResultValue].from_failure(semantic)
            phase_states.append(fingerprint(root, after_ast))
            current_text = FlextInfraModTextGateEngine.scan(
                root,
                fix=False,
                validate_receipts=text_precondition_pending,
            ).unwrap()
            if current_text.actionable:
                applied = FlextInfraModTextGateEngine.scan(
                    root,
                    fix=True,
                    validate_receipts=text_precondition_pending,
                )
                if applied.failure:
                    return r[t.Cli.ResultValue].from_failure(applied)
            # Exact optional migration receipts apply once per invocation,
            # not to every internal convergence pass after consuming matches.
            text_precondition_pending = False
            for rename_params in self.rename_inputs:
                renamed = self.rename_runner.run(rename_params)
                if renamed.failure:
                    return r[t.Cli.ResultValue].from_failure(renamed)
                self.progress.emit_rename(renamed.value)
            current = FlextInfraModGateEngine.scan(root, fix=False).unwrap()
            current_text = FlextInfraModTextGateEngine.scan(root, fix=False).unwrap()
            after = fingerprint(root, current)
            if after != before:
                continue
            if any(state != before for state in phase_states):
                return r[t.Cli.ResultValue].fail(
                    "mod cross-phase cycle returned to its starting source state; "
                    "changes retained for mandatory owner repair",
                )
            if current.actionable or current_text.actionable:
                return r[t.Cli.ResultValue].fail(
                    "mod made no progress with "
                    f"{current.actionable} AST and {current_text.actionable} text "
                    "actionable findings; changes retained for mandatory owner repair",
                )
            # Repair reports what it cannot own; check owns every verdict. A
            # generated file is never written here: its findings are repaired
            # by the canonical generator (make gen), never a reason for this
            # repair verb to fail (operator ruling 2026-10-02: repair verbs
            # never deadlock).
            generated = FlextInfraModReplacements.generator_owned(current.entries)
            if generated:
                self.progress.emit(
                    f"mod: {len(generated)} generated finding(s) remain for "
                    f"canonical generator repair: {', '.join(generated)}",
                )
            # Ruff, Pyrefly and Pyright findings are check's alone.
            if current.detection_only or current.non_actionable_with_fix:
                detection_rules = sorted({
                    finding.rule_id
                    for finding in current.entries
                    if not finding.actionable
                })
                self.progress.emit(
                    f"mod: {current.detection_only} detection-only and "
                    f"{current.non_actionable_with_fix} non-actionable with fix "
                    f"finding(s) remain for owner repair: {', '.join(detection_rules)}",
                )
            if current_text.findings:
                text_rules = sorted({entry.rule_id for entry in current_text.entries})
                self.progress.emit(
                    f"mod: {current_text.findings} detection-only sed-by-list "
                    f"finding(s) remain for owner repair: {', '.join(text_rules)}",
                )
            self.progress.emit(
                "mod: joint AST, semantic, and text fixed point verified "
                "with zero actionable findings",
            )
            return r[t.Cli.ResultValue].ok(value=True)

    def _pending_renames(self) -> p.Result[int]:
        """Count pending rename occurrences across the configured campaigns.

        Returns:
            The resulting ``p.Result[int]``.

        """
        pending = 0
        for params in self.rename_inputs:
            report = self.rename_runner.run(params)
            if report.failure:
                return r[int].from_failure(report)
            pending += report.value.occurrences
        return r[int].ok(pending)

    @staticmethod
    def validate_fix_match(
        before: m.Infra.ModScanReport,
        after_apply: m.Infra.ModScanReport,
    ) -> None:
        """Reject unresolved rewrites while preserving valid rule cascades.

        Raises:
            RuntimeError: If fix!=match.

        """
        # Check that actionable findings were actually resolved
        before_actionable = {
            (f.rule_id, f.file.as_posix(), f.text, f.replacement)
            for f in before.entries
            if f.actionable
        }
        after_apply_actionable = {
            (f.rule_id, f.file.as_posix(), f.text, f.replacement)
            for f in after_apply.entries
            if f.actionable
        }
        # Actionable findings should be resolved
        unresolved = before_actionable & after_apply_actionable
        if unresolved:
            rule_ids = {r for r, _, _, _ in unresolved}
            files = {p for _, p, _, _ in unresolved}
            msg = (
                f"fix!=match: ast-grep apply did not resolve {len(unresolved)} "
                f"actionable findings in rules {sorted(rule_ids)} "
                f"across files {sorted(files)}"
            )
            raise RuntimeError(msg)
        # A completed rule may enable a later rule in the declared cascade.
        # Those later-rule findings are consumed by the next fixed-point iteration.
        new_actionable = after_apply_actionable - before_actionable
        prior_rule_ids = {rule_id for rule_id, _, _, _ in before_actionable}
        unexpected = {
            finding for finding in new_actionable if finding[0] in prior_rule_ids
        }
        if unexpected:
            rule_ids = {r for r, _, _, _ in unexpected}
            files = {p for _, p, _, _ in unexpected}
            msg = (
                f"fix!=match: ast-grep apply introduced {len(unexpected)} new "
                f"actionable findings in rules {sorted(rule_ids)} "
                f"across files {sorted(files)}"
            )
            raise RuntimeError(msg)


__all__: list[str] = ["FlextInfraCodemodBatchApply"]
