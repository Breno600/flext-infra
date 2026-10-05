"""Validate fleet-mandatory Mypy policy through the typed YAML owner.

Pydantic 2 and its plugin remain mandatory. Configuration, not declaration
defaults, owns the selected policy; tests validate its public input contract.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import pytest
from flext_tests import tm

from flext_core import e
from flext_infra import config, m


class TestsMypyFleetMandatoryDefaults:
    """The selected SSOT policy survives validation and rejects weakening."""

    @staticmethod
    def test_selected_policy_round_trips() -> None:
        """The same typed SSOT supplies production and expected policy values."""
        policy = config.Infra.tooling.tools.mypy
        validated = m.Infra.MypyConfig.model_validate(policy.model_dump(by_alias=True))
        tm.that(tuple(validated.plugins), eq=tuple(policy.plugins))
        tm.that(
            tuple(validated.disable_error_code),
            eq=tuple(policy.disable_error_code),
        )

    @pytest.mark.parametrize("change", ["empty", "missing", "additional"])
    def test_selected_policy_rejects_unauthorized_suspensions(self, change: str) -> None:
        """No complete payload may remove a required code or suspend another."""
        payload = config.Infra.tooling.tools.mypy.model_dump(by_alias=True)
        codes = list(config.Infra.tooling.tools.mypy.disable_error_code)
        if change == "empty":
            codes.clear()
        elif change == "missing":
            codes.pop()
        else:
            codes.append("assignment")
        payload["disable-error-code"] = codes
        with pytest.raises(e.PydanticValidationError, match="Mypy ruling"):
            m.Infra.MypyConfig.model_validate(payload)

    @staticmethod
    def test_selected_policy_requires_a_declared_suspension_field() -> None:
        """Missing policy does not silently introduce schema-owned defaults."""
        payload = config.Infra.tooling.tools.mypy.model_dump(by_alias=True)
        del payload["disable-error-code"]
        with pytest.raises(e.PydanticValidationError, match="disable-error-code"):
            m.Infra.MypyConfig.model_validate(payload)
