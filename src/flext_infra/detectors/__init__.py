# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.detectors package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .deferred_self_reference_detector import (
        FlextInfraDeferredSelfReferenceDetector,
    )
    from .lsp_diagnostics import FlextInfraLspDiagnosticsDetector


__all__: tuple[str, ...] = (
    "FlextInfraDeferredSelfReferenceDetector",
    "FlextInfraLspDiagnosticsDetector",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".deferred_self_reference_detector": (
                "FlextInfraDeferredSelfReferenceDetector",
            ),
            ".lsp_diagnostics": ("FlextInfraLspDiagnosticsDetector",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
