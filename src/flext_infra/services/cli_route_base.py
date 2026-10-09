"""Shared typed behavior for CLI route services.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Callable

from flext_infra import p, t


class FlextInfraCliRouteBase:
    """Provide the common result-value widening contract for route handlers."""

    @staticmethod
    def as_route_value(value: t.Cli.ResultValue) -> t.Cli.ResultValue:
        """Widen a concrete result payload to the CLI route contract value.

        Returns:
            The same payload, typed at the route contract boundary.

        """
        return value

    @staticmethod
    def result_handler[TParams, TResult: t.JsonPayload](
        handler: Callable[[TParams], p.Result[TResult]],
    ) -> p.Cli.ResultRouteHandler:
        """Erase one concrete result payload at the heterogeneous route boundary.

        Returns:
            The resulting ``p.Cli.ResultRouteHandler``.

        """

        def execute(params: TParams) -> p.Result[t.Cli.ResultValue]:
            return handler(params).map(FlextInfraCliRouteBase.as_route_value)

        return execute


__all__: list[str] = ["FlextInfraCliRouteBase"]
