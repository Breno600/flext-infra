# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Pyproject package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .base import FlextInfraUtilitiesPyprojectConformBase
    from .document import FlextInfraUtilitiesPyprojectDocument
    from .overlay import FlextInfraUtilitiesPyprojectOverlay
    from .requirements import FlextInfraUtilitiesPyprojectRequirements
    from .toml_phases import FlextInfraUtilitiesPyprojectTomlPhases
    from .uv_sources import FlextInfraUtilitiesPyprojectUvSources


__all__: tuple[str, ...] = (
    "FlextInfraUtilitiesPyprojectConformBase",
    "FlextInfraUtilitiesPyprojectDocument",
    "FlextInfraUtilitiesPyprojectOverlay",
    "FlextInfraUtilitiesPyprojectRequirements",
    "FlextInfraUtilitiesPyprojectTomlPhases",
    "FlextInfraUtilitiesPyprojectUvSources",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".base": ("FlextInfraUtilitiesPyprojectConformBase",),
            ".document": ("FlextInfraUtilitiesPyprojectDocument",),
            ".overlay": ("FlextInfraUtilitiesPyprojectOverlay",),
            ".requirements": ("FlextInfraUtilitiesPyprojectRequirements",),
            ".toml_phases": ("FlextInfraUtilitiesPyprojectTomlPhases",),
            ".uv_sources": ("FlextInfraUtilitiesPyprojectUvSources",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
