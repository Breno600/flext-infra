# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.check package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.check._workspace_check_reports import (
        FlextInfraWorkspaceCheckReportsMixin,
    )
    from flext_infra.check.gate_registry import FlextInfraGateRegistry
    from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker
    from flext_infra.check.workspace_check_gates import (
        FlextInfraWorkspaceCheckGatesMixin,
    )


__all__: tuple[str, ...] = (
    "FlextInfraGateRegistry",
    "FlextInfraWorkspaceCheckGatesMixin",
    "FlextInfraWorkspaceCheckReportsMixin",
    "FlextInfraWorkspaceChecker",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraGateRegistry": (".gate_registry", "FlextInfraGateRegistry"),
        "FlextInfraWorkspaceCheckGatesMixin": (
            ".workspace_check_gates",
            "FlextInfraWorkspaceCheckGatesMixin",
        ),
        "FlextInfraWorkspaceCheckReportsMixin": (
            "._workspace_check_reports",
            "FlextInfraWorkspaceCheckReportsMixin",
        ),
        "FlextInfraWorkspaceChecker": (
            ".workspace_check",
            "FlextInfraWorkspaceChecker",
        ),
    }),
    public_exports=__all__,
)
