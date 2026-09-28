"""Data-only contracts for the canonical AST-grep circuit."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar

from flext_core import m
from flext_infra import t


class FlextInfraModelsCodemod:
    """Typed reports emitted by ``make mod``."""

    class ModFixtureDirectories(m.ArbitraryTypesModel):
        """Validated physical directories selected by one ast-grep owner."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        rule_dirs: tuple[Path, ...] = m.Field(
            description="Validated rule directories declared by the ast-grep owner"
        )
        util_dirs: tuple[Path, ...] = m.Field(
            description="Validated utility directories declared by the ast-grep owner"
        )
        test_dirs: tuple[Path, ...] = m.Field(
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
