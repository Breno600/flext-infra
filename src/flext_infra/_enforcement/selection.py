"""Catalog selection helpers for enforcement flows."""

from __future__ import annotations

from typing import ClassVar

from flext_infra import m, t, u
from flext_infra.refactor.declarative_enforcement import (
    FlextInfraRefactorDeclarativeEnforcement,
)


class FlextInfraEnforcementSelection:
    """Catalog-backed rule selection from the flext-core SSOT."""

    _STUB_VIOLATION_FIELD: ClassVar[str] = "stub_file_violations"

    _TESTS_TIER_SOURCE_KINDS: ClassVar[t.StrSequence] = ("flext_tests_validator",)
    """Source kinds owned by the flext-tests pytest enforcement dispatcher.

    ``tv.<method>`` validators execute inside flext-tests (the declared
    dependency direction is tests -> infra); flext-infra never imports
    ``flext_tests`` at runtime, so the infra engine neither collects nor
    fixes these rules — the pytest tier gates them.
    """

    @staticmethod
    def canonical_catalog() -> m.EnforcementCatalog:
        """Return the canonical flext-core enforcement catalog."""
        catalog: m.EnforcementCatalog = u.build_canonical_catalog()
        return catalog

    @classmethod
    def selected_rules(
        cls,
        *,
        catalog: m.EnforcementCatalog | None = None,
        wanted: t.StrSequence = (),
        safe_only: bool = True,
    ) -> t.VariadicTuple[m.EnforcementRuleSpec]:
        """Return enabled fixable rules selected for fixer execution.

        Tests-tier source kinds are excluded: their execution owner is the
        flext-tests pytest dispatcher, not the infra engine. An explicit
        request for one fails loud naming the tier owner.
        """
        wanted_ids = frozenset(wanted)
        rule_catalog = catalog or cls.canonical_catalog()
        tests_tier_kinds = frozenset(cls._TESTS_TIER_SOURCE_KINDS)
        fixable = tuple(
            rule
            for rule in rule_catalog.enabled_rules()
            if rule.fix_action is not None and (not wanted_ids or rule.id in wanted_ids)
        )
        tests_tier = [rule for rule in fixable if rule.source.kind in tests_tier_kinds]
        if wanted_ids and tests_tier:
            msg = (
                "Requested rules are owned by the flext-tests pytest tier "
                "(flext-infra never imports flext_tests at runtime): "
                f"{', '.join(sorted(rule.id for rule in tests_tier))}"
            )
            raise ValueError(msg)
        candidates = tuple(
            rule for rule in fixable if rule.source.kind not in tests_tier_kinds
        )
        if wanted_ids:
            cls._validate_requested_rules(
                candidates, wanted_ids=wanted_ids, safe_only=safe_only
            )
        return tuple(
            rule
            for rule in candidates
            if rule.fix_action is not None and (not safe_only or rule.fix_action.safe)
        )

    @staticmethod
    def declarative_rules(
        rule_names: t.StrSequence | None = None,
    ) -> t.VariadicTuple[m.EnforcementRuleSpec]:
        """Return enabled catalog rules handled by the declarative detector."""
        selected = frozenset(rule_names) if rule_names else None
        return tuple(
            rule
            for rule in FlextInfraEnforcementSelection.canonical_catalog().enabled_rules()
            if (selected is None or rule.id in selected)
            and FlextInfraRefactorDeclarativeEnforcement.supports(rule)
        )

    @staticmethod
    def supports_declarative(rule: m.EnforcementRuleSpec) -> bool:
        """Return whether the declarative detector supports ``rule``."""
        return FlextInfraRefactorDeclarativeEnforcement.supports(rule)

    @classmethod
    def rule_requires_stub_file(cls, rule: m.EnforcementRuleSpec) -> bool:
        """Return whether ``rule`` needs explicit ``.pyi`` file discovery."""
        source = rule.source
        required: bool = t.Infra.BOOL_ADAPTER.validate_python(
            source.kind == "flext_infra_detector"
            and source.violation_field == cls._STUB_VIOLATION_FIELD
        )
        return required

    @staticmethod
    def _validate_requested_rules(
        candidates: t.VariadicTuple[m.EnforcementRuleSpec],
        *,
        wanted_ids: frozenset[str],
        safe_only: bool,
    ) -> None:
        """Validate explicit rule selection and fail loud on impossible requests."""
        requested_ids = {rule.id for rule in candidates}
        missing = wanted_ids - requested_ids
        if missing:
            msg = (
                "Requested rules are not enabled or have no fix action: "
                f"{', '.join(sorted(missing))}"
            )
            raise ValueError(msg)
        if safe_only:
            unsafe = {
                rule.id
                for rule in candidates
                if rule.fix_action is not None and not rule.fix_action.safe
            }
            if unsafe:
                msg = (
                    "Requested rules are unsafe under --safe-only: "
                    f"{', '.join(sorted(unsafe))}"
                )
                raise ValueError(msg)


__all__: list[str] = ["FlextInfraEnforcementSelection"]
