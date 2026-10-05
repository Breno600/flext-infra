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
from flext_infra import config, m, t


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

    @staticmethod
    @pytest.mark.parametrize("change", ["empty", "missing", "additional"])
    def test_selected_policy_rejects_unauthorized_suspensions(
        change: str,
    ) -> None:
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

    @staticmethod
    @pytest.mark.parametrize(
        ("section", "option", "value"),
        [
            ("string-settings", "plugins", "pydantic.v1.mypy"),
            ("string-settings", "disable_error_code", "assignment"),
            ("string-settings", "enable_error_code", "call-arg"),
            ("string-settings", "enable-error-code", "prop-decorator"),
            ("string-settings", "disable-error-code", "assignment"),
            ("string-settings", "plugins ", "pydantic.v1.mypy"),
            ("string-settings", "python_version", "0.0"),
            ("string-settings", "python-version", "0.0"),
            ("string-settings", "mypy_path", "untrusted"),
            ("boolean-settings", "plugins", False),
            ("boolean-settings", "disable_error_code", False),
            ("boolean-settings", "enable_error_code", True),
            ("boolean-settings", "enable-error-code", True),
            ("boolean-settings", "overrides", False),
            ("boolean-settings", "ignore_errors", True),
            ("string-settings", "ignore_errors", "true"),
        ],
    )
    def test_generic_options_cannot_shadow_typed_policy(
        section: str,
        option: str,
        value: t.Scalar,
    ) -> None:
        """Generic options cannot bypass the dedicated plugin and code fields."""
        payload = config.Infra.tooling.tools.mypy.model_dump(by_alias=True)
        payload[section] = {option: value}
        with pytest.raises(e.PydanticValidationError, match="Mypy policy"):
            m.Infra.MypyConfig.model_validate(payload)

    @staticmethod
    @pytest.mark.parametrize("option", ["follow_imports", "follow-imports"])
    def test_generic_options_reject_cross_map_collisions(option: str) -> None:
        """An option cannot silently prefer the string map over the boolean map."""
        payload = config.Infra.tooling.tools.mypy.model_dump(by_alias=True)
        payload["boolean-settings"] = {option: True}
        payload["string-settings"] = {"follow_imports": "normal"}
        with pytest.raises(e.PydanticValidationError, match="duplicate generic"):
            m.Infra.MypyConfig.model_validate(payload)

    @staticmethod
    def test_generic_options_reject_alias_collisions_within_a_map() -> None:
        """Aliases cannot introduce two declarations of one generic option."""
        payload = config.Infra.tooling.tools.mypy.model_dump(by_alias=True)
        payload["string-settings"] = {
            "follow_imports": "normal",
            "follow-imports": "error",
        }
        with pytest.raises(e.PydanticValidationError, match="duplicate generic"):
            m.Infra.MypyConfig.model_validate(payload)

    @staticmethod
    def test_generic_options_allow_enabling_an_unsuspended_error() -> None:
        """Valid unrelated diagnostic settings remain supported without masking."""
        policy = config.Infra.tooling.tools.mypy
        payload = policy.model_dump(by_alias=True)
        payload["string-settings"] = {
            **policy.string_settings,
            "enable_error_code": "arg-type",
        }
        payload["boolean-settings"] = {
            **policy.boolean_settings,
            "ignore_errors": False,
        }
        validated = m.Infra.MypyConfig.model_validate(payload)
        tm.that(validated.string_settings["enable_error_code"], eq="arg-type")
        tm.that(validated.boolean_settings["ignore_errors"], eq=False)
        tm.that(tuple(validated.plugins), eq=tuple(policy.plugins))
        tm.that(
            tuple(validated.disable_error_code),
            eq=tuple(policy.disable_error_code),
        )

    @staticmethod
    def test_generic_options_reject_mixed_enabled_suspended_codes() -> None:
        """A comma-separated list cannot hide a suspended code among others."""
        policy = config.Infra.tooling.tools.mypy
        payload = policy.model_dump(by_alias=True)
        payload["string-settings"] = {
            **policy.string_settings,
            "enable_error_code": f"arg-type, {policy.disable_error_code[0]} ",
        }
        with pytest.raises(e.PydanticValidationError, match="re-enable suspended"):
            m.Infra.MypyConfig.model_validate(payload)

    @staticmethod
    @pytest.mark.parametrize(
        "option",
        [
            'enable_error_code = "call-arg"\ncustom_option',
            '"plugins"',
            "follow-imports",
        ],
    )
    def test_generic_options_reject_toml_key_syntax(option: str) -> None:
        """A generic key is one option, never a quoted or injected TOML statement."""
        payload = config.Infra.tooling.tools.mypy.model_dump(by_alias=True)
        payload["string-settings"] = {option: "normal"}
        with pytest.raises(e.PydanticValidationError, match="plain option names"):
            m.Infra.MypyConfig.model_validate(payload)
