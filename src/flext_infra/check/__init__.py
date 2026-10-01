# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.check package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from ._workspace_check_reports import FlextInfraWorkspaceCheckReportsMixin
    from .gate_registry import FlextInfraGateRegistry
    from .workspace_check import FlextInfraWorkspaceChecker
    from .workspace_check_gates import FlextInfraWorkspaceCheckGatesMixin


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
