"""Auto-fix, consolidation, and namespace policy models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableSet, Sequence
from typing import Annotated, ClassVar, Literal

from flext_cli import m

from flext_infra import t
from flext_infra._models import FlextInfraModelsMixins as mm
from flext_infra._models._codegen.scaffold import FlextInfraModelsCodegenScaffoldModels


class FlextInfraModelsCodegenFixModels:
    """Auto-fix, consolidation, and namespace policy models."""

    class AutoFixResult(mm.ProjectNameMixin, m.ArbitraryTypesModel):
        """Result of auto-fixing namespace violations for a project."""

        violations_fixed: Annotated[
            t.MutableSequenceOf[FlextInfraModelsCodegenScaffoldModels.CensusViolation],
            m.Field(default_factory=list, description="Fixed violations"),
        ]
        violations_skipped: Annotated[
            t.MutableSequenceOf[FlextInfraModelsCodegenScaffoldModels.CensusViolation],
            m.Field(
                default_factory=list,
                description="Skipped violations (not auto-fixable)",
            ),
        ]
        files_modified: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Modified file paths",
        )

    class ConsolidatorFileResult(m.ContractModel):
        """Per-file result emitted by the constants consolidator."""

        file: Annotated[
            t.NonEmptyStr,
            m.Field(description="Workspace-relative file path"),
        ]
        status: Annotated[
            Literal["applied", "reverted"],
            m.Field(description="File processing status"),
        ]
        changes: Annotated[
            t.StrSequence,
            m.Field(default_factory=tuple, description="Applied replacements"),
        ]

    class ConsolidatorReport(m.ContractModel):
        """JSON report emitted by the constants consolidator."""

        total_found: Annotated[
            t.NonNegativeInt,
            m.Field(description="Total replacements found"),
        ] = 0
        total_applied: Annotated[
            t.NonNegativeInt,
            m.Field(description="Total replacements applied"),
        ] = 0
        total_failed: Annotated[
            t.NonNegativeInt,
            m.Field(description="Total files reverted"),
        ] = 0
        files: Annotated[
            t.SequenceOf[FlextInfraModelsCodegenFixModels.ConsolidatorFileResult],
            m.Field(default_factory=tuple, description="Per-file processing results"),
        ]

    class FacadeFamily(m.ContractModel):
        """One facade family the core package declares (c, t, p, m, u)."""

        letter: Annotated[
            t.NonEmptyStr,
            m.Field(description="Facade letter of the import-layer order"),
        ]
        module: Annotated[
            t.NonEmptyStr,
            m.Field(description="Stem of the facade module declaring the letter"),
        ]
        suffix: Annotated[
            t.NonEmptyStr,
            m.Field(description="Facade class suffix past the shared class stem"),
        ]

        @m.computed_field
        @property
        def directory(self) -> str:
            """Private family package beside the facade module."""
            return f"_{self.module}"

        @m.computed_field
        @property
        def directories(self) -> frozenset[str]:
            """Public and private family package directory names."""
            return frozenset({self.module, f"_{self.module}"})

        @m.computed_field
        @property
        def file_names(self) -> frozenset[str]:
            """Public and private facade module file names."""
            return frozenset({f"{self.module}.py", f"_{self.module}.py"})

    class NamespaceModulePolicy(m.ArbitraryTypesModel):
        """Derived gen-init policy for one governed module."""

        enforce_contract: Annotated[
            bool,
            m.Field(description="Whether gen-init must enforce namespace shape."),
        ] = False
        export_symbols: Annotated[
            bool,
            m.Field(description="Whether gen-init should discover public symbols."),
        ] = False
        include_in_lazy_init: Annotated[
            bool,
            m.Field(description="Whether lazy-init should index this module at all."),
        ] = True
        project_prefix: Annotated[
            str,
            m.Field(description="Canonical class prefix expected for the module."),
        ] = ""
        expected_alias: Annotated[
            str | None,
            m.Field(description="Canonical module-level alias allowed for the file."),
        ] = None
        expected_family: Annotated[
            str | None,
            m.Field(description="Canonical namespace family suffix for the file."),
        ] = None
        inherited_namespaces: t.StrSequence = m.Field(
            default_factory=tuple,
            description=(
                "Nested class attributes inherited unchanged "
                "through the actual facade MRO."
            ),
        )
        is_internal_namespace: bool = m.Field(
            default=False,
            description=(
                "Whether the facade belongs to a discovered non-public root tier."
            ),
        )
        family_tokens: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Accepted family markers for private namespace modules.",
        )
        accepted_suffixes: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Accepted class suffixes for governed facade classes.",
        )
        allow_main_export: Annotated[
            bool,
            m.Field(description="Whether the file may export a module-level main()."),
        ] = False
        allow_type_alias: Annotated[
            bool,
            m.Field(description="Whether the module may keep TypeAlias declarations."),
        ] = False
        is_fixture_module: Annotated[
            bool,
            m.Field(
                description="Whether the module belongs to a private fixtures package.",
            ),
        ] = False
        type_checking_imports: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Canonical root names allowed inside TYPE_CHECKING imports.",
        )

    class BulkFixItem(
        mm.AbsoluteFilePathTextMixin,
        mm.PositiveLineMixin,
        m.ArbitraryTypesModel,
    ):
        """Shared line-addressable item used by bulk codegen fixes."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Item identifier")]

    class ConstantDefinition(mm.ProjectNameMixin, mm.NestedClassPathMixin, BulkFixItem):
        """A single constant extracted from a constants.py file."""

        value_repr: Annotated[
            str,
            m.Field(description="Source repr (e.g., '30', '\"localhost\"')"),
        ]
        type_annotation: Annotated[
            str,
            m.Field(description="Type annotation string"),
        ] = ""

    class DuplicateConstantGroup(m.ArbitraryTypesModel):
        """Cross-project duplicate group with consolidation metadata."""

        constant_name: t.NonEmptyStr = m.Field(description="Constant identifier")
        definitions: Sequence[FlextInfraModelsCodegenFixModels.ConstantDefinition] = (
            m.Field(description="Definitions across projects")
        )
        is_value_identical: bool = m.Field(description="Whether all values match")
        canonical_ref: Annotated[
            str,
            m.Field(description="Canonical parent reference"),
        ] = ""

    class DirectConstantRef(mm.ProjectNameMixin, m.ArbitraryTypesModel):
        """Direct FlextXConstants.Y.Z reference that should use c.* alias."""

        full_ref: Annotated[
            t.NonEmptyStr,
            m.Field(description="e.g., FlextAuthConstants.Auth.DEFAULT_TIMEOUT"),
        ]
        alias_ref: Annotated[
            t.NonEmptyStr,
            m.Field(description="e.g., c.Auth.DEFAULT_TIMEOUT"),
        ]
        file_path: Annotated[
            t.NonEmptyStr,
            m.Field(description="File containing the reference"),
        ]
        line: Annotated[t.PositiveInt, m.Field(description="Line number")]

    class FixContext(m.ArbitraryTypesModel):
        """Mutable accumulation context for fix operations.

        Enforcement exemption: MutableSequence/MutableSet accumulators are
        appended/added to as fixes proceed; fresh per-instance — no shared
        state.
        """

        violations_fixed: Annotated[
            t.MutableSequenceOf[FlextInfraModelsCodegenScaffoldModels.CensusViolation],
            m.Field(
                default_factory=list,
                description="List of violations that were fixed",
            ),
        ] = m.Field(
            default_factory=list,
            description="List of violations that were fixed",
        )
        violations_skipped: Annotated[
            t.MutableSequenceOf[FlextInfraModelsCodegenScaffoldModels.CensusViolation],
            m.Field(
                default_factory=list,
                description="List of violations that were skipped",
            ),
        ] = m.Field(
            default_factory=list,
            description="List of violations that were skipped",
        )
        files_modified: Annotated[
            MutableSet[str],
            m.Field(
                default_factory=set,
                description="Set of unique modified file paths",
            ),
        ] = m.Field(
            default_factory=set,
            description="Set of unique modified file paths",
        )

        @property
        def has_changes(self) -> bool:
            """Whether at least one file was modified."""
            return bool(self.files_modified)

        def skip(self, *, module: str, rule: str, line: int, message: str) -> None:
            """Skip."""
            self.violations_skipped.append(
                FlextInfraModelsCodegenScaffoldModels.CensusViolation(
                    module=module,
                    rule=rule,
                    line=line,
                    message=message,
                    fixable=False,
                ),
            )

        def fix(self, *, module: str, rule: str, line: int, message: str) -> None:
            """Fix."""
            self.violations_fixed.append(
                FlextInfraModelsCodegenScaffoldModels.CensusViolation(
                    module=module,
                    rule=rule,
                    line=line,
                    message=message,
                    fixable=True,
                ),
            )

    class ViolationKey(m.ContractModel):
        """Content-stable violation identifier — resilient to line shifts."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        module: Annotated[str, m.Field(description="Module containing the violation")]
        rule: Annotated[str, m.Field(description="Rule that was violated")]
        content_hash: Annotated[
            str,
            m.Field(description="SHA256 of surrounding context lines"),
        ]

        def __hash__(self) -> int:
            """Hash by stable business identity so keys work in sets and frozensets.

            Returns:
                The resulting ``int``.

            """
            return hash((self.module, self.rule, self.content_hash))
