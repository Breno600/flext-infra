# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Promoted package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._utilities._promoted.commands import (
        FlextInfraUtilitiesPromotedCommands,
    )
    from flext_infra._utilities._promoted.execution import (
        FlextInfraUtilitiesPromotedExecution,
    )
    from flext_infra._utilities._promoted.invocation import (
        FlextInfraUtilitiesPromotedInvocation,
    )
    from flext_infra._utilities._promoted.rendering import (
        FlextInfraUtilitiesPromotedRendering,
    )
    from flext_infra._utilities._promoted.workspace import (
        FlextInfraUtilitiesPromotedWorkspace,
    )

__all__: tuple[str, ...] = (
    "FlextInfraUtilitiesPromotedCommands",
    "FlextInfraUtilitiesPromotedExecution",
    "FlextInfraUtilitiesPromotedInvocation",
    "FlextInfraUtilitiesPromotedRendering",
    "FlextInfraUtilitiesPromotedWorkspace",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".commands": ("FlextInfraUtilitiesPromotedCommands",),
            ".execution": ("FlextInfraUtilitiesPromotedExecution",),
            ".invocation": ("FlextInfraUtilitiesPromotedInvocation",),
            ".rendering": ("FlextInfraUtilitiesPromotedRendering",),
            ".workspace": ("FlextInfraUtilitiesPromotedWorkspace",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
