"""Census per-module rule dispatch — extracted concern."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import m

from .._enforcement.engine import FlextInfraEnforcementEngine
from ._census_rules_shared import FlextInfraRefactorCensusRulesSharedMixin

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraRefactorCensusRulesDispatchMixin(
    FlextInfraRefactorCensusRulesSharedMixin
):
    """Run every selected structural rule for one module and collect outcomes.

    Parent of FlextInfraRefactorCensusCollectMixin (its ``_scan_module`` calls
    ``_module_rules``); borrows the symbol-index, rule-selection filter, and
    the four per-rule detectors from sibling mixins via FLEXT.
    """

    if TYPE_CHECKING:

        @classmethod
        def _lightweight_symbol_index(
            cls, rope: p.Infra.RopeWorkspaceDsl, file_path: Path
        ) -> MutableMapping[str, t.Pair[str, int]]: ...
        @staticmethod
        def _include_rule(
            rule: str,
            *,
            rule_names: t.StrSequence | None,
            selected_rules: frozenset[str] | None = None,
        ) -> bool: ...
        def _rule_runtime_alias(
            self,
            rope: p.Infra.RopeWorkspaceDsl,
            file_path: Path,
            *,
            project_name: str,
            objects: t.VariadicTuple[m.Infra.Object] | None,
            applied: frozenset[str],
            selected_kinds: frozenset[str],
            symbol_index: t.MappingKV[str, t.Pair[str, int]],
            convention: m.Infra.RopeModuleConvention,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...
        def _rule_manual_typing_alias(
            self,
            rope: p.Infra.RopeWorkspaceDsl,
            file_path: Path,
            *,
            project_name: str,
            objects: t.VariadicTuple[m.Infra.Object] | None,
            applied: frozenset[str],
            selected_kinds: frozenset[str],
            convention: m.Infra.RopeModuleConvention,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...
        def _rule_class_placement(
            self,
            rope: p.Infra.RopeWorkspaceDsl,
            file_path: Path,
            *,
            project_name: str,
            objects: t.VariadicTuple[m.Infra.Object] | None,
            applied: frozenset[str],
            selected_kinds: frozenset[str],
            symbol_index: t.MappingKV[str, t.Pair[str, int]],
            convention: m.Infra.RopeModuleConvention,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...
        def _rule_private_import_bypass(
            self,
            rope: p.Infra.RopeWorkspaceDsl,
            file_path: Path,
            *,
            project_name: str,
            objects: t.VariadicTuple[m.Infra.Object] | None,
            applied: frozenset[str],
            selected_kinds: frozenset[str],
            symbol_index: t.MappingKV[str, t.Pair[str, int]],
            convention: m.Infra.RopeModuleConvention,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...
        def _rule_compatibility_alias(
            self,
            rope: p.Infra.RopeWorkspaceDsl,
            file_path: Path,
            *,
            project_name: str,
            objects: t.VariadicTuple[m.Infra.Object] | None,
            applied: frozenset[str],
            selected_kinds: frozenset[str],
            symbol_index: t.MappingKV[str, t.Pair[str, int]],
            convention: m.Infra.RopeModuleConvention,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...
        def _rule_inline_import(
            self,
            rope: p.Infra.RopeWorkspaceDsl,
            file_path: Path,
            *,
            project_name: str,
            objects: t.VariadicTuple[m.Infra.Object] | None,
            applied: frozenset[str],
            selected_kinds: frozenset[str],
            symbol_index: t.MappingKV[str, t.Pair[str, int]],
            convention: m.Infra.RopeModuleConvention,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...
        def _rule_silent_failure(
            self,
            rope: p.Infra.RopeWorkspaceDsl,
            file_path: Path,
            *,
            project_name: str,
            objects: t.VariadicTuple[m.Infra.Object] | None,
            applied: frozenset[str],
            selected_kinds: frozenset[str],
            symbol_index: t.MappingKV[str, t.Pair[str, int]],
            convention: m.Infra.RopeModuleConvention,
        ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]: ...

    def _module_rules(
        self,
        rope: p.Infra.RopeWorkspaceDsl,
        file_path: Path,
        *,
        objects: t.VariadicTuple[m.Infra.Object] | None,
        project_name: str,
        scan_config: m.Infra.ScanConfig,
    ) -> t.Pair[t.VariadicTuple[m.Infra.Violation], t.VariadicTuple[m.Infra.Fix]]:
        """Run every selected structural rule for one module and collect outcomes."""
        resolved_convention = rope.convention(file_path)
        resolved_kinds = scan_config.selected_kinds or frozenset()
        symbol_index = self._lightweight_symbol_index(rope, file_path)
        violations: list[m.Infra.Violation] = []
        fixes: list[m.Infra.Fix] = []

        def selected(rule_name: str) -> bool:
            return self._include_rule(
                rule_name,
                rule_names=scan_config.rule_names,
                selected_rules=scan_config.selected_rules,
            )

        def run(rule_name: str, rule: p.Infra.CensusModuleRule) -> None:
            if not selected(rule_name):
                return
            rule_violations, rule_fixes = rule(
                rope,
                file_path,
                project_name=project_name,
                objects=objects,
                applied=scan_config.applied,
                selected_kinds=resolved_kinds,
                symbol_index=symbol_index,
                convention=resolved_convention,
            )
            violations.extend(rule_violations)
            fixes.extend(rule_fixes)

        run("runtime_alias", self._rule_runtime_alias)
        if selected("manual_typing_alias"):
            v, f = self._rule_manual_typing_alias(
                rope,
                file_path,
                project_name=project_name,
                objects=objects,
                applied=scan_config.applied,
                selected_kinds=resolved_kinds,
                convention=resolved_convention,
            )
            violations.extend(v)
            fixes.extend(f)
        run("class_placement", self._rule_class_placement)
        run("private_import_bypass", self._rule_private_import_bypass)
        run("compatibility_alias", self._rule_compatibility_alias)
        run("inline_import", self._rule_inline_import)
        run("silent_failure", self._rule_silent_failure)
        v, f = self._rule_declarative(
            rope,
            file_path,
            project_name=project_name,
            applied=scan_config.applied,
            selected_kinds=resolved_kinds,
            selected_rules=scan_config.selected_rules,
            rule_names=scan_config.rule_names,
            convention=resolved_convention,
        )
        violations.extend(v)
        fixes.extend(f)
        return (tuple(violations), tuple(fixes))

    @staticmethod
    def _declarative_catalog_rules() -> t.VariadicTuple[m.EnforcementRuleSpec]:
        """Return enabled catalog rules handled by the declarative engine."""
        return FlextInfraEnforcementEngine.declarative_rules()

    def _rule_declarative(
        self,
        rope: p.Infra.RopeWorkspaceDsl,
        file_path: Path,
        *,
        project_name: str,
        applied: frozenset[str],
        selected_kinds: frozenset[str],
        selected_rules: frozenset[str] | None,
        rule_names: t.StrSequence | None,
        convention: m.Infra.RopeModuleConvention,
    ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]:
        """Run catalog-driven declarative rules for one module."""
        violations: list[m.Infra.Violation] = []
        fixes: list[m.Infra.Fix] = []
        rules = self._declarative_catalog_rules()
        if not rules:
            return violations, fixes
        ctx = self._detector_context(rope, file_path, convention=convention)
        for rule in rules:
            if not self._include_rule(
                rule.id, rule_names=rule_names, selected_rules=selected_rules
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
                    rule, probe, object_name
                )
                violations.append(
                    self._raw_violation(
                        project=project_name,
                        object_name=object_name,
                        object_kind=object_kind,
                        kind=kind,
                        file_path=file_path,
                        line=line,
                        description=description,
                        fixable=fixable,
                        fix_action=action,
                    )
                )
                if action:
                    fixes.append(
                        m.Infra.Fix(
                            object_name=object_name,
                            action=action,
                            source_file=str(file_path),
                            files_changed=1,
                            applied=self._fix_key(file_path, object_name, action)
                            in applied,
                        )
                    )
        return violations, fixes


__all__: list[str] = ["FlextInfraRefactorCensusRulesDispatchMixin"]
