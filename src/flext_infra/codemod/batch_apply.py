"""Fix-forward ast-grep batch application for ``make mod``."""

from __future__ import annotations

from pathlib import Path
from typing import override

from flext_cli import cli

from flext_core import r

from .. import FlextInfraConfig, FlextInfraServiceBase, m, p, t, u
from . import (
    FlextInfraApplyRenames,
    FlextInfraCodemodSemanticApply,
    FlextInfraModGateEngine,
    FlextInfraModTextGateEngine,
)
from .batch_replacements import FlextInfraModReplacements


class FlextInfraCodemodBatchApply(FlextInfraServiceBase[t.Cli.ResultValue]):
    """Apply every discovered AST rewrite without destructive rollback."""

    @override
    def execute(self) -> p.Result[t.Cli.ResultValue]:
        """Inspect or apply the complete rule cascade with visible phases."""
        planned = u.Infra.codemod_rule_plan(self.repository_root)
        if planned.failure:
            return r[t.Cli.ResultValue].from_failure(planned)
        rules = tuple(dict.fromkeys(rule.resource for rule in planned.value.rules))
        if self.effective_dry_run:
            cli.display_text(f"mod: scan {len(rules)} discovered rule file(s)")
            pending = FlextInfraModGateEngine.scan(
                self.repository_root, fix=False
            ).unwrap()
            pending_count = pending.findings
            text_pending = FlextInfraModTextGateEngine.scan(
                self.repository_root, fix=False, validate_receipts=True
            ).unwrap()
            pending_count += text_pending.findings
            renames_pending = FlextInfraCodemodBatchApply._pending_renames(
                self.repository_root
            )
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
                    f"across {len(rules)} rule file(s)"
                )
            validated = FlextInfraModGateEngine.validate(self.repository_root)
            if validated.failure:
                return r[t.Cli.ResultValue].from_failure(validated)
            cli.display_text("mod: no pending ast-grep or sed-by-list fixes")
            return r[t.Cli.ResultValue].ok(True)
        return self._execute_apply(self.repository_root, rules)

    @staticmethod
    def _execute_apply(
        root: Path, rules: t.SequenceOf[Path]
    ) -> p.Result[t.Cli.ResultValue]:
        """Converge AST, semantic, and text phases over the same source state."""
        cli.display_text("mod: validate ast-grep rule fixtures")
        FlextInfraModGateEngine.validate_rule_fixtures(root, rules).unwrap()
        current = FlextInfraModGateEngine.scan(root, fix=False).unwrap()
        fingerprint = FlextInfraCodemodSemanticApply.source_fingerprint
        seen: dict[t.VariadicTuple[t.Pair[str, str]], int] = {}
        iteration = 0
        text_precondition_pending = True
        while True:
            iteration += 1
            before = fingerprint(root, current)
            if before in seen:
                return r[t.Cli.ResultValue].fail(
                    f"mod cross-phase cycle at iteration {iteration}; "
                    f"source state repeats iteration {seen[before]}; "
                    "changes retained for mandatory owner repair"
                )
            seen[before] = iteration
            cli.display_text(
                f"mod: joint iteration {iteration} — "
                f"{current.actionable} actionable, "
                f"{current.detection_only} detection-only"
            )
            if current.actionable:
                FlextInfraModGateEngine.scan(root, fix=True).unwrap()
            after_ast = FlextInfraModGateEngine.scan(root, fix=False).unwrap()
            FlextInfraCodemodBatchApply.validate_fix_match(current, after_ast)
            phase_states = [fingerprint(root, after_ast)]
            transaction_paths = FlextInfraCodemodSemanticApply.plan_transaction_paths(
                root, after_ast
            )
            if transaction_paths:
                FlextInfraCodemodSemanticApply.apply_transaction_paths(
                    root, transaction_paths
                )
                after_ast = FlextInfraModGateEngine.scan(root, fix=False).unwrap()
            phase_states.append(fingerprint(root, after_ast))
            owned = FlextInfraModReplacements.require_authored(after_ast)
            if owned.failure:
                return r[t.Cli.ResultValue].from_failure(owned)
            # Detection-only findings and configured import alignment select
            # semantic work even when no AST rule has a textual replacement.
            semantic = FlextInfraCodemodSemanticApply.apply(root, after_ast)
            if semantic.failure:
                return r[t.Cli.ResultValue].from_failure(semantic)
            phase_states.append(fingerprint(root, after_ast))
            current_text = FlextInfraModTextGateEngine.scan(
                root, fix=False, validate_receipts=text_precondition_pending
            ).unwrap()
            if current_text.actionable:
                applied = FlextInfraModTextGateEngine.scan(
                    root, fix=True, validate_receipts=text_precondition_pending
                )
                if applied.failure:
                    return r[t.Cli.ResultValue].from_failure(applied)
            # Exact optional migration receipts apply once per invocation,
            # not to every internal convergence pass after consuming matches.
            text_precondition_pending = False
            configured_renames = FlextInfraCodemodBatchApply._rename_inputs(
                root, apply=True
            )
            for rename_params in configured_renames:
                renamed = FlextInfraApplyRenames.run(rename_params)
                if renamed.failure:
                    return r[t.Cli.ResultValue].from_failure(renamed)
            current = FlextInfraModGateEngine.scan(root, fix=False).unwrap()
            current_text = FlextInfraModTextGateEngine.scan(root, fix=False).unwrap()
            after = fingerprint(root, current)
            if after != before:
                continue
            if any(state != before for state in phase_states):
                return r[t.Cli.ResultValue].fail(
                    "mod cross-phase cycle returned to its starting source state; "
                    "changes retained for mandatory owner repair"
                )
            if current.actionable or current_text.actionable:
                return r[t.Cli.ResultValue].fail(
                    "mod made no progress with "
                    f"{current.actionable} AST and {current_text.actionable} text "
                    "actionable findings; changes retained for mandatory owner repair"
                )
            cli.display_text(
                "mod: require canonical formatting and zero Ruff, Pyrefly, and LSP diagnostics"
            )
            validated = FlextInfraModGateEngine.validate(root)
            if validated.failure:
                return r[t.Cli.ResultValue].from_failure(validated)
            current = FlextInfraModGateEngine.scan(root, fix=False).unwrap()
            current_text = FlextInfraModTextGateEngine.scan(root, fix=False).unwrap()
            if (
                fingerprint(root, current) != after
                or current.actionable
                or current_text.actionable
            ):
                continue
            # Repair reports non-rewritable defects; check owns their verdict.
            if current.detection_only or current.non_actionable_with_fix:
                detection_rules = sorted({
                    finding.rule_id
                    for finding in current.entries
                    if not finding.actionable
                })
                cli.display_text(
                    f"mod: {current.detection_only} detection-only and "
                    f"{current.non_actionable_with_fix} non-actionable with fix "
                    f"finding(s) remain for owner repair: {', '.join(detection_rules)}"
                )
            if current_text.findings:
                text_rules = sorted({entry.rule_id for entry in current_text.entries})
                cli.display_text(
                    f"mod: {current_text.findings} detection-only sed-by-list "
                    f"finding(s) remain for owner repair: {', '.join(text_rules)}"
                )
            cli.display_text(
                "mod: joint AST, semantic, and text fixed point verified "
                "with zero actionable findings"
            )
            return r[t.Cli.ResultValue].ok(True)

    @staticmethod
    def _rename_inputs(
        root: Path, *, apply: bool
    ) -> t.SequenceOf[m.Infra.ApplyRenamesInput]:
        """Resolve configured rename campaigns into engine inputs anchored at root.

        The rename list is resolved against the config directory that declares
        it, which ships inside the package: every consumer repository applies
        the same list without carrying a copy. Scan roots stay
        repository-root-relative because they select the tree being rewritten.
        """
        campaigns = (
            FlextInfraConfig.fetch_global().Infra.refactor_csv_campaigns.campaigns
        )
        config_dir = FlextInfraConfig.ssot_config_dir()
        inputs: list[m.Infra.ApplyRenamesInput] = []
        for campaign in campaigns:
            csv_declared = Path(campaign.csv)
            csv = (
                csv_declared
                if csv_declared.is_absolute()
                else config_dir / csv_declared
            )
            roots = tuple(
                str(path if path.is_absolute() else root / path)
                for path in (Path(value) for value in campaign.roots)
            )
            inputs.append(
                m.Infra.ApplyRenamesInput(
                    csv=str(csv), roots=roots or (str(root),), apply=apply
                )
            )
        return tuple(inputs)

    @staticmethod
    def _pending_renames(root: Path) -> p.Result[int]:
        """Count pending rename occurrences across the configured campaigns."""
        pending = 0
        for params in FlextInfraCodemodBatchApply._rename_inputs(root, apply=False):
            report = FlextInfraApplyRenames.run(params)
            if report.failure:
                return r[int].from_failure(report)
            pending += report.value.occurrences
        return r[int].ok(pending)

    @staticmethod
    def validate_fix_match(
        before: m.Infra.ModScanReport, after_apply: m.Infra.ModScanReport
    ) -> None:
        """Reject unresolved rewrites while preserving valid rule cascades."""
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
                f"fix!=match: ast-grep apply did not resolve {len(unresolved)} expected actionable "
                f"findings in rules {sorted(rule_ids)} across files {sorted(files)}"
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
                f"fix!=match: ast-grep apply introduced {len(unexpected)} new actionable "
                f"findings in rules {sorted(rule_ids)} across files {sorted(files)}"
            )
            raise RuntimeError(msg)


__all__: list[str] = ["FlextInfraCodemodBatchApply"]
