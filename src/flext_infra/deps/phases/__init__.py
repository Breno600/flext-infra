# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.deps.phases package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports
from flext_infra.deps.phases.consolidate_groups import FlextInfraConsolidateGroupsPhase
from flext_infra.deps.phases.ensure_packaging import FlextInfraEnsurePackagingPhase
from flext_infra.deps.phases.ensure_pyrefly import FlextInfraEnsurePyreflyConfigPhase
from flext_infra.deps.phases.ensure_pyright import FlextInfraEnsurePyrightConfigPhase
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

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".consolidate_groups": ("FlextInfraConsolidateGroupsPhase",),
            ".ensure_packaging": ("FlextInfraEnsurePackagingPhase",),
            ".ensure_pyrefly": ("FlextInfraEnsurePyreflyConfigPhase",),
            ".ensure_pyright": ("FlextInfraEnsurePyrightConfigPhase",),
            ".ensure_ruff": ("FlextInfraEnsureRuffConfigPhase",),
            ".inject_comments": ("FlextInfraInjectCommentsPhase",),
            ".tool_tables": ("FlextInfraToolTablesPhase",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
