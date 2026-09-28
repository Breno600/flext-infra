"""Violation and helper classification models for the refactor subpackage."""

from __future__ import annotations

from typing import Annotated, ClassVar

from flext_core import m
from flext_infra import t

from ._defaults import immutable_empty_mapping
from .mixins import FlextInfraModelsMixins as mm


class FlextInfraModelsRefactorViolations:
    """Class-nesting violation, helper classification, and analysis report models."""

    class ClassNestingViolation(
        mm.ConfidenceLevelMixin, mm.FileLineViolationMixin, m.ArbitraryTypesModel
    ):
        """Loose top-level class and the facade its module policy derives for it."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)
        class_name: Annotated[t.NonEmptyStr, m.Field(description="Class name")]
        target_namespace: Annotated[
            str,
            m.Field(
                description=(
                    "Facade class derived from the module's namespace policy; "
                    "empty when the module declares no family to nest under"
                )
            ),
        ] = ""

    class ClassNestingReport(m.ArbitraryTypesModel):
        """Aggregated class-nesting analysis report."""

        violations_count: Annotated[
            t.NonNegativeInt, m.Field(description="Total violations")
        ]
        confidence_counts: t.IntMapping = m.Field(
            default_factory=immutable_empty_mapping, description="Confidence histogram"
        )
        violations: t.VariadicTuple[
            FlextInfraModelsRefactorViolations.ClassNestingViolation
        ] = m.Field(default_factory=tuple, description="Violation details")
        per_file_counts: t.IntMapping = m.Field(
            default_factory=immutable_empty_mapping,
            description="Violation counts per file",
        )

    class HelperClassification(m.ArbitraryTypesModel):
        """Classification result for a helper function."""

        file: Annotated[t.NonEmptyStr, m.Field(description="Source file")]
        function: Annotated[t.NonEmptyStr, m.Field(description="Function name")]
        category: Annotated[t.NonEmptyStr, m.Field(description="Assigned category")]
        target_namespace: Annotated[
            t.NonEmptyStr, m.Field(description="Target namespace path")
        ]
        dependencies: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Dependency symbols referenced by the helper.",
        )
        manual_review: Annotated[
            bool, m.Field(description="Whether manual review is required")
        ] = False
        review_reason: Annotated[
            str, m.Field(description="Manual review rationale")
        ] = ""

    class HelperClassificationReport(m.ArbitraryTypesModel):
        """Aggregated helper-function classification payload."""

        totals: t.IntMapping = m.Field(
            default_factory=immutable_empty_mapping, description="Category totals"
        )
        suggestions: t.VariadicTuple[
            FlextInfraModelsRefactorViolations.HelperClassification
        ] = m.Field(default_factory=tuple, description="Classification suggestions")
        manual_review: t.VariadicTuple[
            FlextInfraModelsRefactorViolations.HelperClassification
        ] = m.Field(default_factory=tuple, description="Manual-review candidates")

    class HelperFileAnalysis(m.ArbitraryTypesModel):
        """Helper file analysis."""

        suggestions: t.VariadicTuple[
            FlextInfraModelsRefactorViolations.HelperClassification
        ] = m.Field(
            default_factory=tuple, description="Helper classifications from one file"
        )
        totals: t.IntMapping = m.Field(
            default_factory=immutable_empty_mapping,
            description="Category totals for file helpers",
        )
        manual_review: t.VariadicTuple[
            FlextInfraModelsRefactorViolations.HelperClassification
        ] = m.Field(
            default_factory=tuple, description="Helpers requiring manual review"
        )

    class ViolationTopFileSection(m.ArbitraryTypesModel):
        """One ranked hotspot entry in violation analysis output."""

        file: Annotated[t.NonEmptyStr, m.Field(description="File path")]
        total: Annotated[
            t.NonNegativeInt, m.Field(description="Total violations in file")
        ]
        counts: t.IntMapping = m.Field(
            default_factory=immutable_empty_mapping, description="Per-pattern counts"
        )

    class ViolationAnalysisReport(m.ArbitraryTypesModel):
        """Full violation analysis report for refactor diagnostics."""

        totals: t.IntMapping = m.Field(
            default_factory=immutable_empty_mapping,
            description="Aggregate counts by pattern",
        )
        files: t.MappingKV[str, t.IntMapping] = m.Field(
            default_factory=immutable_empty_mapping,
            description="Per-file per-pattern counts",
        )
        top_files: t.VariadicTuple[
            FlextInfraModelsRefactorViolations.ViolationTopFileSection
        ] = m.Field(default_factory=tuple, description="Top hotspot files")
        files_scanned: Annotated[t.NonNegativeInt, m.Field(description="Files scanned")]
        helper_classification: FlextInfraModelsRefactorViolations.HelperClassificationReport = m.Field(
            description="Helper classification summary"
        )
        class_nesting: FlextInfraModelsRefactorViolations.ClassNestingReport = m.Field(
            description="Class nesting analysis summary"
        )


__all__: list[str] = ["FlextInfraModelsRefactorViolations"]
