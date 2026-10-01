"""Tests for the FLEXT service-base alias.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import s as cli_service_base
from flext_tests import tm

from flext_infra import FlextInfraServiceBase
from tests import u


class TestsFlextInfraServiceBaseAlias:
    """Tests for ``FlextInfraServiceBaseAlias``."""

    @staticmethod
    def test_service_base_generic_alias_flext_is_permitted() -> None:
        """Generic service-root bases must not trigger facade FLEXT enforcement."""
        infra_report = u.check(FlextInfraServiceBase)
        cli_report = u.check(cli_service_base)

        tm.that(not infra_report.violations, eq=True)
        tm.that(not cli_report.violations, eq=True)
