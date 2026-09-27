"""Canonical per-group lazy resolution for every flext-infra CLI route."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c

if TYPE_CHECKING:
    from flext_infra import m, t

# Why (ai-hub-xkux, fleet-wide fix): the previous FlextInfraCliRouteService composed
# FlextInfraCodegenRoutes + FlextInfraValidationRoutes + FlextInfraWorkspaceRoutes via multi-inheritance and
# built every group's ClassVar route table (docs/refactor/release/check/...)
# at CLASS-DEFINITION time, so importing this module -- which cli_dispatch.py
# does unconditionally on every CLI invocation -- eagerly imported all three
# owning modules and their entire transitive dependency graph (~5.9s measured
# via python -X importtime), even though exactly one command group is ever
# dispatched per invocation. Only the owning module for the RESOLVED group is
# imported now, cutting startup to that one module's cost.
_GROUP_OWNERS: Final[MutableMapping[str, t.Triple[str, str, str]]] = {
    c.Infra.CLI_GROUP_CHECK: (
        "flext_infra.services.cli_routes_codegen",
        "FlextInfraCodegenRoutes",
        "codegen_routes",
    ),
    c.Infra.CLI_GROUP_CODEGEN: (
        "flext_infra.services.cli_routes_codegen",
        "FlextInfraCodegenRoutes",
        "codegen_routes",
    ),
    c.Infra.CLI_GROUP_DEPS: (
        "flext_infra.services.cli_routes_codegen",
        "FlextInfraCodegenRoutes",
        "codegen_routes",
    ),
    c.Infra.CLI_GROUP_DOCS: (
        "flext_infra.services.cli_routes_validate",
        "FlextInfraValidationRoutes",
        "validation_routes",
    ),
    c.Infra.CLI_GROUP_MAINTENANCE: (
        "flext_infra.services.cli_routes_validate",
        "FlextInfraValidationRoutes",
        "validation_routes",
    ),
    c.Infra.CLI_GROUP_VALIDATE: (
        "flext_infra.services.cli_routes_validate",
        "FlextInfraValidationRoutes",
        "validation_routes",
    ),
    c.Infra.CLI_GROUP_REFACTOR: (
        "flext_infra.services.cli_routes_workspace",
        "FlextInfraWorkspaceRoutes",
        "workspace_routes",
    ),
    c.Infra.CLI_GROUP_RELEASE: (
        "flext_infra.services.cli_routes_workspace",
        "FlextInfraWorkspaceRoutes",
        "workspace_routes",
    ),
    c.Infra.CLI_GROUP_WORKSPACE: (
        "flext_infra.services.cli_routes_workspace",
        "FlextInfraWorkspaceRoutes",
        "workspace_routes",
    ),
}


class FlextInfraCliRouteService:
    """Resolve one group's CLI route table on demand, never all of them."""

    @classmethod
    def route_table_for(cls, group: str) -> t.VariadicTuple[m.Cli.ResultCommandRoute]:
        """Return the routes for one command group, importing only its owner."""
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
