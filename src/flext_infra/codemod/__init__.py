# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.codemod package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.codemod._loop_phase_accessor_rename import (
        FlextInfraAccessorRenamePhase,
    )
    from flext_infra.codemod._loop_phase_import_normalization import (
        FlextInfraImportNormalizationPhase,
    )
    from flext_infra.codemod._loop_phase_namespace_relocation import (
        FlextInfraNamespaceRelocationPhase,
    )
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
    "FlextInfraAccessorRenamePhase",
    "FlextInfraApplyRenames",
    "FlextInfraCodemodAstScan",
    "FlextInfraCodemodBatchApply",
    "FlextInfraCodemodSemanticApply",
    "FlextInfraCodemodSnapshotReconciler",
    "FlextInfraCodemodSnapshotRefresh",
    "FlextInfraImportNormalizationPhase",
    "FlextInfraModGateEngine",
    "FlextInfraModReplacements",
    "FlextInfraModTextGateEngine",
    "FlextInfraNamespaceRelocationPhase",
    "FlextInfraRenameSources",
    "FlextInfraRenameSymbols",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraAccessorRenamePhase": "._loop_phase_accessor_rename",
        "FlextInfraApplyRenames": ".apply_renames",
        "FlextInfraCodemodAstScan": ".ast_scan",
        "FlextInfraCodemodBatchApply": ".batch_apply",
        "FlextInfraCodemodSemanticApply": ".semantic_apply",
        "FlextInfraCodemodSnapshotReconciler": ".snapshot_reconciler",
        "FlextInfraCodemodSnapshotRefresh": ".snapshot_refresh",
        "FlextInfraImportNormalizationPhase": "._loop_phase_import_normalization",
        "FlextInfraModGateEngine": ".batch_gates",
        "FlextInfraModReplacements": ".batch_replacements",
        "FlextInfraModTextGateEngine": ".text_gates",
        "FlextInfraNamespaceRelocationPhase": "._loop_phase_namespace_relocation",
        "FlextInfraRenameSources": "._rename_sources",
        "FlextInfraRenameSymbols": "._rename_symbols",
    }),
    public_exports=__all__,
)
