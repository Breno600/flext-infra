# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Work package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .ownership import FlextInfraWorkOwnership
    from .reservation import FlextInfraWorkReservation
    from .start_support import FlextInfraWorkStartSupport
    from .topology import FlextInfraWorkTopology


__all__: tuple[str, ...] = (
    "FlextInfraWorkOwnership",
    "FlextInfraWorkReservation",
    "FlextInfraWorkStartSupport",
    "FlextInfraWorkTopology",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".ownership": ("FlextInfraWorkOwnership",),
            ".reservation": ("FlextInfraWorkReservation",),
            ".start_support": ("FlextInfraWorkStartSupport",),
            ".topology": ("FlextInfraWorkTopology",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
