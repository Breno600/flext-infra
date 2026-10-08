"""Census and scaffold models for the codegen pipeline.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, ClassVar

from flext_cli import m

from flext_infra import t
from flext_infra._models.mixins import FlextInfraModelsMixins


class FlextInfraModelsCodegenScaffoldModels:
    """Census and scaffold models for the codegen pipeline."""

    class CensusViolation(
        FlextInfraModelsMixins.RequiredNonNegativeLineMixin,
        m.ArbitraryTypesModel,
    ):
        """A single namespace violation detected by the census service."""

        module: t.NonEmptyStr = m.Field(description="Module file path")
        rule: t.NonEmptyStr = m.Field(description="Violated catalog rule identifier")
        message: t.NonEmptyStr = m.Field(description="Human-readable violation message")
        fixable: bool = m.Field(description="Whether this violation can be auto-fixed")

    class CensusReport(FlextInfraModelsMixins.ProjectNameMixin, m.ArbitraryTypesModel):
        """Aggregated census report for a single project."""

        violations: Annotated[
            Sequence[FlextInfraModelsCodegenScaffoldModels.CensusViolation],
            m.Field(description="Detected violations"),
        ] = m.Field(default_factory=tuple)
        total: Annotated[t.NonNegativeInt, m.Field(description="Total violation count")]
        fixable: Annotated[
            t.NonNegativeInt,
            m.Field(description="Count of auto-fixable violations"),
        ]

    class ScaffoldResult(
        FlextInfraModelsMixins.ProjectNameMixin,
        m.ArbitraryTypesModel,
    ):
        """Result of scaffolding base modules for a project.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        files_created: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Newly created file paths",
        )
        files_skipped: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Skipped (already existing) file paths",
        )

    class ScaffoldDirRequest(m.ArbitraryTypesModel):
        """Directory-level scaffold request and accumulation state."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            arbitrary_types_allowed=True,
            revalidate_instances="never",
        )

        target_dir: Annotated[Path, m.Field(description="Directory to scaffold")]
        prefix: Annotated[str, m.Field(description="Generated class name prefix")]
        modules: Annotated[
            t.VariadicTuple[t.Quad[str, str, str, str]],
            m.Field(description="Module skeleton definitions"),
        ]
        test_prefix: Annotated[str, m.Field(description="Generated test class prefix")]
        base_module: Annotated[
            t.NonEmptyStr,
            m.Field(description="Explicit module owning every generated base class"),
        ]
        project_module: Annotated[
            t.NonEmptyStr,
            m.Field(description="Owning package imported by generated test modules"),
        ]
        test_module: Annotated[
            bool,
            m.Field(description="Whether this directory renders test module skeletons"),
        ]
        dry_run: Annotated[
            bool,
            m.Field(description="Whether to report creations without writing"),
        ]
        files_created: Annotated[
            t.MutableSequenceOf[str],
            m.Field(description="Created file accumulator"),
        ]
        files_skipped: Annotated[
            t.MutableSequenceOf[str],
            m.Field(description="Skipped file accumulator"),
        ]
