# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.workspace package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.workspace._governance import FlextInfraWorkspaceGovernanceMixin
    from flext_infra.workspace._rope_query import FlextInfraRopeQueryMixin
    from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
    from flext_infra.workspace.environment import FlextInfraWorkspaceEnvironmentMixin
    from flext_infra.workspace.environment_contracts import (
        FlextInfraWorkspaceEnvironmentContracts,
    )
    from flext_infra.workspace.environment_provenance import (
        FlextInfraWorkspaceEnvironmentProvenance,
    )
    from flext_infra.workspace.fleet_gaps import FlextInfraWorkspaceFleetGaps
    from flext_infra.workspace.flext_binding import FlextInfraFlextBindingService
    from flext_infra.workspace.lifecycle import FlextInfraWorkspaceLifecycle
    from flext_infra.workspace.propagation import FlextInfraWorkspacePropagation
    from flext_infra.workspace.rope import FlextInfraRopeWorkspace


__all__: tuple[str, ...] = (
    "FlextInfraFlextBindingService",
    "FlextInfraRopeQueryMixin",
    "FlextInfraRopeWorkspace",
    "FlextInfraWorkspaceDetector",
    "FlextInfraWorkspaceEnvironmentContracts",
    "FlextInfraWorkspaceEnvironmentMixin",
    "FlextInfraWorkspaceEnvironmentProvenance",
    "FlextInfraWorkspaceFleetGaps",
    "FlextInfraWorkspaceGovernanceMixin",
    "FlextInfraWorkspaceLifecycle",
    "FlextInfraWorkspacePropagation",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraFlextBindingService": ".flext_binding",
        "FlextInfraRopeQueryMixin": "._rope_query",
        "FlextInfraRopeWorkspace": ".rope",
        "FlextInfraWorkspaceDetector": ".detector",
        "FlextInfraWorkspaceEnvironmentContracts": ".environment_contracts",
        "FlextInfraWorkspaceEnvironmentMixin": ".environment",
        "FlextInfraWorkspaceEnvironmentProvenance": ".environment_provenance",
        "FlextInfraWorkspaceFleetGaps": ".fleet_gaps",
        "FlextInfraWorkspaceGovernanceMixin": "._governance",
        "FlextInfraWorkspaceLifecycle": ".lifecycle",
        "FlextInfraWorkspacePropagation": ".propagation",
    }),
    public_exports=__all__,
)
