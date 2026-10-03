# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.validate. Pytest Runner package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.validate._pytest_runner.base import FlextInfraPytestRunnerBase
    from flext_infra.validate._pytest_runner.command import (
        FlextInfraPytestRunnerCommand,
    )
    from flext_infra.validate._pytest_runner.execution import (
        FlextInfraPytestRunnerExecution,
    )
    from flext_infra.validate._pytest_runner.reports import (
        FlextInfraPytestRunnerReports,
    )

__all__: tuple[str, ...] = (
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
            ".reports": ("FlextInfraPytestRunnerReports",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
