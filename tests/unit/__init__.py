# AUTO-GENERATED FILE — Regenerate with: make gen
"""Tests.unit package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from . import (
        _utilities,
        check,
        codegen,
        codemod,
        container,
        deps,
        detectors,
        discovery,
        docs,
        gates,
        github,
        io,
        maintenance,
        promoted,
        refactor,
        release,
        transformers,
        validate,
        workspace,
    )


__all__: tuple[str, ...] = (
    "_utilities",
    "check",
    "codegen",
    "codemod",
    "container",
    "deps",
    "detectors",
    "discovery",
    "docs",
    "gates",
    "github",
    "io",
    "maintenance",
    "promoted",
    "refactor",
    "release",
    "transformers",
    "validate",
    "workspace",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._utilities": ("_utilities",),
            ".check": ("check",),
            ".codegen": ("codegen",),
            ".codemod": ("codemod",),
            ".container": ("container",),
            ".deps": ("deps",),
            ".detectors": ("detectors",),
            ".discovery": ("discovery",),
            ".docs": ("docs",),
            ".gates": ("gates",),
            ".github": ("github",),
            ".io": ("io",),
            ".maintenance": ("maintenance",),
            ".promoted": ("promoted",),
            ".refactor": ("refactor",),
            ".release": ("release",),
            ".transformers": ("transformers",),
            ".validate": ("validate",),
            ".workspace": ("workspace",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
