"""Codegen models facade: joins the family modules via MRO."""

from __future__ import annotations

from ..codegen_render import FlextInfraModelsCodegenRender
from ..codegen_toolchain import FlextInfraModelsCodegenToolchain
from .fix import FlextInfraModelsCodegenFixModels
from .journal import FlextInfraModelsCodegenJournalModels
from .lazy_init import FlextInfraModelsCodegenLazyInitModels
from .pipeline import FlextInfraModelsCodegenPipelineModels
from .scaffold import FlextInfraModelsCodegenScaffoldModels
from .transaction import FlextInfraModelsCodegenTransactionModels


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
