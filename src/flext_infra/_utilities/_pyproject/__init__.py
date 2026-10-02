# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Pyproject package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

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

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".base": ("FlextInfraUtilitiesPyprojectConformBase",),
            ".document": ("FlextInfraUtilitiesPyprojectDocument",),
            ".overlay": ("FlextInfraUtilitiesPyprojectOverlay",),
            ".requirements": ("FlextInfraUtilitiesPyprojectRequirements",),
            ".session": ("FlextInfraUtilitiesPyprojectSession",),
            ".toml_phases": ("FlextInfraUtilitiesPyprojectTomlPhases",),
            ".uv_sources": ("FlextInfraUtilitiesPyprojectUvSources",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
