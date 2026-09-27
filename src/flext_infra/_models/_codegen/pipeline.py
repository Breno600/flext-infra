"""Phase analysis and pipeline state models."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal, Self

from flext_cli import m, u

from ... import p, t
from .._config.base import FlextInfraConfigModels
from .fix import FlextInfraModelsCodegenFixModels
from .lazy_init import FlextInfraModelsCodegenLazyInitModels
from .scaffold import FlextInfraModelsCodegenScaffoldModels


class FlextInfraModelsCodegenPipelineModels:
    """Phase analysis and pipeline state models."""

    class CodegenPhaseAnalysis(m.ArbitraryTypesModel):
        """Immutable planner receipt reused for publication verification."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        phase: Annotated[
            Literal["docs", "lazy-init", "mod-text", "semantic"],
            m.Field(description="Generation phase that produced this receipt"),
        ]
        files: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.CodegenFilePlan],
            m.Field(description="Ordered desired publication states"),
        ]
        inputs: Annotated[
            t.VariadicTuple[m.Cli.AtomicFileState],
            m.Field(description="Ordered complete authenticated planner inputs"),
        ]
        publications: Annotated[
            t.VariadicTuple[FlextInfraModelsCodegenLazyInitModels.LazyInitPlan],
            m.Field(description="Resolved export contracts verified before commit"),
        ] = ()

        @u.model_validator(mode="after")
        def _validate_unique_paths(self) -> Self:
            """Reject ambiguous receipts with competing path authorities."""
            file_paths = tuple(file.path for file in self.files)
            if len(set(file_paths)) != len(file_paths):
                msg = "codegen phase receipt destination paths must be unique"
                raise ValueError(msg)
            input_paths = tuple(state.path for state in self.inputs)
            if len(set(input_paths)) != len(input_paths):
                msg = "codegen phase receipt input paths must be unique"
                raise ValueError(msg)
            return self

    class CodegenPipelineState(m.ArbitraryTypesModel):
        """Typed inter-stage state for the codegen pipeline — Pydantic v2 model."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid", arbitrary_types_allowed=True
        )

        discovered_projects: Annotated[
            t.SequenceOf[p.Infra.ProjectInfo],
            m.Field(description="Projects discovered at pipeline start"),
        ] = ()
        census_service: Annotated[
            p.Infra.CodegenCensusService | None,
            m.Field(description="Cached census service for reuse across stages"),
        ] = None
        reports_before: Annotated[
            t.SequenceOf[FlextInfraModelsCodegenScaffoldModels.CensusReport],
            m.Field(description="Census reports collected before fixes"),
        ] = ()
        reports_after: Annotated[
            t.SequenceOf[FlextInfraModelsCodegenScaffoldModels.CensusReport],
            m.Field(description="Census reports collected after fixes"),
        ] = ()
        scaffold_results: Annotated[
            t.SequenceOf[FlextInfraModelsCodegenScaffoldModels.ScaffoldResult],
            m.Field(description="Scaffolding stage results"),
        ] = ()
        fix_results: Annotated[
            t.SequenceOf[FlextInfraModelsCodegenFixModels.AutoFixResult],
            m.Field(description="Auto-fix stage results"),
        ] = ()
