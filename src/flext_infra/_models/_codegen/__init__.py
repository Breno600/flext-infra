# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Models. Codegen package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports
from flext_infra._models._codegen.base import FlextInfraCodegen
from flext_infra._models._codegen.fix import FlextInfraModelsCodegenFixModels
from flext_infra._models._codegen.journal import FlextInfraModelsCodegenJournalModels
from flext_infra._models._codegen.lazy_init import FlextInfraModelsCodegenLazyInitModels
from flext_infra._models._codegen.pipeline import FlextInfraModelsCodegenPipelineModels
from flext_infra._models._codegen.scaffold import FlextInfraModelsCodegenScaffoldModels
from flext_infra._models._codegen.transaction import (
    FlextInfraModelsCodegenTransactionModels,
)

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
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
