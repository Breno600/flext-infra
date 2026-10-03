# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Rope Analysis package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._utilities._rope_analysis.asthelpers import (
        FlextInfraUtilitiesRopeAnalysisAstHelpers,
    )
    from flext_infra._utilities._rope_analysis.base import (
        FlextInfraUtilitiesRopeAnalysisBase,
    )
    from flext_infra._utilities._rope_analysis.exports import (
        FlextInfraUtilitiesRopeAnalysisExports,
    )
    from flext_infra._utilities._rope_analysis.importstate import (
        FlextInfraUtilitiesRopeAnalysisImportState,
    )
    from flext_infra._utilities._rope_analysis.sourcescan import (
        FlextInfraUtilitiesRopeAnalysisSourceScan,
    )

__all__: tuple[str, ...] = (
    "FlextInfraUtilitiesRopeAnalysisAstHelpers",
    "FlextInfraUtilitiesRopeAnalysisBase",
    "FlextInfraUtilitiesRopeAnalysisExports",
    "FlextInfraUtilitiesRopeAnalysisImportState",
    "FlextInfraUtilitiesRopeAnalysisSourceScan",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".asthelpers": ("FlextInfraUtilitiesRopeAnalysisAstHelpers",),
            ".base": ("FlextInfraUtilitiesRopeAnalysisBase",),
            ".exports": ("FlextInfraUtilitiesRopeAnalysisExports",),
            ".importstate": ("FlextInfraUtilitiesRopeAnalysisImportState",),
            ".sourcescan": ("FlextInfraUtilitiesRopeAnalysisSourceScan",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
