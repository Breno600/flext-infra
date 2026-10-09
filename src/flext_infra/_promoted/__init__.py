# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Promoted package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports
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

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".base": ("FlextInfraPromotedBase",),
            ".discovery": ("FlextInfraPromotedDiscovery",),
            ".dispatch": ("FlextInfraPromotedDispatch",),
            ".registry": ("FlextInfraPromotedRegistry",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
