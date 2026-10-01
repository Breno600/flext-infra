"""Audit request contracts reject retired permissive controls at ingress."""

from __future__ import annotations

import pytest
from flext_tests import tm

from flext_infra.docs.auditor import FlextInfraDocAuditor
from tests import c, m


class TestsFlextInfraAuditorContract:
    """The typed owner has no budget or optional strict-mode contract."""

    def test_default_request_has_no_permissive_controls(self) -> None:
        params = m.Infra.AuditScopeParams()
        tm.that(params.check, eq="all")
        tm.that(params.docstring_min, none=True)
        tm.that("budgets" in params.model_dump(), eq=False)
        tm.that("strict" in params.model_dump(), eq=False)
        tm.that("strict_mode" in FlextInfraDocAuditor.model_fields, eq=False)

    @pytest.mark.parametrize("strict", [False, True])
    def test_retired_strict_control_is_rejected(self, *, strict: bool) -> None:
        with pytest.raises(c.ValidationError, match="strict"):
            m.Infra.AuditScopeParams.model_validate({"strict": strict})

    def test_invalid_json_fails_at_request_ingress(self) -> None:
        with pytest.raises(c.ValidationError, match="Invalid JSON"):
            m.Infra.AuditScopeParams.model_validate_json("{invalid json}")

    @pytest.mark.parametrize("budget", [0, 5, 5.5])
    def test_default_and_scope_budgets_are_rejected(self, budget: float) -> None:
        with pytest.raises(c.ValidationError, match="budgets"):
            m.Infra.AuditScopeParams.model_validate({
                "budgets": (budget, {"test-project": budget})
            })

    def test_scope_budget_without_default_is_rejected(self) -> None:
        with pytest.raises(c.ValidationError, match="budgets"):
            m.Infra.AuditScopeParams.model_validate({
                "budgets": (None, {"test-project": 3})
            })
