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
    from flext_infra._utilities._pyproject.base import (
        FlextInfraUtilitiesPyprojectConformBase,
    )
    from flext_infra._utilities._pyproject.document import (
        FlextInfraUtilitiesPyprojectDocument,
    )
    from flext_infra._utilities._pyproject.overlay import (
        FlextInfraUtilitiesPyprojectOverlay,
    )
    from flext_infra._utilities._pyproject.requirements import (
        FlextInfraUtilitiesPyprojectRequirements,
    )
    from flext_infra._utilities._pyproject.session import (
        FlextInfraUtilitiesPyprojectSession,
    )
    from flext_infra._utilities._pyproject.toml_phases import (
        FlextInfraUtilitiesPyprojectTomlPhases,
    )
    from flext_infra._utilities._pyproject.uv_sources import (
        FlextInfraUtilitiesPyprojectUvSources,
    )


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
        "FlextInfraUtilitiesPyprojectConformBase": (
            ".base",
            "FlextInfraUtilitiesPyprojectConformBase",
        ),
        "FlextInfraUtilitiesPyprojectDocument": (
            ".document",
            "FlextInfraUtilitiesPyprojectDocument",
        ),
        "FlextInfraUtilitiesPyprojectOverlay": (
            ".overlay",
            "FlextInfraUtilitiesPyprojectOverlay",
        ),
        "FlextInfraUtilitiesPyprojectRequirements": (
            ".requirements",
            "FlextInfraUtilitiesPyprojectRequirements",
        ),
        "FlextInfraUtilitiesPyprojectSession": (
            ".session",
            "FlextInfraUtilitiesPyprojectSession",
        ),
        "FlextInfraUtilitiesPyprojectTomlPhases": (
            ".toml_phases",
            "FlextInfraUtilitiesPyprojectTomlPhases",
        ),
        "FlextInfraUtilitiesPyprojectUvSources": (
            ".uv_sources",
            "FlextInfraUtilitiesPyprojectUvSources",
        ),
    }),
    public_exports=__all__,
)
