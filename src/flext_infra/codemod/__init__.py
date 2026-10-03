# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.codemod package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.codemod._rename_sources import FlextInfraRenameSources
    from flext_infra.codemod._rename_symbols import FlextInfraRenameSymbols
    from flext_infra.codemod.apply_renames import FlextInfraApplyRenames
    from flext_infra.codemod.ast_scan import FlextInfraCodemodAstScan
    from flext_infra.codemod.batch_apply import FlextInfraCodemodBatchApply
    from flext_infra.codemod.batch_gates import FlextInfraModGateEngine
    from flext_infra.codemod.batch_replacements import FlextInfraModReplacements
    from flext_infra.codemod.semantic_apply import FlextInfraCodemodSemanticApply
    from flext_infra.codemod.snapshot_reconciler import (
        FlextInfraCodemodSnapshotReconciler,
    )
    from flext_infra.codemod.snapshot_refresh import FlextInfraCodemodSnapshotRefresh
    from flext_infra.codemod.text_gates import FlextInfraModTextGateEngine

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
