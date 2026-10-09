"""Domain models for the refactor subpackage.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import MutableMapping, MutableSequence, MutableSet
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, ClassVar

from flext_cli import m

from flext_infra import t
from flext_infra._models.mixins import FlextInfraModelsMixins
from flext_infra._models.refactor_ast_grep import FlextInfraModelsRefactorGrep
from flext_infra._models.refactor_namespace_enforcer import (
    FlextInfraModelsNamespaceEnforcer,
)

if TYPE_CHECKING:
    from flext_infra._models.scan import FlextInfraModelsScan


class FlextInfraModelsRefactor(
    FlextInfraModelsRefactorGrep,
    FlextInfraModelsNamespaceEnforcer,
):
    """Models for refactor workflows and related tools.

    Canonical base policy:
    - ``ContractModel`` for configuration/policy contracts.
    - ``ArbitraryTypesModel`` for mutable report/result payloads.
    """

    class ModTextCommand(FlextInfraModelsMixins.WriteMixin, m.ContractModel):
        """Repository-scoped request for authenticated Sed rule replay."""

    class ViolationsTotals(m.ContractModel):
        """One mod scan's violation totals as the sweep compares them."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        findings: Annotated[
            int,
            m.Field(description="Total mod scan findings"),
        ]
        actionable: Annotated[
            int,
            m.Field(description="Findings a mod rewrite would repair"),
        ]
        detection_only: Annotated[
            int,
            m.Field(description="Findings no rewrite repairs"),
        ]
        non_actionable_with_fix: Annotated[
            int,
            m.Field(description="Findings whose rewrite matches the current source"),
        ]

        @classmethod
        def from_scan_report(
            cls,
            report: FlextInfraModelsScan.ModScanReport,
        ) -> FlextInfraModelsRefactor.ViolationsTotals:
            """Read one scan report's totals.

            Returns:
                The resulting ``FlextInfraModelsRefactor.ViolationsTotals``.

            """
            return cls(
                findings=report.findings,
                actionable=report.actionable,
                detection_only=report.detection_only,
                non_actionable_with_fix=report.non_actionable_with_fix,
            )

    class ViolationsSweepReport(m.ContractModel):
        """Before/after receipt of one violations sweep.

        Published only when the always-reducing law held: no scan total
        increased across the repair sequence.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        schema_version: Annotated[
            int,
            m.Field(description="Report schema version"),
        ]
        repository_root: Annotated[
            Path,
            m.Field(description="Repository the sweep repaired and proved"),
        ]
        repair_verbs: Annotated[
            t.StrSequence,
            m.Field(description="Canonical verbs the sweep ran, in order"),
        ]
        before: Annotated[
            FlextInfraModelsRefactor.ViolationsTotals,
            m.Field(description="Scan totals before the repair sequence"),
        ]
        after: Annotated[
            FlextInfraModelsRefactor.ViolationsTotals,
            m.Field(description="Scan totals after the repair sequence"),
        ]

        @property
        def increased_totals(self) -> t.StrSequence:
            """Names of the totals that increased, empty when none did.

            Returns:
                The resulting ``t.StrSequence``.

            """
            return tuple(
                name
                for name in (
                    "findings",
                    "actionable",
                    "detection_only",
                    "non_actionable_with_fix",
                )
                if getattr(self.after, name) > getattr(self.before, name)
            )

    class RefactorNamespaceEnforceInput(
        FlextInfraModelsMixins.WriteMixin,
        m.ContractModel,
    ):
        """CLI/service request for namespace enforcement."""

    class AccessorMigrationInput(FlextInfraModelsMixins.WriteMixin, m.ContractModel):
        """CLI/service request for accessor migration dry-runs and applies."""

        preview_limit: Annotated[
            t.PositiveInt,
            m.Field(
                alias="preview-limit",
                description="Maximum number of file previews to include in the report",
            ),
        ] = 10

    class Result(m.ArbitraryTypesModel):
        """Result of applying refactor rules to a single file."""

        file_path: Annotated[Path, m.Field(description="Target file path")]
        success: Annotated[bool, m.Field(description="Whether the operation succeeded")]
        modified: Annotated[
            bool,
            m.Field(description="Whether the file was actually modified"),
        ]
        error: Annotated[
            str | None,
            m.Field(description="Error message on failure"),
        ] = None
        changes: Annotated[
            t.StrSequence,
            m.Field(description="Human-readable change descriptions"),
        ] = m.Field(default_factory=tuple)
        refactored_code: Annotated[
            str | None,
            m.Field(description="Resulting source code after transformation"),
        ] = None

    class RefactorProjectInfo(m.ArbitraryTypesModel):
        """Project metadata with mutable package-root set.

        Enforcement exemption: ``package_roots`` is a ``set[str]``
        accumulator populated during scanning.
        """

        name: Annotated[t.NonEmptyStr, m.Field(description="Project directory name")]
        path: Annotated[Path, m.Field(description="Absolute project path")]
        src_path: Annotated[Path, m.Field(description="Absolute src/ path")]
        package_roots: Annotated[
            MutableSet[str],
            m.Field(description="Top-level Python package roots in src/"),
        ] = m.Field(default_factory=set[str])

    class FileImportData(m.ArbitraryTypesModel):
        """File-level import data with mutable set accumulators.

        Enforcement exemption: ``imported_modules``/``imported_symbols``
        accumulate during a scan; keep ``set[str]`` as the declared type.
        """

        imported_modules: Annotated[
            MutableSet[str],
            m.Field(description="Imported module roots"),
        ] = m.Field(default_factory=set[str])
        imported_symbols: Annotated[
            MutableSet[str],
            m.Field(description="Imported symbol names"),
        ] = m.Field(default_factory=set[str])

    class MethodInfo(m.ArbitraryTypesModel):
        """Metadata about a method used for ordering inside classes."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Method name")]
        category: Annotated[str, m.Field(description="Method category classification")]
        node: Annotated[
            t.Infra.RopePyObject | None,
            m.Field(
                description="Node representation from Rope or PyObject",
                exclude=True,
            ),
        ]
        decorators: Annotated[
            t.StrSequence,
            m.Field(description="Decorator names applied to this method"),
        ] = m.Field(default_factory=tuple)

    class ProjectClassification(m.ArbitraryTypesModel):
        """Result of classifying a project by kind and family chains."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        project_kind: Annotated[
            t.NonEmptyStr,
            m.Field(
                description="Project kind (core, domain, platform, integration, app)",
            ),
        ]
        family_chains: Annotated[
            t.MappingKV[str, t.StrSequence],
            m.Field(description="Family letter to FLEXT chain mapping"),
        ]

    # NOTE (multi-agent): the model below replaces the dataclass payload that
    # lived in refactor/_wrapper_rewrite.py (deep-FLEXT: models only in m).
    class WrapperRewriteAccumulator(m.ArbitraryTypesModel):
        """Aggregates per-file rewrite stats across the wrapper-root verb run.

        Mutable accumulator (never frozen): every field is appended to or
        incremented while the run scans candidate files.
        """

        updates: Annotated[
            MutableMapping[Path, str],
            m.Field(description="Pending file content updates keyed by path"),
        ] = m.Field(default_factory=dict[Path, str])
        expected_sources: Annotated[
            MutableMapping[Path, str],
            m.Field(description="Original content keyed by every pending update path"),
        ] = m.Field(default_factory=dict[Path, str])
        changed_files: Annotated[
            MutableSequence[str],
            m.Field(description="String paths of files changed by the run"),
        ] = m.Field(default_factory=list[str])
        total_replacements: Annotated[
            int,
            m.Field(description="Total replacements applied across the run"),
        ] = 0
        total_core_replacements: Annotated[
            int,
            m.Field(description="Total Core.Tests chain rewrites applied"),
        ] = 0
        import_rewrite_candidates: Annotated[
            int,
            m.Field(description="Count of wrapper import rewrite candidates"),
        ] = 0
        per_project_changes: Annotated[
            defaultdict[str, int],
            m.Field(description="Changed file count keyed by project name"),
        ] = m.Field(default_factory=lambda: defaultdict[str, int](int))
        per_project_replacements: Annotated[
            defaultdict[str, int],
            m.Field(description="Replacement count keyed by project name"),
        ] = m.Field(default_factory=lambda: defaultdict[str, int](int))

    # -- CSV-driven Rename Models ---------------------------------------------

    class ModCommand(FlextInfraModelsMixins.WriteMixin, m.ContractModel):
        """CLI request for the shared AST, semantic, and text codemod cascade."""

        check: Annotated[bool, m.Field(description="Validate without writing")] = False
        dry_run_mode: Annotated[
            bool,
            m.Field(alias="dry-run", description="Inspect without writing"),
        ] = False

    class ApplyRenamesInput(FlextInfraModelsMixins.WriteMixin, m.ContractModel):
        """Validated CLI request for CSV-driven symbol renames."""

        csv: Annotated[
            t.NonEmptyStr,
            m.Field(description="Path to the old,new rename-list CSV"),
        ]
        roots: Annotated[
            t.StrSequence,
            m.Field(min_length=1, description="Directories to scan for rename targets"),
        ]
        bindings: Annotated[
            t.MappingKV[str, t.StrSequence],
            m.Field(
                description=(
                    "CSV expression prefixes mapped to current"
                    " public Rope owner identities"
                ),
            ),
        ] = m.Field(default_factory=lambda: MappingProxyType[str, t.StrSequence]({}))
        text_globs: Annotated[
            t.StrSequence,
            m.Field(
                description=(
                    "Explicit root-relative non-Python documentation"
                    " and configuration text surfaces"
                ),
            ),
        ] = ()
        python_documentation: Annotated[
            bool,
            m.Field(
                description=(
                    "Rename comments and actual Python docstrings,"
                    " preserving executable string payloads"
                ),
            ),
        ] = False
        exclude_globs: Annotated[
            t.StrSequence,
            m.Field(
                description=(
                    "Declared generated projections excluded from campaign targets"
                ),
            ),
        ] = ()

    class ApplyRenamesReport(m.ArbitraryTypesModel):
        """Summary of one CSV-driven rename pass."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        label: Annotated[t.NonEmptyStr, m.Field(description="Rename-list label")]
        files_scanned: Annotated[
            t.NonNegativeInt,
            m.Field(description="Text files scanned"),
        ]
        occurrences: Annotated[
            t.NonNegativeInt,
            m.Field(
                description=(
                    "Pending authenticated source edit spans from the current scan"
                ),
            ),
        ] = 0
        files_changed: Annotated[
            t.NonNegativeInt,
            m.Field(description="Files rewritten in apply mode"),
        ] = 0
        applied: Annotated[bool, m.Field(description="Whether changes were applied")]

    # -- Namespace Enforcer Models ---------------------------------------------

    class ParsedPythonModule(m.ArbitraryTypesModel):
        """Result of parsing a Python source file into AST."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        source: Annotated[str, m.Field(description="Raw source text")]
        tree: Annotated[
            t.Infra.RopePyModule,
            m.Field(description="Parsed PyObject module representation"),
        ]

    class ImportLawScope(m.ArbitraryTypesModel):
        """Immutable facts one import-law pass decides a module's imports on."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        project_root: Annotated[Path, m.Field(description="Governed project root")]
        file_path: Annotated[Path, m.Field(description="Normalized module path")]
        namespace_dir: Annotated[
            Path,
            m.Field(description="Directory of the namespace owning the module"),
        ]
        module: Annotated[str, m.Field(description="Dotted name of the module")]
        layer: Annotated[int, m.Field(description="Module's import-layer rank")]
        own_exports: Annotated[
            frozenset[str],
            m.Field(description="Names the module declares in its own __all__"),
        ]
        family_letter: Annotated[
            str | None,
            m.Field(
                description=(
                    "Facade letter of the family package holding the module, "
                    "or None outside every family package"
                ),
            ),
        ] = None
        direct_imports: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether the module keeps direct leaf imports: a "
                    "settings/config module or a family base.py, which must "
                    "never route through the namespace root or a lazy package"
                ),
            ),
        ] = False

        @m.computed_field
        @property
        def namespace(self) -> str:
            """Top-level package name of the owning namespace.

            Returns:
                The namespace package name.

            """
            return self.namespace_dir.name

    class ImportLawPass(m.ArbitraryTypesModel):
        """One parsed module and the facts one import-law pass reads from it."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        scope: Annotated[
            FlextInfraModelsRefactor.ImportLawScope,
            m.Field(description="Module facts of the pass"),
        ]
        tree: Annotated[ast.Module, m.Field(description="Parsed module")]
        parents: Annotated[
            t.MappingKV[int, ast.AST],
            m.Field(description="Child node id to parent node map"),
        ]
        bindings: Annotated[
            t.MappingKV[str, ast.stmt],
            m.Field(description="Module-level statement binding each top name"),
        ]
        root_exports: Annotated[
            t.StrMapping,
            m.Field(description="Names the namespace root publishes lazily"),
        ]


__all__: list[str] = ["FlextInfraModelsRefactor"]
