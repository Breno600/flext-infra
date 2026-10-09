# AUTO-GENERATED FILE — Regenerate with: make gen
"""Tests.unit.validate package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from tests.unit.validate import _fixtures


__all__: tuple[str, ...] = ("_fixtures",)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({"_fixtures": "._fixtures"}),
    public_exports=__all__,
)
