"""Codegen models facade: joins the family modules via MRO.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._models._codegen.fix import FlextInfraModelsCodegenFixModels
from flext_infra._models._codegen.journal import FlextInfraModelsCodegenJournalModels
from flext_infra._models._codegen.lazy_init import FlextInfraModelsCodegenLazyInitModels
from flext_infra._models._codegen.pipeline import FlextInfraModelsCodegenPipelineModels
from flext_infra._models._codegen.scaffold import FlextInfraModelsCodegenScaffoldModels
from flext_infra._models._codegen.transaction import (
    FlextInfraModelsCodegenTransactionModels,
)
from flext_infra._models.codegen_render import FlextInfraModelsCodegenRender
from flext_infra._models.codegen_toolchain import FlextInfraModelsCodegenToolchain


class FlextInfraCodegen(
    FlextInfraModelsCodegenRender,
    FlextInfraModelsCodegenToolchain,
    FlextInfraModelsCodegenJournalModels,
    FlextInfraModelsCodegenTransactionModels,
    FlextInfraModelsCodegenScaffoldModels,
    FlextInfraModelsCodegenFixModels,
    FlextInfraModelsCodegenLazyInitModels,
    FlextInfraModelsCodegenPipelineModels,
):
    """Models for codegen census, scaffold, and auto-fix pipelines."""


__all__: list[str] = ["FlextInfraCodegen"]
