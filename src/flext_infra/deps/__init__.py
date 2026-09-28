# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.deps package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from . import _modernizer, phases
    from ._detection_runners import FlextInfraDependencyDetectionRunnersMixin
    from ._detector_runtime_steps import FlextInfraDependencyDetectorRuntimeSteps
    from ._extra_paths_sync import FlextInfraExtraPathsSyncMixin
    from ._floor_profile_writer import FlextInfraDepsFloorProfileWriter
    from ._modernizer.base import FlextInfraPyprojectModernizerBase
    from ._modernizer.document import FlextInfraPyprojectModernizerDocument
    from ._modernizer.run import FlextInfraPyprojectModernizerRun
    from ._modernizer.tooling import FlextInfraPyprojectModernizerTooling
    from ._pyrefly_fix_steps import FlextInfraConfigFixerSteps
    from .detection import FlextInfraDependencyDetectionService
    from .detection_analysis import FlextInfraDependencyDetectionAnalysis
    from .detector import FlextInfraRuntimeDevDependencyDetector
    from .detector_runtime import FlextInfraDependencyDetectorRuntime
    from .extra_paths import FlextInfraExtraPathsManager
    from .fix_pyrefly_config import FlextInfraConfigFixer
    from .modernizer import FlextInfraPyprojectModernizer
    from .phases.consolidate_groups import FlextInfraConsolidateGroupsPhase
    from .phases.ensure_packaging import FlextInfraEnsurePackagingPhase
    from .phases.ensure_pyrefly import FlextInfraEnsurePyreflyConfigPhase
    from .phases.ensure_pyright import FlextInfraEnsurePyrightConfigPhase
    from .phases.ensure_ruff import FlextInfraEnsureRuffConfigPhase
    from .phases.inject_comments import FlextInfraInjectCommentsPhase
    from .phases.tool_tables import FlextInfraToolTablesPhase


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
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
