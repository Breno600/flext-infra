# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.release package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

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

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._release_artifact": ("FlextInfraReleaseArtifactMixin",),
            "._release_boundary": ("FlextInfraReleaseBoundaryMixin",),
            "._release_build": ("FlextInfraReleaseBuildMixin",),
            "._release_metadata": ("FlextInfraReleaseMetadataMixin",),
            "._release_plan": ("FlextInfraReleasePlanMixin",),
            "._release_project": ("FlextInfraReleaseProjectMixin",),
            "._release_publish": ("FlextInfraReleasePublishMixin",),
            "._release_source": ("FlextInfraReleaseSourceMixin",),
            ".orchestrator": ("FlextInfraReleaseOrchestrator",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
