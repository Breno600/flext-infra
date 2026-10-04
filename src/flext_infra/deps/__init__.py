# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.deps package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.deps import _modernizer, phases
    from flext_infra.deps._detection_runners import (
        FlextInfraDependencyDetectionRunnersMixin,
    )
    from flext_infra.deps._detector_runtime_steps import (
        FlextInfraDependencyDetectorRuntimeSteps,
    )
    from flext_infra.deps._extra_paths_sync import FlextInfraExtraPathsSyncMixin
    from flext_infra.deps._floor_profile_writer import FlextInfraDepsFloorProfileWriter
    from flext_infra.deps._modernizer.base import FlextInfraPyprojectModernizerBase
    from flext_infra.deps._modernizer.document import (
        FlextInfraPyprojectModernizerDocument,
    )
    from flext_infra.deps._modernizer.run import FlextInfraPyprojectModernizerRun
    from flext_infra.deps._modernizer.tooling import (
        FlextInfraPyprojectModernizerTooling,
    )
    from flext_infra.deps._pyrefly_fix_steps import FlextInfraConfigFixerSteps
    from flext_infra.deps.detection import FlextInfraDependencyDetectionService
    from flext_infra.deps.detection_analysis import (
        FlextInfraDependencyDetectionAnalysis,
    )
    from flext_infra.deps.detector import FlextInfraRuntimeDevDependencyDetector
    from flext_infra.deps.detector_runtime import FlextInfraDependencyDetectorRuntime
    from flext_infra.deps.extra_paths import FlextInfraExtraPathsManager
    from flext_infra.deps.fix_pyrefly_config import FlextInfraConfigFixer
    from flext_infra.deps.lock_integrity import FlextInfraLockIntegrityVerifier
    from flext_infra.deps.modernizer import FlextInfraPyprojectModernizer
    from flext_infra.deps.phases.consolidate_groups import (
        FlextInfraConsolidateGroupsPhase,
    )
    from flext_infra.deps.phases.ensure_packaging import FlextInfraEnsurePackagingPhase
    from flext_infra.deps.phases.ensure_pyrefly import (
        FlextInfraEnsurePyreflyConfigPhase,
    )
    from flext_infra.deps.phases.ensure_pyright import (
        FlextInfraEnsurePyrightConfigPhase,
    )
    from flext_infra.deps.phases.ensure_ruff import FlextInfraEnsureRuffConfigPhase
    from flext_infra.deps.phases.inject_comments import FlextInfraInjectCommentsPhase
    from flext_infra.deps.phases.tool_tables import FlextInfraToolTablesPhase


__all__: tuple[str, ...] = (
    "FlextInfraConfigFixer",
    "FlextInfraConfigFixerSteps",
    "FlextInfraConsolidateGroupsPhase",
    "FlextInfraDependencyDetectionAnalysis",
    "FlextInfraDependencyDetectionRunnersMixin",
    "FlextInfraDependencyDetectionService",
    "FlextInfraDependencyDetectorRuntime",
    "FlextInfraDependencyDetectorRuntimeSteps",
    "FlextInfraDepsFloorProfileWriter",
    "FlextInfraEnsurePackagingPhase",
    "FlextInfraEnsurePyreflyConfigPhase",
    "FlextInfraEnsurePyrightConfigPhase",
    "FlextInfraEnsureRuffConfigPhase",
    "FlextInfraExtraPathsManager",
    "FlextInfraExtraPathsSyncMixin",
    "FlextInfraInjectCommentsPhase",
    "FlextInfraLockIntegrityVerifier",
    "FlextInfraPyprojectModernizer",
    "FlextInfraPyprojectModernizerBase",
    "FlextInfraPyprojectModernizerDocument",
    "FlextInfraPyprojectModernizerRun",
    "FlextInfraPyprojectModernizerTooling",
    "FlextInfraRuntimeDevDependencyDetector",
    "FlextInfraToolTablesPhase",
    "_modernizer",
    "phases",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraConfigFixer": ".fix_pyrefly_config",
        "FlextInfraConfigFixerSteps": "._pyrefly_fix_steps",
        "FlextInfraConsolidateGroupsPhase": ".phases.consolidate_groups",
        "FlextInfraDependencyDetectionAnalysis": ".detection_analysis",
        "FlextInfraDependencyDetectionRunnersMixin": "._detection_runners",
        "FlextInfraDependencyDetectionService": ".detection",
        "FlextInfraDependencyDetectorRuntime": ".detector_runtime",
        "FlextInfraDependencyDetectorRuntimeSteps": "._detector_runtime_steps",
        "FlextInfraDepsFloorProfileWriter": "._floor_profile_writer",
        "FlextInfraEnsurePackagingPhase": ".phases.ensure_packaging",
        "FlextInfraEnsurePyreflyConfigPhase": ".phases.ensure_pyrefly",
        "FlextInfraEnsurePyrightConfigPhase": ".phases.ensure_pyright",
        "FlextInfraEnsureRuffConfigPhase": ".phases.ensure_ruff",
        "FlextInfraExtraPathsManager": ".extra_paths",
        "FlextInfraExtraPathsSyncMixin": "._extra_paths_sync",
        "FlextInfraInjectCommentsPhase": ".phases.inject_comments",
        "FlextInfraLockIntegrityVerifier": ".lock_integrity",
        "FlextInfraPyprojectModernizer": ".modernizer",
        "FlextInfraPyprojectModernizerBase": "._modernizer.base",
        "FlextInfraPyprojectModernizerDocument": "._modernizer.document",
        "FlextInfraPyprojectModernizerRun": "._modernizer.run",
        "FlextInfraPyprojectModernizerTooling": "._modernizer.tooling",
        "FlextInfraRuntimeDevDependencyDetector": ".detector",
        "FlextInfraToolTablesPhase": ".phases.tool_tables",
        "_modernizer": "._modernizer",
        "phases": ".phases",
    }),
    public_exports=__all__,
)
