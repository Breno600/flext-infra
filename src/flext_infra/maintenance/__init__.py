# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.maintenance package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.maintenance.clean import FlextInfraCleanService
    from flext_infra.maintenance.python_version import FlextInfraPythonVersionEnforcer
    from flext_infra.maintenance.sonarcloud import FlextInfraSonarcloudSettingsSync

__all__: tuple[str, ...] = (
    "FlextInfraCleanService",
    "FlextInfraPythonVersionEnforcer",
    "FlextInfraSonarcloudSettingsSync",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".clean": ("FlextInfraCleanService",),
            ".python_version": ("FlextInfraPythonVersionEnforcer",),
            ".sonarcloud": ("FlextInfraSonarcloudSettingsSync",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
