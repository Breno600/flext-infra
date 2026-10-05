# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.transformers package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.transformers._semantic_publication import (
        FlextInfraSemanticPublication,
    )
    from flext_infra.transformers.rope_transformer import FlextInfraRopeTransformer


__all__: tuple[str, ...] = (
    "FlextInfraRopeTransformer",
    "FlextInfraSemanticPublication",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraRopeTransformer": ".rope_transformer",
        "FlextInfraSemanticPublication": "._semantic_publication",
    }),
    public_exports=__all__,
)
