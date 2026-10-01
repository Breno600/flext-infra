# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.detectors package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.detectors.lsp_diagnostics import FlextInfraLspDiagnosticsDetector


__all__: tuple[str, ...] = ("FlextInfraLspDiagnosticsDetector",)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({".lsp_diagnostics": ("FlextInfraLspDiagnosticsDetector",)}),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
