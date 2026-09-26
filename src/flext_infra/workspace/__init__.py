# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.workspace package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from ._governance import FlextInfraWorkspaceGovernanceMixin
    from ._orchestrator_discovery import FlextInfraWorkspaceOrchestratorDiscoveryMixin
    from ._orchestrator_execution import FlextInfraWorkspaceOrchestratorExecutionMixin
    from .detector import FlextInfraWorkspaceDetector
    from .environment import FlextInfraWorkspaceEnvironmentMixin
    from .environment_beads import (
        FlextInfraWorkspaceBeadsEnvironmentMixin,
        FlextInfraWorkspaceEnvironmentSync,
    )
    from .environment_contracts import FlextInfraWorkspaceEnvironmentContracts
    from .environment_provenance import FlextInfraWorkspaceEnvironmentProvenance
    from .flext_binding import FlextInfraFlextBindingService
    from .orchestrator import FlextInfraOrchestratorService
    from .propagation import FlextInfraWorkspacePropagation
    from .rope import FlextInfraRopeWorkspace


__all__: tuple[str, ...] = (
    "FlextInfraFlextBindingService",
    "FlextInfraOrchestratorService",
    "FlextInfraRopeWorkspace",
    "FlextInfraWorkspaceBeadsEnvironmentMixin",
    "FlextInfraWorkspaceDetector",
    "FlextInfraWorkspaceEnvironmentContracts",
    "FlextInfraWorkspaceEnvironmentMixin",
    "FlextInfraWorkspaceEnvironmentProvenance",
    "FlextInfraWorkspaceEnvironmentSync",
    "FlextInfraWorkspaceGovernanceMixin",
    "FlextInfraWorkspaceOrchestratorDiscoveryMixin",
    "FlextInfraWorkspaceOrchestratorExecutionMixin",
    "FlextInfraWorkspacePropagation",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._governance": ("FlextInfraWorkspaceGovernanceMixin",),
            "._orchestrator_discovery": (
                "FlextInfraWorkspaceOrchestratorDiscoveryMixin",
            ),
            "._orchestrator_execution": (
                "FlextInfraWorkspaceOrchestratorExecutionMixin",
            ),
            ".detector": ("FlextInfraWorkspaceDetector",),
            ".environment": ("FlextInfraWorkspaceEnvironmentMixin",),
            ".environment_beads": (
                "FlextInfraWorkspaceBeadsEnvironmentMixin",
                "FlextInfraWorkspaceEnvironmentSync",
            ),
            ".environment_contracts": ("FlextInfraWorkspaceEnvironmentContracts",),
            ".environment_provenance": ("FlextInfraWorkspaceEnvironmentProvenance",),
            ".flext_binding": ("FlextInfraFlextBindingService",),
            ".orchestrator": ("FlextInfraOrchestratorService",),
            ".propagation": ("FlextInfraWorkspacePropagation",),
            ".rope": ("FlextInfraRopeWorkspace",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
