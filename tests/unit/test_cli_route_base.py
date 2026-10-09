"""Public CLI route adapters preserve success values and failure details.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraCliRouteBase, c, m, p, r, t


class TestsFlextInfraCliRouteBase:
    """Exercise heterogeneous routes through the published adapter."""

    @staticmethod
    def _success(value: t.Cli.ResultValue) -> p.Result[t.Cli.ResultValue]:
        """Return a payload through the canonical result owner.

        Returns:
            The successful result carrying the supplied payload.
        """
        return r[t.Cli.ResultValue].ok(value)

    @staticmethod
    def test_route_preserves_model_and_collection_identity() -> None:
        """Widening leaves typed models and mutable collections intact."""
        issue = m.Infra.Issue(
            file="sample.py",
            line=1,
            column=1,
            code="sample",
            message="Consumer payload",
        )
        payloads: tuple[t.Cli.ResultValue, ...] = (
            issue,
            [issue, Path("sample.py")],
        )
        handler = FlextInfraCliRouteBase.result_handler(
            TestsFlextInfraCliRouteBase._success,
        )
        for payload in payloads:
            result = handler(payload)
            tm.that(result.success, eq=True)
            tm.that(result.value is payload, eq=True)

    @staticmethod
    def test_route_preserves_none_payload_rejection() -> None:
        """The result owner rejects an invalid success payload unchanged."""
        handler = FlextInfraCliRouteBase.result_handler(
            TestsFlextInfraCliRouteBase._success,
        )
        with pytest.raises(
            ValueError,
            match=re.escape(c.ERR_RESULT_SUCCESS_PAYLOAD_CANNOT_BE_NONE),
        ) as caught:
            handler(None)
        tm.that(str(caught.value), eq=c.ERR_RESULT_SUCCESS_PAYLOAD_CANNOT_BE_NONE)

    @staticmethod
    def test_route_preserves_failure_details() -> None:
        """A failed handler crosses the adapter without changing its details."""
        failure = r[str].fail(
            "Consumer operation failed",
            error_code="consumer-failure",
            error_data={"operation": "route"},
        )

        def failed_handler(_params: str) -> p.Result[str]:
            """Return the original failed result.

            Returns:
                The failed consumer result.
            """
            return failure

        result = FlextInfraCliRouteBase.result_handler(failed_handler)("request")
        tm.that(result.failure, eq=True)
        tm.that(result.error, eq=failure.error)
        tm.that(result.error_code, eq=failure.error_code)
        tm.that(result.error_data, eq=failure.error_data)
