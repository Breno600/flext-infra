# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.gates package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.gates.bandit import FlextInfraBanditGate
    from flext_infra.gates.base_gate import FlextInfraGate
    from flext_infra.gates.direnv import FlextInfraDirenvGate
    from flext_infra.gates.duplication import FlextInfraDuplicationGate
    from flext_infra.gates.fresh_import import FlextInfraFreshImportGate
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
    "FlextInfraFreshImportGate",
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

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraBanditGate": ".bandit",
        "FlextInfraDirenvGate": ".direnv",
        "FlextInfraDuplicationGate": ".duplication",
        "FlextInfraFreshImportGate": ".fresh_import",
        "FlextInfraGate": ".base_gate",
        "FlextInfraIndexDeclarationsGate": ".index_declarations",
        "FlextInfraLayoutGate": ".layout",
        "FlextInfraLocCapGate": ".loc_cap",
        "FlextInfraMarkdownCodeGate": ".markdown_code",
        "FlextInfraMarkdownCodeSources": ".markdown_code_sources",
        "FlextInfraMarkdownFormatGate": ".markdown_format",
        "FlextInfraMarkdownGate": ".markdown",
        "FlextInfraMarkdownGateBase": ".markdown_support",
        "FlextInfraMypyGate": ".mypy",
        "FlextInfraPyreflyGate": ".pyrefly",
        "FlextInfraPyrightGate": ".pyright",
        "FlextInfraRuffFormatGate": ".ruff_format",
        "FlextInfraRuffLintGate": ".ruff_lint",
        "FlextInfraRuntimeCensusGate": ".runtime_census",
        "FlextInfraScannerGateMixin": ".scanner_gate",
        "FlextInfraSmellsGate": ".smells",
    }),
    public_exports=__all__,
)
