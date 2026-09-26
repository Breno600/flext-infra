# AUTO-GENERATED FILE — Regenerate with: make gen
"""Tests.unit.codegen package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .test_codegen_make_runtime_identity import (
        TestsFlextInfraCodegenMakeRuntimeIdentity,
    )


__all__: tuple[str, ...] = ("TestsFlextInfraCodegenMakeRuntimeIdentity",)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".test_codegen_make_runtime_identity": (
                "TestsFlextInfraCodegenMakeRuntimeIdentity",
            )
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
