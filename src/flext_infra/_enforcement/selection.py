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

    @staticmethod
    def canonical_catalog() -> m.EnforcementCatalog:
        """Return the canonical flext-core enforcement catalog."""
        return u.build_canonical_catalog()

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

    @classmethod
    def rule_requires_stub_file(cls, rule: m.EnforcementRuleSpec) -> bool:
        """Return whether ``rule`` needs explicit ``.pyi`` file discovery."""
        source = rule.source
        required: bool = t.Infra.BOOL_ADAPTER.validate_python(
            source.kind == "flext_infra_detector"
            and source.violation_field == cls._STUB_VIOLATION_FIELD
        )
        return required


__all__: list[str] = ["FlextInfraEnforcementSelection"]
