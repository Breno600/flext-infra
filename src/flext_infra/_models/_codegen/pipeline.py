"""Phase analysis and pipeline state models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Literal, Self

from flext_cli import m, u

from flext_infra import p, t
from flext_infra._models._codegen.fix import FlextInfraModelsCodegenFixModels
from flext_infra._models._codegen.lazy_init import FlextInfraModelsCodegenLazyInitModels
from flext_infra._models._codegen.scaffold import FlextInfraModelsCodegenScaffoldModels
from flext_infra._models._config.base import FlextInfraConfigModels
from flext_infra._models.mixins import FlextInfraModelsMixins as mm


class FlextInfraModelsCodegenPipelineModels:
    """Phase analysis and pipeline state models."""

    class CodegenCommand(mm.WriteMixin, m.ContractModel):
        """CLI request shared by Rope-backed codegen operations."""

        check_only: Annotated[bool, m.Field(description="Validate without writing")] = (
            False
        )
        output_format: Annotated[
            str,
            m.Field(description="Output format (json|text)"),
        ] = "text"

    class CodegenAutoFixCommand(CodegenCommand):
        """Auto-fix request with its one additional rule selector."""

        rules_only: Annotated[
            bool,
            m.Field(description="Run only deterministic namespace rules"),
        ] = False

    class CandidateBootstrapCommand(m.ContractModel):
        """Typed public request for an atomic declared Makefile campaign."""

        repository_root: Annotated[
            Path,
            m.Field(description="Repository with the candidate declarations"),
        ]
        dry_run: Annotated[bool, m.Field(description="Validate without writing")] = (
            False
        )
        check_only: Annotated[bool, m.Field(description="Validate without writing")] = (
            False
        )
        apply_changes: Annotated[
            bool,
            m.Field(description="Apply the complete candidate campaign"),
        ] = True

    class CodegenPhaseAnalysis(m.ArbitraryTypesModel):
        """Immutable planner receipt reused for publication verification."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        phase: Annotated[
            Literal[
                "docs",
                "lazy-init",
                "mod-text",
                "semantic",
                "candidate-bootstrap",
                "conform-bootstrap",
            ],
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
            """Reject ambiguous receipts with competing path authorities.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If codegen phase receipt destination paths must be unique;
                    or if codegen phase receipt input paths must be unique.

            """
            file_paths = tuple(file.path for file in self.files)
            if len(set(file_paths)) != len(file_paths):
                msg = "codegen phase receipt destination paths must be unique"
                raise ValueError(msg)
            input_paths = tuple(state.path for state in self.inputs)
            if len(set(input_paths)) != len(input_paths):
                msg = "codegen phase receipt input paths must be unique"
                raise ValueError(msg)
            return self

    class CodegenConformPorts(m.ArbitraryTypesModel):
        """Collaborators the complete conform crosses into, wired by the facade.

        Docs rendering is another service family; the composition root binds
        its implementation once and conform only consumes this port.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            frozen=True,
            extra="forbid",
            arbitrary_types_allowed=True,
        )

        docs_planner: Annotated[
            p.Infra.DocsArtifactPlannerFactory,
            m.Field(description="Builds the docs planner for one conform scope"),
        ]

    class CodegenPipelineState(m.ArbitraryTypesModel):
        """Typed inter-stage state for the codegen pipeline — Pydantic v2 model."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid",
            arbitrary_types_allowed=True,
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
