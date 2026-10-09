# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.check package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports
from flext_infra.check._workspace_check_reports import (
    FlextInfraWorkspaceCheckReportsMixin,
)
from flext_infra.check.gate_registry import FlextInfraGateRegistry
from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker
from flext_infra.check.workspace_check_gates import FlextInfraWorkspaceCheckGatesMixin

__all__: tuple[str, ...] = (
    "FlextInfraGateRegistry",
    "FlextInfraWorkspaceCheckGatesMixin",
    "FlextInfraWorkspaceCheckReportsMixin",
    "FlextInfraWorkspaceChecker",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._workspace_check_reports": ("FlextInfraWorkspaceCheckReportsMixin",),
            ".gate_registry": ("FlextInfraGateRegistry",),
            ".workspace_check": ("FlextInfraWorkspaceChecker",),
            ".workspace_check_gates": ("FlextInfraWorkspaceCheckGatesMixin",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
