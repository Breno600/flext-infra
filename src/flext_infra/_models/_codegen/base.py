"""Codegen models facade: joins the family modules via MRO.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._models import FlextInfraModelsCodegenFixModels
from flext_infra._models import FlextInfraModelsCodegenJournalModels
from flext_infra._models import FlextInfraModelsCodegenLazyInitModels
from flext_infra._models import FlextInfraModelsCodegenPipelineModels
from flext_infra._models import FlextInfraModelsCodegenScaffoldModels
from flext_infra._models import FlextInfraModelsCodegenTransactionModels
from flext_infra._models import FlextInfraModelsCodegenRender
from flext_infra._models import FlextInfraModelsCodegenToolchain


class FlextInfraCodegen(
    FlextInfraModelsCodegenToolchain,
    FlextInfraModelsCodegenRender,
    FlextInfraModelsCodegenJournalModels,
    FlextInfraModelsCodegenTransactionModels,
    FlextInfraModelsCodegenScaffoldModels,
    FlextInfraModelsCodegenFixModels,
    FlextInfraModelsCodegenLazyInitModels,
    FlextInfraModelsCodegenPipelineModels,
):
    """Models for codegen census, scaffold, and auto-fix pipelines."""


__all__: list[str] = ["FlextInfraCodegen"]
