# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.deps package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

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

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._detection_runners": ("FlextInfraDependencyDetectionRunnersMixin",),
            "._detector_runtime_steps": ("FlextInfraDependencyDetectorRuntimeSteps",),
            "._extra_paths_sync": ("FlextInfraExtraPathsSyncMixin",),
            "._floor_profile_writer": ("FlextInfraDepsFloorProfileWriter",),
            "._modernizer": ("_modernizer",),
            "._modernizer.base": ("FlextInfraPyprojectModernizerBase",),
            "._modernizer.document": ("FlextInfraPyprojectModernizerDocument",),
            "._modernizer.run": ("FlextInfraPyprojectModernizerRun",),
            "._modernizer.tooling": ("FlextInfraPyprojectModernizerTooling",),
            "._pyrefly_fix_steps": ("FlextInfraConfigFixerSteps",),
            ".detection": ("FlextInfraDependencyDetectionService",),
            ".detection_analysis": ("FlextInfraDependencyDetectionAnalysis",),
            ".detector": ("FlextInfraRuntimeDevDependencyDetector",),
            ".detector_runtime": ("FlextInfraDependencyDetectorRuntime",),
            ".extra_paths": ("FlextInfraExtraPathsManager",),
            ".fix_pyrefly_config": ("FlextInfraConfigFixer",),
            ".lock_integrity": ("FlextInfraLockIntegrityVerifier",),
            ".modernizer": ("FlextInfraPyprojectModernizer",),
            ".phases": ("phases",),
            ".phases.consolidate_groups": ("FlextInfraConsolidateGroupsPhase",),
            ".phases.ensure_packaging": ("FlextInfraEnsurePackagingPhase",),
            ".phases.ensure_pyrefly": ("FlextInfraEnsurePyreflyConfigPhase",),
            ".phases.ensure_pyright": ("FlextInfraEnsurePyrightConfigPhase",),
            ".phases.ensure_ruff": ("FlextInfraEnsureRuffConfigPhase",),
            ".phases.inject_comments": ("FlextInfraInjectCommentsPhase",),
            ".phases.tool_tables": ("FlextInfraToolTablesPhase",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
