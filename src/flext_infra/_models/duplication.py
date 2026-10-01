"""Typed jscpd report contracts for the duplication gate."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Self

from flext_core import m, u
from flext_infra import c, t


class FlextInfraModelsDuplication:
    """Strict external-boundary models for jscpd 5 reports."""

    class ProjectDuplicationOverrides(m.ContractModel):
        """Validated ``[tool.flext.project.duplication]`` overrides.

        One project's pyproject.toml may narrow the workspace-wide jscpd
        defaults; every field defaults to the canonical constant so a project
        with no overrides table gets the same behavior as the workspace scan.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid", frozen=True, populate_by_name=True
        )

        min_lines: Annotated[
            t.PositiveInt,
            m.Field(alias="min-lines", description="Minimum duplicated line count"),
        ] = c.Infra.JSCPD_MIN_LINES
        min_tokens: Annotated[
            t.PositiveInt,
            m.Field(alias="min-tokens", description="Minimum duplicated token count"),
        ] = c.Infra.JSCPD_MIN_TOKENS
        threshold_percent: Annotated[
            t.Percentage,
            m.Field(
                alias="threshold-percent",
                description="Maximum allowed duplication percentage",
            ),
        ] = c.Infra.JSCPD_THRESHOLD_PERCENT
        mode: Annotated[t.NonEmptyStr, m.Field(description="jscpd detection mode")] = (
            c.Infra.JSCPD_MODE
        )
        scope: Annotated[
            t.StrSequence, m.Field(description="Scope directory names")
        ] = c.Infra.JSCPD_SCOPE_DIRNAMES

    class JscpdConfig(m.ContractModel):
        """Complete generated jscpd invocation configuration."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid", frozen=True, populate_by_name=True
        )

        absolute: Annotated[t.StrictBool, m.Field(description="Emit absolute paths")]
        formats_exts: Annotated[
            t.MappingKV[str, t.StrSequence],
            m.Field(alias="formatsExts", description="Extensions by parser format"),
        ]
        ignore: Annotated[t.StrSequence, m.Field(description="Ignored path patterns")]
        min_lines: Annotated[
            t.PositiveInt,
            m.Field(alias="minLines", description="Minimum duplicated line count"),
        ]
        min_tokens: Annotated[
            t.PositiveInt,
            m.Field(alias="minTokens", description="Minimum duplicated token count"),
        ]
        mode: Annotated[t.NonEmptyStr, m.Field(description="jscpd detection mode")]
        no_colors: Annotated[
            t.StrictBool, m.Field(alias="noColors", description="Disable color output")
        ]
        no_tips: Annotated[
            t.StrictBool, m.Field(alias="noTips", description="Disable tip output")
        ]
        reporters: Annotated[
            t.StrSequence, m.Field(description="Required report formats")
        ]
        threshold: Annotated[
            t.Percentage, m.Field(description="Maximum allowed duplication percentage")
        ]

    class JscpdLocation(m.ContractModel):
        """One required source coordinate in a jscpd report."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        column: Annotated[
            t.NonNegativeInt,
            m.Field(description="Zero-based source column reported by jscpd"),
        ]
        line: Annotated[
            t.PositiveInt,
            m.Field(description="One-based source line reported by jscpd"),
        ]
        position: Annotated[
            t.NonNegativeInt,
            m.Field(description="Zero-based source offset reported by jscpd"),
        ]

    class JscpdFile(m.ContractModel):
        """One side of a detected clone."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid", frozen=True, populate_by_name=True
        )

        end: Annotated[t.PositiveInt, m.Field(description="Exclusive clone end offset")]
        end_location: Annotated[
            FlextInfraModelsDuplication.JscpdLocation,
            m.Field(alias="endLoc", description="Clone end coordinate"),
        ]
        name: Annotated[
            t.NonEmptyStr, m.Field(description="Absolute scanned source path")
        ]
        start: Annotated[
            t.NonNegativeInt, m.Field(description="Inclusive clone start offset")
        ]
        start_location: Annotated[
            FlextInfraModelsDuplication.JscpdLocation,
            m.Field(alias="startLoc", description="Clone start coordinate"),
        ]

    class JscpdDuplicate(m.ContractModel):
        """One complete two-sided clone from jscpd."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid", frozen=True, populate_by_name=True
        )

        first_file: Annotated[
            FlextInfraModelsDuplication.JscpdFile,
            m.Field(alias="firstFile", description="First clone source"),
        ]
        format_name: Annotated[
            t.NonEmptyStr,
            m.Field(alias="format", description="jscpd parser format name"),
        ]
        fragment: Annotated[
            t.NonEmptyStr, m.Field(description="Duplicated source fragment")
        ]
        is_new: Annotated[
            t.StrictBool,
            m.Field(
                alias="isNew",
                description=(
                    "Whether jscpd marked the clone new; the flag is absent from "
                    "some jscpd report versions and defaults to False"
                ),
            ),
        ] = False
        lines: Annotated[
            t.PositiveInt, m.Field(description="Duplicated logical line count")
        ]
        second_file: Annotated[
            FlextInfraModelsDuplication.JscpdFile,
            m.Field(alias="secondFile", description="Second clone source"),
        ]
        tokens: Annotated[t.PositiveInt, m.Field(description="Duplicated token count")]

    class JscpdStatisticsSummary(m.ContractModel):
        """Complete aggregate emitted for one format or the whole scan."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid", frozen=True, populate_by_name=True
        )

        clones: Annotated[t.NonNegativeInt, m.Field(description="Detected clone count")]
        duplicated_lines: Annotated[
            t.NonNegativeInt,
            m.Field(alias="duplicatedLines", description="Duplicated line count"),
        ]
        duplicated_tokens: Annotated[
            t.NonNegativeInt,
            m.Field(alias="duplicatedTokens", description="Duplicated token count"),
        ]
        lines: Annotated[
            t.NonNegativeInt, m.Field(description="Scanned logical line count")
        ]
        new_clones: Annotated[
            t.NonNegativeInt, m.Field(alias="newClones", description="New clone count")
        ]
        new_duplicated_lines: Annotated[
            t.NonNegativeInt,
            m.Field(
                alias="newDuplicatedLines", description="New duplicated line count"
            ),
        ]
        percentage: Annotated[
            t.Percentage, m.Field(description="Duplicated line percentage")
        ]
        percentage_tokens: Annotated[
            t.Percentage,
            m.Field(
                alias="percentageTokens", description="Duplicated token percentage"
            ),
        ]
        sources: Annotated[
            t.NonNegativeInt, m.Field(description="Scanned source file count")
        ]
        tokens: Annotated[t.NonNegativeInt, m.Field(description="Scanned token count")]

    class JscpdStatistics(m.ContractModel):
        """Per-format and total statistics proving non-empty collection."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid", frozen=True, populate_by_name=True
        )

        detection_date: Annotated[
            t.NonEmptyStr,
            m.Field(alias="detectionDate", description="jscpd detection timestamp"),
        ]
        formats: Annotated[
            t.MappingKV[str, FlextInfraModelsDuplication.JscpdStatisticsSummary],
            m.Field(description="Statistics keyed by parsed source format"),
        ]
        total: Annotated[
            FlextInfraModelsDuplication.JscpdStatisticsSummary,
            m.Field(description="Aggregate scan statistics"),
        ]

    class JscpdReport(m.ContractModel):
        """Validated complete jscpd JSON report."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        duplicates: Annotated[
            t.SequenceOf[FlextInfraModelsDuplication.JscpdDuplicate],
            m.Field(description="Complete detected clone records"),
        ]
        statistics: Annotated[
            FlextInfraModelsDuplication.JscpdStatistics,
            m.Field(description="Validated scan statistics"),
        ]

        @u.model_validator(mode="after")
        def _validate_complete_report(self) -> Self:
            format_summaries = tuple(self.statistics.formats.values())
            if not format_summaries or self.statistics.total.sources == 0:
                msg = "jscpd report collected zero source files"
                raise ValueError(msg)
            if (
                sum(item.sources for item in format_summaries)
                != self.statistics.total.sources
            ):
                msg = "jscpd per-format source count does not match total"
                raise ValueError(msg)
            if (
                sum(item.clones for item in format_summaries)
                != self.statistics.total.clones
            ):
                msg = "jscpd per-format clone count does not match total"
                raise ValueError(msg)
            if self.statistics.total.clones != len(self.duplicates):
                msg = "jscpd duplicate records do not match the reported clone total"
                raise ValueError(msg)
            for duplicate in self.duplicates:
                for source in (duplicate.first_file, duplicate.second_file):
                    if not Path(source.name).is_absolute():
                        msg = (
                            f"jscpd reported a non-absolute source path: {source.name}"
                        )
                        raise ValueError(msg)
            return self

    class JscpdScan(m.ContractModel):
        """Fresh command evidence plus its validated report."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        exit_code: Annotated[
            t.NonNegativeInt, m.Field(le=255, description="Raw jscpd process exit code")
        ]
        report: Annotated[
            FlextInfraModelsDuplication.JscpdReport,
            m.Field(description="Validated report from this exact scan"),
        ]
        stderr: Annotated[str, m.Field(description="Raw jscpd standard error")]
        stdout: Annotated[str, m.Field(description="Raw jscpd standard output")]


__all__: list[str] = ["FlextInfraModelsDuplication"]
