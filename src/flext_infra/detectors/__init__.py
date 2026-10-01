# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.detectors package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .class_placement_detector import FlextInfraClassPlacementDetector
    from .compatibility_alias_detector import FlextInfraCompatibilityAliasDetector
    from .cyclic_import_detector import FlextInfraCyclicImportDetector
    from .deferred_self_reference_detector import (
        FlextInfraDeferredSelfReferenceDetector,
    )
    from .import_alias_detector import FlextInfraImportAliasDetector
    from .internal_import_detector import FlextInfraInternalImportDetector
    from .loose_object_detector import FlextInfraLooseObjectDetector
    from .lsp_diagnostics import FlextInfraLspDiagnosticsDetector
    from .namespace_source_detector import FlextInfraNamespaceSourceDetector
    from .private_import_bypass_detector import FlextInfraPrivateImportBypassDetector
    from .runtime_alias_detector import FlextInfraRuntimeAliasDetector


__all__: tuple[str, ...] = (
    "FlextInfraClassPlacementDetector",
    "FlextInfraCompatibilityAliasDetector",
    "FlextInfraCyclicImportDetector",
    "FlextInfraDeferredSelfReferenceDetector",
    "FlextInfraImportAliasDetector",
    "FlextInfraInternalImportDetector",
    "FlextInfraLooseObjectDetector",
    "FlextInfraLspDiagnosticsDetector",
    "FlextInfraNamespaceSourceDetector",
    "FlextInfraPrivateImportBypassDetector",
    "FlextInfraRuntimeAliasDetector",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".class_placement_detector": ("FlextInfraClassPlacementDetector",),
            ".compatibility_alias_detector": ("FlextInfraCompatibilityAliasDetector",),
            ".cyclic_import_detector": ("FlextInfraCyclicImportDetector",),
            ".deferred_self_reference_detector": (
                "FlextInfraDeferredSelfReferenceDetector",
            ),
            ".import_alias_detector": ("FlextInfraImportAliasDetector",),
            ".internal_import_detector": ("FlextInfraInternalImportDetector",),
            ".loose_object_detector": ("FlextInfraLooseObjectDetector",),
            ".lsp_diagnostics": ("FlextInfraLspDiagnosticsDetector",),
            ".namespace_source_detector": ("FlextInfraNamespaceSourceDetector",),
            ".private_import_bypass_detector": (
                "FlextInfraPrivateImportBypassDetector",
            ),
            ".runtime_alias_detector": ("FlextInfraRuntimeAliasDetector",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
