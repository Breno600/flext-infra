# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.codemod package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .apply_renames import FlextInfraApplyRenames
    from .ast_scan import FlextInfraCodemodAstScan
    from .batch_apply import FlextInfraCodemodBatchApply
    from .batch_gates import FlextInfraModGateEngine
    from .batch_replacements import FlextInfraModReplacements
    from .sed_apply import FlextInfraCodemodSedApply
    from .semantic_apply import FlextInfraCodemodSemanticApply
    from .snapshot_reconciler import FlextInfraCodemodSnapshotReconciler
    from .text_gates import FlextInfraModTextGateEngine


__all__: tuple[str, ...] = (
    "FlextInfraApplyRenames",
    "FlextInfraCodemodAstScan",
    "FlextInfraCodemodBatchApply",
    "FlextInfraCodemodSedApply",
    "FlextInfraCodemodSemanticApply",
    "FlextInfraCodemodSnapshotReconciler",
    "FlextInfraModGateEngine",
    "FlextInfraModReplacements",
    "FlextInfraModTextGateEngine",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".apply_renames": ("FlextInfraApplyRenames",),
            ".ast_scan": ("FlextInfraCodemodAstScan",),
            ".batch_apply": ("FlextInfraCodemodBatchApply",),
            ".batch_gates": ("FlextInfraModGateEngine",),
            ".batch_replacements": ("FlextInfraModReplacements",),
            ".sed_apply": ("FlextInfraCodemodSedApply",),
            ".semantic_apply": ("FlextInfraCodemodSemanticApply",),
            ".snapshot_reconciler": ("FlextInfraCodemodSnapshotReconciler",),
            ".text_gates": ("FlextInfraModTextGateEngine",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
