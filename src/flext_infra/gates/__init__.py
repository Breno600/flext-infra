# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.gates package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.gates.bandit import FlextInfraBanditGate
    from flext_infra.gates.base_gate import FlextInfraGate
    from flext_infra.gates.direnv import FlextInfraDirenvGate
    from flext_infra.gates.duplication import FlextInfraDuplicationGate
    from flext_infra.gates.index_declarations import FlextInfraIndexDeclarationsGate
    from flext_infra.gates.layout import FlextInfraLayoutGate
    from flext_infra.gates.loc_cap import FlextInfraLocCapGate
    from flext_infra.gates.markdown import FlextInfraMarkdownGate
    from flext_infra.gates.markdown_code import FlextInfraMarkdownCodeGate
    from flext_infra.gates.markdown_code_sources import FlextInfraMarkdownCodeSources
    from flext_infra.gates.markdown_format import FlextInfraMarkdownFormatGate
    from flext_infra.gates.markdown_support import FlextInfraMarkdownGateBase
    from flext_infra.gates.mypy import FlextInfraMypyGate
    from flext_infra.gates.pyrefly import FlextInfraPyreflyGate
    from flext_infra.gates.pyright import FlextInfraPyrightGate
    from flext_infra.gates.ruff_format import FlextInfraRuffFormatGate
    from flext_infra.gates.ruff_lint import FlextInfraRuffLintGate
    from flext_infra.gates.runtime_census import FlextInfraRuntimeCensusGate
    from flext_infra.gates.scanner_gate import FlextInfraScannerGateMixin
    from flext_infra.gates.smells import FlextInfraSmellsGate

__all__: tuple[str, ...] = (
    "FlextInfraBanditGate",
    "FlextInfraDirenvGate",
    "FlextInfraDuplicationGate",
    "FlextInfraGate",
    "FlextInfraIndexDeclarationsGate",
    "FlextInfraLayoutGate",
    "FlextInfraLocCapGate",
    "FlextInfraMarkdownCodeGate",
    "FlextInfraMarkdownCodeSources",
    "FlextInfraMarkdownFormatGate",
    "FlextInfraMarkdownGate",
    "FlextInfraMarkdownGateBase",
    "FlextInfraMypyGate",
    "FlextInfraPyreflyGate",
    "FlextInfraPyrightGate",
    "FlextInfraRuffFormatGate",
    "FlextInfraRuffLintGate",
    "FlextInfraRuntimeCensusGate",
    "FlextInfraScannerGateMixin",
    "FlextInfraSmellsGate",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".bandit": ("FlextInfraBanditGate",),
            ".base_gate": ("FlextInfraGate",),
            ".direnv": ("FlextInfraDirenvGate",),
            ".duplication": ("FlextInfraDuplicationGate",),
            ".index_declarations": ("FlextInfraIndexDeclarationsGate",),
            ".layout": ("FlextInfraLayoutGate",),
            ".loc_cap": ("FlextInfraLocCapGate",),
            ".markdown": ("FlextInfraMarkdownGate",),
            ".markdown_code": ("FlextInfraMarkdownCodeGate",),
            ".markdown_code_sources": ("FlextInfraMarkdownCodeSources",),
            ".markdown_format": ("FlextInfraMarkdownFormatGate",),
            ".markdown_support": ("FlextInfraMarkdownGateBase",),
            ".mypy": ("FlextInfraMypyGate",),
            ".pyrefly": ("FlextInfraPyreflyGate",),
            ".pyright": ("FlextInfraPyrightGate",),
            ".ruff_format": ("FlextInfraRuffFormatGate",),
            ".ruff_lint": ("FlextInfraRuffLintGate",),
            ".runtime_census": ("FlextInfraRuntimeCensusGate",),
            ".scanner_gate": ("FlextInfraScannerGateMixin",),
            ".smells": ("FlextInfraSmellsGate",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
