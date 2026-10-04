# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.release package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.release._release_artifact import FlextInfraReleaseArtifactMixin
    from flext_infra.release._release_boundary import FlextInfraReleaseBoundaryMixin
    from flext_infra.release._release_build import FlextInfraReleaseBuildMixin
    from flext_infra.release._release_metadata import FlextInfraReleaseMetadataMixin
    from flext_infra.release._release_plan import FlextInfraReleasePlanMixin
    from flext_infra.release._release_project import FlextInfraReleaseProjectMixin
    from flext_infra.release._release_publish import FlextInfraReleasePublishMixin
    from flext_infra.release._release_source import FlextInfraReleaseSourceMixin
    from flext_infra.release.orchestrator import FlextInfraReleaseOrchestrator


__all__: tuple[str, ...] = (
    "FlextInfraReleaseArtifactMixin",
    "FlextInfraReleaseBoundaryMixin",
    "FlextInfraReleaseBuildMixin",
    "FlextInfraReleaseMetadataMixin",
    "FlextInfraReleaseOrchestrator",
    "FlextInfraReleasePlanMixin",
    "FlextInfraReleaseProjectMixin",
    "FlextInfraReleasePublishMixin",
    "FlextInfraReleaseSourceMixin",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraReleaseArtifactMixin": (
            "._release_artifact",
            "FlextInfraReleaseArtifactMixin",
        ),
        "FlextInfraReleaseBoundaryMixin": (
            "._release_boundary",
            "FlextInfraReleaseBoundaryMixin",
        ),
        "FlextInfraReleaseBuildMixin": (
            "._release_build",
            "FlextInfraReleaseBuildMixin",
        ),
        "FlextInfraReleaseMetadataMixin": (
            "._release_metadata",
            "FlextInfraReleaseMetadataMixin",
        ),
        "FlextInfraReleaseOrchestrator": (
            ".orchestrator",
            "FlextInfraReleaseOrchestrator",
        ),
        "FlextInfraReleasePlanMixin": ("._release_plan", "FlextInfraReleasePlanMixin"),
        "FlextInfraReleaseProjectMixin": (
            "._release_project",
            "FlextInfraReleaseProjectMixin",
        ),
        "FlextInfraReleasePublishMixin": (
            "._release_publish",
            "FlextInfraReleasePublishMixin",
        ),
        "FlextInfraReleaseSourceMixin": (
            "._release_source",
            "FlextInfraReleaseSourceMixin",
        ),
    }),
    public_exports=__all__,
)
