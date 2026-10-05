# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Rope package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._utilities._rope.project import FlextInfraRopeProject


__all__: tuple[str, ...] = ("FlextInfraRopeProject",)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({"FlextInfraRopeProject": ".project"}),
    public_exports=__all__,
)
