# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.workspace package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.workspace._governance import FlextInfraWorkspaceGovernanceMixin
    from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
    from flext_infra.workspace.environment import FlextInfraWorkspaceEnvironmentMixin
    from flext_infra.workspace.environment_contracts import (
        FlextInfraWorkspaceEnvironmentContracts,
    )
    from flext_infra.workspace.environment_provenance import (
        FlextInfraWorkspaceEnvironmentProvenance,
    )
    from flext_infra.workspace.flext_binding import FlextInfraFlextBindingService
    from flext_infra.workspace.propagation import FlextInfraWorkspacePropagation
    from flext_infra.workspace.rope import FlextInfraRopeWorkspace

__all__: tuple[str, ...] = (
    "FlextInfraFlextBindingService",
    "FlextInfraRopeWorkspace",
    "FlextInfraWorkspaceDetector",
    "FlextInfraWorkspaceEnvironmentContracts",
    "FlextInfraWorkspaceEnvironmentMixin",
    "FlextInfraWorkspaceEnvironmentProvenance",
    "FlextInfraWorkspaceGovernanceMixin",
    "FlextInfraWorkspacePropagation",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._governance": ("FlextInfraWorkspaceGovernanceMixin",),
            ".detector": ("FlextInfraWorkspaceDetector",),
            ".environment": ("FlextInfraWorkspaceEnvironmentMixin",),
            ".environment_contracts": ("FlextInfraWorkspaceEnvironmentContracts",),
            ".environment_provenance": ("FlextInfraWorkspaceEnvironmentProvenance",),
            ".flext_binding": ("FlextInfraFlextBindingService",),
            ".propagation": ("FlextInfraWorkspacePropagation",),
            ".rope": ("FlextInfraRopeWorkspace",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
