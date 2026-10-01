"""Census per-module rule dispatch — extracted concern."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import m

from .._enforcement.engine import FlextInfraEnforcementEngine
from ._census_rules_shared import FlextInfraRefactorCensusRulesSharedMixin

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraRefactorCensusRulesDispatchMixin(
    FlextInfraRefactorCensusRulesSharedMixin,
):
    """Run every selected structural rule for one module and collect outcomes.

    Parent of FlextInfraRefactorCensusCollectMixin (its ``_scan_module`` calls
    ``_module_rules``); borrows the rule-selection filter and the per-rule
    detectors from sibling mixins via FLEXT.
    """

    if TYPE_CHECKING:

        @staticmethod
        def _include_rule(
            rule: str,
            *,
            rule_names: t.StrSequence | None,
            selected_rules: frozenset[str] | None = None,
        ) -> bool: ...
        def _rule_runtime_alias(
            self,
            scan: m.Infra.ModuleScan,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...
        def _rule_manual_typing_alias(
            self,
            scan: m.Infra.ModuleScan,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...
        def _rule_class_placement(
            self,
            scan: m.Infra.ModuleScan,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...
        def _rule_private_import_bypass(
            self,
            scan: m.Infra.ModuleScan,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...
        def _rule_compatibility_alias(
            self,
            scan: m.Infra.ModuleScan,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...
        def _rule_inline_import(
            self,
            scan: m.Infra.ModuleScan,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...
        def _rule_silent_failure(
            self,
            scan: m.Infra.ModuleScan,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...

    def _module_rules(
        self,
        scan: m.Infra.ModuleScan,
    ) -> t.Pair[t.VariadicTuple[m.Infra.Violation], t.VariadicTuple[m.Infra.Fix]]:
        """Run every selected structural rule for one module and collect outcomes."""
        violations: list[m.Infra.Violation] = []
        fixes: list[m.Infra.Fix] = []
        rules: t.VariadicTuple[t.Pair[str, p.Infra.CensusModuleRule]] = (
            ("runtime_alias", self._rule_runtime_alias),
            ("manual_typing_alias", self._rule_manual_typing_alias),
            ("class_placement", self._rule_class_placement),
            ("private_import_bypass", self._rule_private_import_bypass),
            ("compatibility_alias", self._rule_compatibility_alias),
            ("inline_import", self._rule_inline_import),
            ("silent_failure", self._rule_silent_failure),
        )
        for rule_name, rule in rules:
            if not self._include_rule(
                rule_name,
                rule_names=scan.scan_config.rule_names,
                selected_rules=scan.scan_config.selected_rules,
            ):
                continue
            rule_violations, rule_fixes = rule(scan)
            violations.extend(rule_violations)
            fixes.extend(rule_fixes)
        declarative_violations, declarative_fixes = self._rule_declarative(scan)
        violations.extend(declarative_violations)
        fixes.extend(declarative_fixes)
        return (tuple(violations), tuple(fixes))

    @staticmethod
    def _declarative_catalog_rules() -> t.VariadicTuple[m.EnforcementRuleSpec]:
        """Return enabled catalog rules handled by the declarative engine."""
        return FlextInfraEnforcementEngine.declarative_rules()

    def _rule_declarative(
        self,
        scan: m.Infra.ModuleScan,
    ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]:
        """Run catalog-driven declarative rules for one module."""
        violations: list[m.Infra.Violation] = []
        fixes: list[m.Infra.Fix] = []
        rules = self._declarative_catalog_rules()
        if not rules:
            return violations, fixes
        ctx = self._detector_context(
            scan.rope,
            scan.file_path,
            convention=scan.convention,
        )
        selected_kinds = scan.scan_config.selected_kinds
        for rule in rules:
            if not self._include_rule(
                rule.id,
                rule_names=scan.scan_config.rule_names,
                selected_rules=scan.scan_config.selected_rules,
            ):
                continue
            kind = FlextInfraEnforcementEngine.violation_kind(rule)
            object_kind = FlextInfraEnforcementEngine.object_kind(kind)
            if selected_kinds and kind not in selected_kinds:
                continue
            probes = FlextInfraEnforcementEngine.detect_declarative(rule, ctx)
            fix_action = rule.fix_action
            fixable = fix_action is not None and fix_action.safe
            action = fix_action.target if fix_action is not None else ""
            for probe in probes:
                line = getattr(probe, "line", 0)
                if not isinstance(line, int) or line < 0:
                    line = 0
                object_name = FlextInfraEnforcementEngine.object_name(probe, kind)
                description = FlextInfraEnforcementEngine.description(
                    rule,
                    probe,
                    object_name,
                )
                violations.append(
                    m.Infra.Violation(
                        project=scan.project,
                        object_name=object_name,
                        object_kind=object_kind,
                        kind=kind,
                        file_path=str(scan.file_path),
                        line=line,
                        description=description,
                        fixable=fixable,
                        fix_action=action,
                    ),
                )
                if action:
                    fixes.append(
                        m.Infra.Fix(
                            object_name=object_name,
                            action=action,
                            source_file=str(scan.file_path),
                            files_changed=1,
                            applied=self._fix_key(scan.file_path, object_name, action)
                            in scan.scan_config.applied,
                        ),
                    )
        return violations, fixes


__all__: list[str] = ["FlextInfraRefactorCensusRulesDispatchMixin"]
