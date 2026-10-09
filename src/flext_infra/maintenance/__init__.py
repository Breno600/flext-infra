# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.maintenance package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.maintenance.clean import FlextInfraCleanService
    from flext_infra.maintenance.python_version import FlextInfraPythonVersionEnforcer
    from flext_infra.maintenance.sonarcloud import FlextInfraSonarcloudSettingsSync
    from flext_infra.maintenance.sonarcloud_client import FlextInfraSonarcloudClient
    from flext_infra.maintenance.sonarcloud_issues import FlextInfraSonarcloudIssues


__all__: tuple[str, ...] = (
    "FlextInfraCleanService",
    "FlextInfraPythonVersionEnforcer",
    "FlextInfraSonarcloudClient",
    "FlextInfraSonarcloudIssues",
    "FlextInfraSonarcloudSettingsSync",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraCleanService": ".clean",
        "FlextInfraPythonVersionEnforcer": ".python_version",
        "FlextInfraSonarcloudClient": ".sonarcloud_client",
        "FlextInfraSonarcloudIssues": ".sonarcloud_issues",
        "FlextInfraSonarcloudSettingsSync": ".sonarcloud",
    }),
    public_exports=__all__,
)
