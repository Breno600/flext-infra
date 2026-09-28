"""Data-only contracts for the canonical AST-grep circuit."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Literal

from flext_core import m
from flext_infra import t


class FlextInfraModelsCodemod:
    """Typed contracts for native codemod scans and mutation reports."""

    class AstGrepDiagnostic(m.FlexibleModel):
        """Required native RuleMatch fields, with zero-based source coordinates.

        ast-grep may include additional replacement and metavariable metadata;
        the complete payload remains in the gate's raw scanner output.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(strict=True)

        file: Annotated[str, m.Field(min_length=1, description="Reported source path")]
        rule_id: Annotated[
            str, m.Field(alias="ruleId", min_length=1, description="Native rule ID")
        ]
        severity: Annotated[
            Literal["error", "warning", "info", "hint"],
            m.Field(description="Native rule severity"),
        ]
        message: Annotated[str, m.Field(description="Native rule diagnostic")]
        text: Annotated[str, m.Field(description="Exact matched source text")]
        lines: Annotated[str, m.Field(description="Source lines containing the match")]
        line: Annotated[
            int,
            m.Field(
                ge=0,
                validation_alias=m.AliasPath("range", "start", "line"),
                description="Zero-based starting source line",
            ),
        ]
        column: Annotated[
            int,
            m.Field(
                ge=0,
                validation_alias=m.AliasPath("range", "start", "column"),
                description="Zero-based starting source column",
            ),
        ]
        end_line: Annotated[
            int,
            m.Field(
                ge=0,
                validation_alias=m.AliasPath("range", "end", "line"),
                description="Zero-based ending source line",
            ),
        ]
        end_column: Annotated[
            int,
            m.Field(
                ge=0,
                validation_alias=m.AliasPath("range", "end", "column"),
                description="Zero-based ending source column",
            ),
        ]
        start_byte: Annotated[
            int,
            m.Field(
                ge=0,
                validation_alias=m.AliasPath("range", "byteOffset", "start"),
                description="Inclusive UTF-8 byte offset",
            ),
        ]
        end_byte: Annotated[
            int,
            m.Field(
                ge=0,
                validation_alias=m.AliasPath("range", "byteOffset", "end"),
                description="Exclusive UTF-8 byte offset",
            ),
        ]

    class AstGrepReport(m.RootModel[tuple[AstGrepDiagnostic, ...]]):
        """Complete ``ast-grep scan --json=compact`` array; malformed input raises."""

    class FamilyFlattenRule(m.ContractModel):
        """One installed, closed family-shape operation (ADR-017)."""

        id: Annotated[t.NonEmptyStr, m.Field(description="Exact rule receipt identity")]
        operation: Annotated[
            Literal["flatten-single-wrapper"],
            m.Field(description="Supported semantic family transformation"),
        ]
        collision: Annotated[
            Literal["prefix-wrapper"],
            m.Field(description="Member-name collision resolution policy"),
        ]

    class ModFixtureDirectories(m.ArbitraryTypesModel):
        """Validated physical directories selected by one ast-grep owner."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        rule_dirs: t.VariadicTuple[Path] = m.Field(
            description="Validated rule directories declared by the ast-grep owner"
        )
        util_dirs: t.VariadicTuple[Path] = m.Field(
            description="Validated utility directories declared by the ast-grep owner"
        )
        test_dirs: t.VariadicTuple[Path] = m.Field(
            description="Validated fixture directories declared by the ast-grep owner"
        )

    class ModRuleBatch(m.ArbitraryTypesModel):
        """Validated executable ast-grep documents prepared for one circuit."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        inline_rules: Annotated[
            t.NonEmptyStr, m.Field(description="Executable YAML document stream")
        ]
        rule_count: Annotated[
            t.PositiveInt, m.Field(description="Discovered rule file count")
        ]
        all_ids: Annotated[
            frozenset[str], m.Field(description="Every validated rule ID")
        ]
        fixable_ids: Annotated[
            frozenset[str], m.Field(description="Rule IDs owning an automatic rewrite")
        ]

    class ModGateSnapshot(m.ArbitraryTypesModel):
        """Exact Ruff and Pyrefly measurement with raw diagnostics."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        ruff_errors: Annotated[
            t.NonNegativeInt, m.Field(description="Ruff error count")
        ]
        pyrefly_errors: Annotated[
            t.NonNegativeInt, m.Field(description="Pyrefly error count")
        ]
        ruff_output: Annotated[
            str, m.Field(description="Complete Ruff machine output")
        ] = ""
        pyrefly_output: Annotated[
            str, m.Field(description="Complete Pyrefly machine output")
        ] = ""


__all__: list[str] = ["FlextInfraModelsCodemod"]
