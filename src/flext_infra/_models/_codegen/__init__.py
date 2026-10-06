# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Models. Codegen package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._models import FlextInfraCodegen
    from flext_infra._models import FlextInfraModelsCodegenFixModels
    from flext_infra._models import FlextInfraModelsCodegenJournalModels
    from flext_infra._models import FlextInfraModelsCodegenLazyInitModels
    from flext_infra._models import FlextInfraModelsCodegenPipelineModels
    from flext_infra._models import FlextInfraModelsCodegenScaffoldModels
    from flext_infra._models import FlextInfraModelsCodegenTransactionModels


__all__: tuple[str, ...] = (
    "FlextInfraCodegen",
    "FlextInfraModelsCodegenFixModels",
    "FlextInfraModelsCodegenJournalModels",
    "FlextInfraModelsCodegenLazyInitModels",
    "FlextInfraModelsCodegenPipelineModels",
    "FlextInfraModelsCodegenScaffoldModels",
    "FlextInfraModelsCodegenTransactionModels",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraCodegen": ".base",
        "FlextInfraModelsCodegenFixModels": ".fix",
        "FlextInfraModelsCodegenJournalModels": ".journal",
        "FlextInfraModelsCodegenLazyInitModels": ".lazy_init",
        "FlextInfraModelsCodegenPipelineModels": ".pipeline",
        "FlextInfraModelsCodegenScaffoldModels": ".scaffold",
        "FlextInfraModelsCodegenTransactionModels": ".transaction",
    }),
    public_exports=__all__,
)
