# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.deps.phases package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.deps.phases.consolidate_groups import (
        FlextInfraConsolidateGroupsPhase,
    )
    from flext_infra.deps.phases.ensure_packaging import FlextInfraEnsurePackagingPhase
    from flext_infra.deps.phases.ensure_pyrefly import (
        FlextInfraEnsurePyreflyConfigPhase,
    )
    from flext_infra.deps.phases.ensure_pyright import (
        FlextInfraEnsurePyrightConfigPhase,
    )
    from flext_infra.deps.phases.ensure_ruff import FlextInfraEnsureRuffConfigPhase
    from flext_infra.deps.phases.inject_comments import FlextInfraInjectCommentsPhase
    from flext_infra.deps.phases.tool_tables import FlextInfraToolTablesPhase


__all__: tuple[str, ...] = (
    "FlextInfraConsolidateGroupsPhase",
    "FlextInfraEnsurePackagingPhase",
    "FlextInfraEnsurePyreflyConfigPhase",
    "FlextInfraEnsurePyrightConfigPhase",
    "FlextInfraEnsureRuffConfigPhase",
    "FlextInfraInjectCommentsPhase",
    "FlextInfraToolTablesPhase",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraConsolidateGroupsPhase": (
            ".consolidate_groups",
            "FlextInfraConsolidateGroupsPhase",
        ),
        "FlextInfraEnsurePackagingPhase": (
            ".ensure_packaging",
            "FlextInfraEnsurePackagingPhase",
        ),
        "FlextInfraEnsurePyreflyConfigPhase": (
            ".ensure_pyrefly",
            "FlextInfraEnsurePyreflyConfigPhase",
        ),
        "FlextInfraEnsurePyrightConfigPhase": (
            ".ensure_pyright",
            "FlextInfraEnsurePyrightConfigPhase",
        ),
        "FlextInfraEnsureRuffConfigPhase": (
            ".ensure_ruff",
            "FlextInfraEnsureRuffConfigPhase",
        ),
        "FlextInfraInjectCommentsPhase": (
            ".inject_comments",
            "FlextInfraInjectCommentsPhase",
        ),
        "FlextInfraToolTablesPhase": (".tool_tables", "FlextInfraToolTablesPhase"),
    }),
    public_exports=__all__,
)
