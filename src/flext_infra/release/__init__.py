# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.release package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from ._release_artifact import FlextInfraReleaseArtifactMixin
    from ._release_boundary import FlextInfraReleaseBoundaryMixin
    from ._release_build import FlextInfraReleaseBuildMixin
    from ._release_metadata import FlextInfraReleaseMetadataMixin
    from ._release_plan import FlextInfraReleasePlanMixin
    from ._release_project import FlextInfraReleaseProjectMixin
    from ._release_publish import FlextInfraReleasePublishMixin
    from ._release_source import FlextInfraReleaseSourceMixin
    from .orchestrator import FlextInfraReleaseOrchestrator


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
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
