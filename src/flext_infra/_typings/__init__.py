# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Typings package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .adapters import FlextInfraTypesAdapters
    from .base import FlextInfraTypesBase
    from .rope import FlextInfraTypesRope


__all__: tuple[str, ...] = (
    "FlextInfraTypesAdapters",
    "FlextInfraTypesBase",
    "FlextInfraTypesRope",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".adapters": ("FlextInfraTypesAdapters",),
            ".base": ("FlextInfraTypesBase",),
            ".rope": ("FlextInfraTypesRope",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
