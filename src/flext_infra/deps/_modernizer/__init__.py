# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.deps. Modernizer package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .base import FlextInfraPyprojectModernizerBase
    from .document import FlextInfraPyprojectModernizerDocument
    from .run import FlextInfraPyprojectModernizerRun
    from .tooling import FlextInfraPyprojectModernizerTooling


__all__: tuple[str, ...] = (
    "FlextInfraPyprojectModernizerBase",
    "FlextInfraPyprojectModernizerDocument",
    "FlextInfraPyprojectModernizerRun",
    "FlextInfraPyprojectModernizerTooling",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".base": ("FlextInfraPyprojectModernizerBase",),
            ".document": ("FlextInfraPyprojectModernizerDocument",),
            ".run": ("FlextInfraPyprojectModernizerRun",),
            ".tooling": ("FlextInfraPyprojectModernizerTooling",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
