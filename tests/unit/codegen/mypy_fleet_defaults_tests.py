"""Fleet-mandatory mypy defaults: pydantic.mypy always on, ruling codes suppressed.

Operator ruling 2026-10-05: Pydantic 2 is the fleet contract; the
pydantic.mypy plugin is its type surface and stays mandatory, and
prop-decorator/call-arg are suspended everywhere. A project overlay that
omits both keys still inherits them through the model defaults — consumers
must never re-declare the law to keep it, and code edited to quiet those two
mypy codes is a regression.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import config


class TestsMypyFleetMandatoryDefaults:
    """The mypy policy defaults carry the ruling to every consumer."""

    @staticmethod
    def test_defaults_carry_plugin_and_ruling_codes() -> None:
        """Omitted keys resolve to the mandatory plugin and ruling codes."""
        fields = type(config.Infra.tooling.tools.mypy).model_fields
        tm.that(
            list(fields["plugins"].get_default(call_default_factory=True)),
            eq=["pydantic.mypy"],
        )
        tm.that(
            list(
                fields["disable_error_code"].get_default(
                    call_default_factory=True,
                ),
            ),
            eq=["prop-decorator", "call-arg"],
        )

    @staticmethod
    def test_this_repository_declares_the_same_law() -> None:
        """The repo's own declared policy agrees with the mandatory defaults."""
        policy = config.Infra.tooling.tools.mypy
        tm.that(list(policy.plugins), eq=["pydantic.mypy"])
        tm.that(list(policy.disable_error_code), eq=["prop-decorator", "call-arg"])
