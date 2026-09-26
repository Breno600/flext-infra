# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.gates package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .abstraction_boundary import FlextInfraAbstractionBoundaryGate
    from .bandit import FlextInfraBanditGate
    from .base_gate import FlextInfraGate, FlextInfraScannerGateMixin
    from .canonical_alias import FlextInfraCanonicalAliasGate
    from .deferred_self_reference import FlextInfraDeferredSelfReferenceGate
    from .direnv import FlextInfraDirenvGate
    from .duplication import FlextInfraDuplicationGate
    from .index_declarations import FlextInfraIndexDeclarationsGate
    from .layout import FlextInfraLayoutGate
    from .loc_cap import FlextInfraLocCapGate
    from .markdown import FlextInfraMarkdownGate
    from .markdown_code import FlextInfraMarkdownCodeGate
    from .markdown_code_sources import (
        is_syntax_broken,
        source_name,
        write_docstring_sources,
        write_fenced_block_sources,
    )
    from .markdown_format import FlextInfraMarkdownFormatGate
    from .markdown_support import (
        FlextInfraMarkdownGateBase,
        collect_markdown_files,
        read_ignore_patterns,
    )
    from .mypy import FlextInfraMypyGate
    from .namespace import FlextInfraNamespaceGate
    from .pyrefly import FlextInfraPyreflyGate
    from .pyright import FlextInfraPyrightGate
    from .ruff_format import FlextInfraRuffFormatGate
    from .ruff_lint import FlextInfraRuffLintGate
    from .runtime_census import FlextInfraRuntimeCensusGate
    from .silent_failure import FlextInfraSilentFailureGate
    from .smells import FlextInfraSmellsGate
    from .tier_whitelist import FlextInfraTierWhitelistGate


__all__: tuple[str, ...] = (
    "FlextInfraAbstractionBoundaryGate",
    "FlextInfraBanditGate",
    "FlextInfraCanonicalAliasGate",
    "FlextInfraDeferredSelfReferenceGate",
    "FlextInfraDirenvGate",
    "FlextInfraDuplicationGate",
    "FlextInfraGate",
    "FlextInfraIndexDeclarationsGate",
    "FlextInfraLayoutGate",
    "FlextInfraLocCapGate",
    "FlextInfraMarkdownCodeGate",
    "FlextInfraMarkdownFormatGate",
    "FlextInfraMarkdownGate",
    "FlextInfraMarkdownGateBase",
    "FlextInfraMypyGate",
    "FlextInfraNamespaceGate",
    "FlextInfraPyreflyGate",
    "FlextInfraPyrightGate",
    "FlextInfraRuffFormatGate",
    "FlextInfraRuffLintGate",
    "FlextInfraRuntimeCensusGate",
    "FlextInfraScannerGateMixin",
    "FlextInfraSilentFailureGate",
    "FlextInfraSmellsGate",
    "FlextInfraTierWhitelistGate",
    "collect_markdown_files",
    "is_syntax_broken",
    "read_ignore_patterns",
    "source_name",
    "write_docstring_sources",
    "write_fenced_block_sources",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".abstraction_boundary": ("FlextInfraAbstractionBoundaryGate",),
            ".bandit": ("FlextInfraBanditGate",),
            ".base_gate": ("FlextInfraGate", "FlextInfraScannerGateMixin"),
            ".canonical_alias": ("FlextInfraCanonicalAliasGate",),
            ".deferred_self_reference": ("FlextInfraDeferredSelfReferenceGate",),
            ".direnv": ("FlextInfraDirenvGate",),
            ".duplication": ("FlextInfraDuplicationGate",),
            ".index_declarations": ("FlextInfraIndexDeclarationsGate",),
            ".layout": ("FlextInfraLayoutGate",),
            ".loc_cap": ("FlextInfraLocCapGate",),
            ".markdown": ("FlextInfraMarkdownGate",),
            ".markdown_code": ("FlextInfraMarkdownCodeGate",),
            ".markdown_code_sources": (
                "is_syntax_broken",
                "source_name",
                "write_docstring_sources",
                "write_fenced_block_sources",
            ),
            ".markdown_format": ("FlextInfraMarkdownFormatGate",),
            ".markdown_support": (
                "FlextInfraMarkdownGateBase",
                "collect_markdown_files",
                "read_ignore_patterns",
            ),
            ".mypy": ("FlextInfraMypyGate",),
            ".namespace": ("FlextInfraNamespaceGate",),
            ".pyrefly": ("FlextInfraPyreflyGate",),
            ".pyright": ("FlextInfraPyrightGate",),
            ".ruff_format": ("FlextInfraRuffFormatGate",),
            ".ruff_lint": ("FlextInfraRuffLintGate",),
            ".runtime_census": ("FlextInfraRuntimeCensusGate",),
            ".silent_failure": ("FlextInfraSilentFailureGate",),
            ".smells": ("FlextInfraSmellsGate",),
            ".tier_whitelist": ("FlextInfraTierWhitelistGate",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
