# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.detectors package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .consumer_import_violations_detector import (
        FlextInfraConsumerImportViolationsDetector,
    )
    from .deferred_self_reference_detector import (
        FlextInfraDeferredSelfReferenceDetector,
    )
    from .future_annotations_detector import FlextInfraFutureAnnotationsDetector
    from .inline_import_detector import FlextInfraInlineImportDetector
    from .loose_test_function_detector import FlextInfraLooseTestFunctionDetector
    from .lsp_diagnostics import FlextInfraLspDiagnosticsDetector
    from .manual_protocol_detector import FlextInfraManualProtocolDetector
    from .manual_typing_alias_detector import FlextInfraManualTypingAliasDetector
    from .silent_failure_detector import FlextInfraSilentFailureDetector


__all__: tuple[str, ...] = (
    "FlextInfraConsumerImportViolationsDetector",
    "FlextInfraDeferredSelfReferenceDetector",
    "FlextInfraFutureAnnotationsDetector",
    "FlextInfraInlineImportDetector",
    "FlextInfraLooseTestFunctionDetector",
    "FlextInfraLspDiagnosticsDetector",
    "FlextInfraManualProtocolDetector",
    "FlextInfraManualTypingAliasDetector",
    "FlextInfraSilentFailureDetector",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".consumer_import_violations_detector": (
                "FlextInfraConsumerImportViolationsDetector",
            ),
            ".deferred_self_reference_detector": (
                "FlextInfraDeferredSelfReferenceDetector",
            ),
            ".future_annotations_detector": ("FlextInfraFutureAnnotationsDetector",),
            ".inline_import_detector": ("FlextInfraInlineImportDetector",),
            ".loose_test_function_detector": ("FlextInfraLooseTestFunctionDetector",),
            ".lsp_diagnostics": ("FlextInfraLspDiagnosticsDetector",),
            ".manual_protocol_detector": ("FlextInfraManualProtocolDetector",),
            ".manual_typing_alias_detector": ("FlextInfraManualTypingAliasDetector",),
            ".silent_failure_detector": ("FlextInfraSilentFailureDetector",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
