"""Audit request contracts reject retired permissive controls at ingress.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import pytest
from flext_tests import tm

from flext_infra.docs.auditor import FlextInfraDocAuditor
from tests import c, m


class TestsFlextInfraAuditorContract:
    """The typed owner has no budget or optional strict-mode contract."""

    @staticmethod
    def test_default_request_has_no_permissive_controls() -> None:
        """Test default request has no permissive controls."""
        params = m.Infra.AuditScopeParams()
        tm.that(params.check, eq="all")
        tm.that(params.docstring_min, none=True)
        tm.that("budgets" in params.model_dump(), eq=False)
        tm.that("strict" in params.model_dump(), eq=False)
        tm.that("strict_mode" in FlextInfraDocAuditor.model_fields, eq=False)

    @staticmethod
    @pytest.mark.parametrize("strict", [False, True])
<<<<<<< HEAD
    @staticmethod
=======
>>>>>>> origin/0.12.0-dev
    def test_retired_strict_control_is_rejected(*, strict: bool) -> None:
        """Test retired strict control is rejected."""
        with pytest.raises(c.ValidationError, match="strict"):
            m.Infra.AuditScopeParams.model_validate({"strict": strict})

    @staticmethod
    def test_invalid_json_fails_at_request_ingress() -> None:
        """Test invalid json fails at request ingress."""
        with pytest.raises(c.ValidationError, match="Invalid JSON"):
            m.Infra.AuditScopeParams.model_validate_json("{invalid json}")

    @staticmethod
    @pytest.mark.parametrize("budget", [0, 5, 5.5])
<<<<<<< HEAD
    @staticmethod
=======
>>>>>>> origin/0.12.0-dev
    def test_default_and_scope_budgets_are_rejected(budget: float) -> None:
        """Test default and scope budgets are rejected."""
        with pytest.raises(c.ValidationError, match="budgets"):
            m.Infra.AuditScopeParams.model_validate({
                "budgets": (budget, {"test-project": budget}),
            })

    @staticmethod
    def test_scope_budget_without_default_is_rejected() -> None:
        """Test scope budget without default is rejected."""
        with pytest.raises(c.ValidationError, match="budgets"):
            m.Infra.AuditScopeParams.model_validate({
                "budgets": (None, {"test-project": 3}),
            })
