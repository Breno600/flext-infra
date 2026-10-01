# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.transformers package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from ._semantic_publication import FlextInfraSemanticPublication
    from .rope_transformer import FlextInfraRopeTransformer


__all__: tuple[str, ...] = (
    "FlextInfraRopeTransformer",
    "FlextInfraSemanticPublication",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._semantic_publication": ("FlextInfraSemanticPublication",),
            ".rope_transformer": ("FlextInfraRopeTransformer",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
