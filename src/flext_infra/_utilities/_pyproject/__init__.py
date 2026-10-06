# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Pyproject package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectConformBase
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectDocument
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectOverlay
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectRequirements
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectSession
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectTomlPhases
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectUvSources


__all__: tuple[str, ...] = (
    "FlextInfraUtilitiesPyprojectConformBase",
    "FlextInfraUtilitiesPyprojectDocument",
    "FlextInfraUtilitiesPyprojectOverlay",
    "FlextInfraUtilitiesPyprojectRequirements",
    "FlextInfraUtilitiesPyprojectSession",
    "FlextInfraUtilitiesPyprojectTomlPhases",
    "FlextInfraUtilitiesPyprojectUvSources",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraUtilitiesPyprojectConformBase": ".base",
        "FlextInfraUtilitiesPyprojectDocument": ".document",
        "FlextInfraUtilitiesPyprojectOverlay": ".overlay",
        "FlextInfraUtilitiesPyprojectRequirements": ".requirements",
        "FlextInfraUtilitiesPyprojectSession": ".session",
        "FlextInfraUtilitiesPyprojectTomlPhases": ".toml_phases",
        "FlextInfraUtilitiesPyprojectUvSources": ".uv_sources",
    }),
    public_exports=__all__,
)
