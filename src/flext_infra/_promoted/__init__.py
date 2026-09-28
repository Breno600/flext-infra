# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Promoted package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .base import FlextInfraPromotedBase
    from .discovery import FlextInfraPromotedDiscovery
    from .dispatch import FlextInfraPromotedDispatch
    from .registry import FlextInfraPromotedRegistry


__all__: tuple[str, ...] = (
    "FlextInfraPromotedBase",
    "FlextInfraPromotedDiscovery",
    "FlextInfraPromotedDispatch",
    "FlextInfraPromotedRegistry",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".base": ("FlextInfraPromotedBase",),
            ".discovery": ("FlextInfraPromotedDiscovery",),
            ".dispatch": ("FlextInfraPromotedDispatch",),
            ".registry": ("FlextInfraPromotedRegistry",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
