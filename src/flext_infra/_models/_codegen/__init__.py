# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Models. Codegen package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .base import FlextInfraCodegen
    from .fix import FlextInfraModelsCodegenFixModels
    from .journal import FlextInfraModelsCodegenJournalModels
    from .lazy_init import FlextInfraModelsCodegenLazyInitModels
    from .pipeline import FlextInfraModelsCodegenPipelineModels
    from .scaffold import FlextInfraModelsCodegenScaffoldModels
    from .transaction import FlextInfraModelsCodegenTransactionModels


__all__: tuple[str, ...] = (
    "FlextInfraCodegen",
    "FlextInfraModelsCodegenFixModels",
    "FlextInfraModelsCodegenJournalModels",
    "FlextInfraModelsCodegenLazyInitModels",
    "FlextInfraModelsCodegenPipelineModels",
    "FlextInfraModelsCodegenScaffoldModels",
    "FlextInfraModelsCodegenTransactionModels",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".base": ("FlextInfraCodegen",),
            ".fix": ("FlextInfraModelsCodegenFixModels",),
            ".journal": ("FlextInfraModelsCodegenJournalModels",),
            ".lazy_init": ("FlextInfraModelsCodegenLazyInitModels",),
            ".pipeline": ("FlextInfraModelsCodegenPipelineModels",),
            ".scaffold": ("FlextInfraModelsCodegenScaffoldModels",),
            ".transaction": ("FlextInfraModelsCodegenTransactionModels",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
