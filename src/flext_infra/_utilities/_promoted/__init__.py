# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Promoted package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .commands import FlextInfraUtilitiesPromotedCommands
    from .execution import FlextInfraUtilitiesPromotedExecution
    from .invocation import FlextInfraUtilitiesPromotedInvocation
    from .rendering import FlextInfraUtilitiesPromotedRendering
    from .workspace import FlextInfraUtilitiesPromotedWorkspace


__all__: tuple[str, ...] = (
    "FlextInfraUtilitiesPromotedCommands",
    "FlextInfraUtilitiesPromotedExecution",
    "FlextInfraUtilitiesPromotedInvocation",
    "FlextInfraUtilitiesPromotedRendering",
    "FlextInfraUtilitiesPromotedWorkspace",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".commands": ("FlextInfraUtilitiesPromotedCommands",),
            ".execution": ("FlextInfraUtilitiesPromotedExecution",),
            ".invocation": ("FlextInfraUtilitiesPromotedInvocation",),
            ".rendering": ("FlextInfraUtilitiesPromotedRendering",),
            ".workspace": ("FlextInfraUtilitiesPromotedWorkspace",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
