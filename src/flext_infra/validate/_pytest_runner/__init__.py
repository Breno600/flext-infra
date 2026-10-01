# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.validate. Pytest Runner package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .base import FlextInfraPytestRunnerBase
    from .command import FlextInfraPytestRunnerCommand
    from .execution import FlextInfraPytestRunnerExecution
    from .inputs import FlextInfraPytestInputs
    from .reports import FlextInfraPytestRunnerReports


__all__: tuple[str, ...] = (
    "FlextInfraPytestInputs",
    "FlextInfraPytestRunnerBase",
    "FlextInfraPytestRunnerCommand",
    "FlextInfraPytestRunnerExecution",
    "FlextInfraPytestRunnerReports",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".base": ("FlextInfraPytestRunnerBase",),
            ".command": ("FlextInfraPytestRunnerCommand",),
            ".execution": ("FlextInfraPytestRunnerExecution",),
            ".inputs": ("FlextInfraPytestInputs",),
            ".reports": ("FlextInfraPytestRunnerReports",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
