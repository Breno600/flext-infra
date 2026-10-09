"""Canonical per-group lazy resolution for every flext-infra CLI route.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c

if TYPE_CHECKING:
    from flext_infra import m, t


class FlextInfraCliRouteService:
    """Resolve one group's CLI route table on demand, never all of them."""

    @classmethod
    def route_table_for(cls, group: str) -> t.VariadicTuple[m.Cli.ResultCommandRoute]:
        """Return the routes for one command group, importing only its owner.

        Returns:
            The routes for one command group, importing only its owner.

        Raises:
            ValueError: If CLI group has no route owner.

        """
        if group in {
            c.Infra.CLI_GROUP_CHECK,
            c.Infra.CLI_GROUP_CODEGEN,
            c.Infra.CLI_GROUP_DEPS,
        }:
            from flext_infra.services.cli_routes_codegen import FlextInfraCodegenRoutes

            return FlextInfraCodegenRoutes.codegen_routes[group]
        if group in {
            c.Infra.CLI_GROUP_DOCS,
            c.Infra.CLI_GROUP_MAINTENANCE,
            c.Infra.CLI_GROUP_VALIDATE,
        }:
            from flext_infra.services.cli_routes_validate import (
                FlextInfraValidationRoutes,
            )

            return FlextInfraValidationRoutes.validation_routes[group]
        if group in {
            c.Infra.CLI_GROUP_REFACTOR,
            c.Infra.CLI_GROUP_RELEASE,
            c.Infra.CLI_GROUP_WORKSPACE,
        }:
            from flext_infra.services.cli_routes_workspace import (
                FlextInfraWorkspaceRoutes,
            )

            return FlextInfraWorkspaceRoutes.workspace_routes[group]
        msg = f"CLI group has no route owner: {group}"
        raise ValueError(msg)


__all__: list[str] = ["FlextInfraCliRouteService"]
