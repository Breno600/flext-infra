# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Rope Analysis package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .asthelpers import FlextInfraUtilitiesRopeAnalysisAstHelpers
    from .base import FlextInfraUtilitiesRopeAnalysisBase
    from .exports import FlextInfraUtilitiesRopeAnalysisExports
    from .importstate import FlextInfraUtilitiesRopeAnalysisImportState
    from .sourcescan import FlextInfraUtilitiesRopeAnalysisSourceScan


__all__: tuple[str, ...] = (
    "FlextInfraUtilitiesRopeAnalysisAstHelpers",
    "FlextInfraUtilitiesRopeAnalysisBase",
    "FlextInfraUtilitiesRopeAnalysisExports",
    "FlextInfraUtilitiesRopeAnalysisImportState",
    "FlextInfraUtilitiesRopeAnalysisSourceScan",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".asthelpers": ("FlextInfraUtilitiesRopeAnalysisAstHelpers",),
            ".base": ("FlextInfraUtilitiesRopeAnalysisBase",),
            ".exports": ("FlextInfraUtilitiesRopeAnalysisExports",),
            ".importstate": ("FlextInfraUtilitiesRopeAnalysisImportState",),
            ".sourcescan": ("FlextInfraUtilitiesRopeAnalysisSourceScan",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
