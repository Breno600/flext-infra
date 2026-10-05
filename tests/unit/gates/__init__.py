# AUTO-GENERATED FILE — Regenerate with: make gen
"""Tests.unit.gates package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from tests.unit.gates.test_lint_informative_rules import (
        TestsFlextInfraLintInformativeRules,
    )


__all__: tuple[str, ...] = ("TestsFlextInfraLintInformativeRules",)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "TestsFlextInfraLintInformativeRules": ".test_lint_informative_rules",
    }),
    public_exports=__all__,
)
