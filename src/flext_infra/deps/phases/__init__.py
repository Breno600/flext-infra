# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.deps.phases package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .consolidate_groups import FlextInfraConsolidateGroupsPhase
    from .ensure_packaging import FlextInfraEnsurePackagingPhase
    from .ensure_pyrefly import FlextInfraEnsurePyreflyConfigPhase
    from .ensure_pyright import FlextInfraEnsurePyrightConfigPhase
    from .ensure_ruff import FlextInfraEnsureRuffConfigPhase
    from .inject_comments import FlextInfraInjectCommentsPhase
    from .tool_tables import FlextInfraToolTablesPhase


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
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
