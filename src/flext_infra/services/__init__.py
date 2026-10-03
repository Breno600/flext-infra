# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.services package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.services import _codegen
    from flext_infra.services._codegen.vscode import FlextInfraCodegenVscodeMixin
    from flext_infra.services.candidate_bootstrap import (
        FlextInfraCandidateBootstrapService,
    )
    from flext_infra.services.cli_dispatch import FlextInfraCliDispatchService
    from flext_infra.services.cli_route_base import FlextInfraCliRouteBase
    from flext_infra.services.cli_routes import FlextInfraCliRouteService
    from flext_infra.services.cli_routes_codegen import FlextInfraCodegenRoutes
    from flext_infra.services.cli_routes_refactor import FlextInfraRefactorRoutes
    from flext_infra.services.cli_routes_validate import FlextInfraValidationRoutes
    from flext_infra.services.cli_routes_validate_commands import (
        FlextInfraValidationCommandRoutes,
    )
    from flext_infra.services.cli_routes_workspace import FlextInfraWorkspaceRoutes
    from flext_infra.services.codegen import FlextInfraCodegen

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
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
