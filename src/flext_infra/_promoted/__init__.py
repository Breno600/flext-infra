# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Promoted package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._promoted.base import FlextInfraPromotedBase
    from flext_infra._promoted.discovery import FlextInfraPromotedDiscovery
    from flext_infra._promoted.dispatch import FlextInfraPromotedDispatch
    from flext_infra._promoted.registry import FlextInfraPromotedRegistry


__all__: tuple[str, ...] = (
    "FlextInfraPromotedBase",
    "FlextInfraPromotedDiscovery",
    "FlextInfraPromotedDispatch",
    "FlextInfraPromotedRegistry",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraPromotedBase": (".base", "FlextInfraPromotedBase"),
        "FlextInfraPromotedDiscovery": (".discovery", "FlextInfraPromotedDiscovery"),
        "FlextInfraPromotedDispatch": (".dispatch", "FlextInfraPromotedDispatch"),
        "FlextInfraPromotedRegistry": (".registry", "FlextInfraPromotedRegistry"),
    }),
    public_exports=__all__,
)
