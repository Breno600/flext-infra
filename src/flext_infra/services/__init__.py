# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.services package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from . import _codegen
    from ._codegen.vscode import FlextInfraCodegenVscodeMixin
    from .candidate_bootstrap import FlextInfraCandidateBootstrapService
    from .cli_dispatch import FlextInfraCliDispatchService
    from .cli_route_base import FlextInfraCliRouteBase
    from .cli_routes import FlextInfraCliRouteService
    from .cli_routes_codegen import FlextInfraCodegenRoutes
    from .cli_routes_refactor import FlextInfraRefactorRoutes
    from .cli_routes_validate import FlextInfraValidationRoutes
    from .cli_routes_validate_commands import FlextInfraValidationCommandRoutes
    from .cli_routes_workspace import FlextInfraWorkspaceRoutes
    from .codegen import FlextInfraCodegen


__all__: tuple[str, ...] = (
    "FlextInfraCandidateBootstrapService",
    "FlextInfraCliDispatchService",
    "FlextInfraCliRouteBase",
    "FlextInfraCliRouteService",
    "FlextInfraCodegen",
    "FlextInfraCodegenRoutes",
    "FlextInfraCodegenVscodeMixin",
    "FlextInfraRefactorRoutes",
    "FlextInfraValidationCommandRoutes",
    "FlextInfraValidationRoutes",
    "FlextInfraWorkspaceRoutes",
    "_codegen",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._codegen": ("_codegen",),
            "._codegen.vscode": ("FlextInfraCodegenVscodeMixin",),
            ".candidate_bootstrap": ("FlextInfraCandidateBootstrapService",),
            ".cli_dispatch": ("FlextInfraCliDispatchService",),
            ".cli_route_base": ("FlextInfraCliRouteBase",),
            ".cli_routes": ("FlextInfraCliRouteService",),
            ".cli_routes_codegen": ("FlextInfraCodegenRoutes",),
            ".cli_routes_refactor": ("FlextInfraRefactorRoutes",),
            ".cli_routes_validate": ("FlextInfraValidationRoutes",),
            ".cli_routes_validate_commands": ("FlextInfraValidationCommandRoutes",),
            ".cli_routes_workspace": ("FlextInfraWorkspaceRoutes",),
            ".codegen": ("FlextInfraCodegen",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
