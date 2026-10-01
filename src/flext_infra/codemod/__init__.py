# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.codemod package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from ._rename_sources import FlextInfraRenameSources
    from ._rename_symbols import FlextInfraRenameSymbols
    from .apply_renames import FlextInfraApplyRenames
    from .ast_scan import FlextInfraCodemodAstScan
    from .batch_apply import FlextInfraCodemodBatchApply
    from .batch_gates import FlextInfraModGateEngine
    from .batch_replacements import FlextInfraModReplacements
    from .semantic_apply import FlextInfraCodemodSemanticApply
    from .snapshot_reconciler import FlextInfraCodemodSnapshotReconciler
    from .snapshot_refresh import FlextInfraCodemodSnapshotRefresh
    from .text_gates import FlextInfraModTextGateEngine


__all__: tuple[str, ...] = (
    "FlextInfraApplyRenames",
    "FlextInfraCodemodAstScan",
    "FlextInfraCodemodBatchApply",
    "FlextInfraCodemodSemanticApply",
    "FlextInfraCodemodSnapshotReconciler",
    "FlextInfraCodemodSnapshotRefresh",
    "FlextInfraModGateEngine",
    "FlextInfraModReplacements",
    "FlextInfraModTextGateEngine",
    "FlextInfraRenameSources",
    "FlextInfraRenameSymbols",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._rename_sources": ("FlextInfraRenameSources",),
            "._rename_symbols": ("FlextInfraRenameSymbols",),
            ".apply_renames": ("FlextInfraApplyRenames",),
            ".ast_scan": ("FlextInfraCodemodAstScan",),
            ".batch_apply": ("FlextInfraCodemodBatchApply",),
            ".batch_gates": ("FlextInfraModGateEngine",),
            ".batch_replacements": ("FlextInfraModReplacements",),
            ".semantic_apply": ("FlextInfraCodemodSemanticApply",),
            ".snapshot_reconciler": ("FlextInfraCodemodSnapshotReconciler",),
            ".snapshot_refresh": ("FlextInfraCodemodSnapshotRefresh",),
            ".text_gates": ("FlextInfraModTextGateEngine",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
