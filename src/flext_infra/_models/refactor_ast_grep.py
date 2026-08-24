"""Refactor migration model mixins for rope-oriented orchestration."""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Annotated, ClassVar

from flext_cli import m
from flext_infra import c, t
from flext_infra._models.mixins import FlextInfraModelsMixins as mm
from flext_infra._models.mro_scan import FlextInfraModelsMroScan


class FlextInfraModelsRefactorGrep(FlextInfraModelsMroScan):
    """Mixin containing migration/reporting contracts for refactor orchestration."""

    class RewriteFilesInput(m.Value):
        """Typed input envelope for workspace rewrite execution."""

        workspace_root: Annotated[Path, m.Field(description="Workspace root path")]
        file_moves: Annotated[
            t.MappingKV[Path, t.MappingKV[str, t.Pair[str, t.StrMapping]]],
            m.Field(description="Per-file symbol move map for rewrite"),
        ]
        pending_sources: Annotated[
            t.MappingKV[Path, str],
            m.Field(description="In-memory pending sources keyed by file path"),
        ]
        apply: Annotated[
            bool, m.Field(description="Whether to write rewritten sources")
        ]
        gates: Annotated[
            t.StrSequence | None,
            m.Field(description="Optional protected-write gate selectors"),
        ] = None

    class MROImportRewrite(m.ArbitraryTypesModel):
        """Unified import rewrite payload for MRO reference updates."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        facade_name: Annotated[str, m.Field(description="Facade alias/import name")] = (
            ""
        )
        module: Annotated[t.NonEmptyStr, m.Field(description="Import module path")]
        import_name: Annotated[str, m.Field(description="Imported symbol name")]
        as_name: Annotated[str | None, m.Field(description="Optional alias")] = None
        symbol: Annotated[str, m.Field(description="Resolved symbol in facade")] = ""

    class MROFileMigration(m.ArbitraryTypesModel):
        """Migration summary for one transformed file."""

        file: Annotated[t.NonEmptyStr, m.Field(description="Absolute file path")]
        module: Annotated[t.NonEmptyStr, m.Field(description="Import module path")]
        moved_symbols: t.VariadicTuple[str] = m.Field(
            default_factory=tuple, description="Symbols moved to facade class"
        )
        created_classes: t.VariadicTuple[str] = m.Field(
            default_factory=tuple, description="Facade classes created during migration"
        )

    class MRORewriteResult(m.ArbitraryTypesModel):
        """Reference rewrite summary for one file."""

        file: Annotated[t.NonEmptyStr, m.Field(description="Absolute file path")]
        replacements: Annotated[
            int, m.Field(description="Reference replacements applied")
        ]

    class MROMigrationReport(mm.CheckpointRefMixin, m.ArbitraryTypesModel):
        """End-to-end report for migrate-to-mro command execution."""

        workspace: Annotated[str, m.Field(description="Workspace root path")]
        target: Annotated[t.NonEmptyStr, m.Field(description="constants|typings|all")]
        selected_projects: t.VariadicTuple[str] = m.Field(
            default_factory=tuple,
            description="Project scope used for the run; empty means whole workspace",
        )
        dry_run: Annotated[bool, m.Field(description="Dry-run indicator")]
        validation_mode: Annotated[
            str,
            m.Field(
                description="Validation strategy used for remaining violation counts"
            ),
        ] = "post-apply-rescan"
        files_scanned: Annotated[int, m.Field(description="Total scanned Python files")]
        files_with_candidates: Annotated[
            int, m.Field(ge=0, description="Files containing movable declarations")
        ]
        migrations: t.VariadicTuple[FlextInfraModelsRefactorGrep.MROFileMigration] = (
            m.Field(default_factory=tuple, description="File migration summaries")
        )
        rewrites: t.VariadicTuple[FlextInfraModelsRefactorGrep.MRORewriteResult] = (
            m.Field(default_factory=tuple, description="Reference rewrite summaries")
        )
        remaining_violations: Annotated[
            int, m.Field(ge=0, description="Loose declarations remaining after run")
        ]
        mro_failures: Annotated[
            t.NonNegativeInt, m.Field(description="MRO validation failures")
        ]
        scan_duration_seconds: Annotated[
            float, m.Field(ge=0.0, description="Scan phase duration in seconds")
        ] = 0.0
        rewrite_duration_seconds: Annotated[
            float, m.Field(ge=0.0, description="Rewrite phase duration in seconds")
        ] = 0.0
        validation_duration_seconds: Annotated[
            float, m.Field(ge=0.0, description="Validation phase duration in seconds")
        ] = 0.0
        total_duration_seconds: Annotated[
            float, m.Field(ge=0.0, description="Total run duration in seconds")
        ] = 0.0
        warnings: t.VariadicTuple[str] = m.Field(
            default_factory=tuple, description="Warnings"
        )
        errors: t.VariadicTuple[str] = m.Field(
            default_factory=tuple, description="Errors"
        )

    class RefactorConfig(m.ContractModel):
        """Refactor file-selection config."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        project_scan_dirs: t.StrSequence = m.Field(
            default_factory=lambda: [
                c.Infra.DEFAULT_SRC_DIR,
                c.Infra.DIR_TESTS,
                c.Infra.DIR_SCRIPTS,
                c.Infra.DIR_EXAMPLES,
            ],
            description="Relative directories scanned for candidate files",
        )
        ignore_patterns: t.StrSequence = m.Field(
            default_factory=tuple, description="Glob/file patterns ignored during scan"
        )
        file_extensions: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Allowed file extensions (empty = all by pattern)",
        )

    class MethodOrderRule(m.ContractModel):
        """A declarative method ordering rule for class reconstruction.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict()

        category: Annotated[str | None, m.Field(description="Method category")] = None
        visibility: Annotated[str | None, m.Field(description="Visibility filter")] = (
            None
        )
        exclude_decorators: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Decorators excluded from the ordering rule",
        )
        decorators: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Decorators required by the ordering rule",
        )
        patterns: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Method name patterns included by the ordering rule",
        )
        order: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Expected method-category order for matching methods",
        )

    class SignatureMigration(m.ContractModel):
        """Declarative signature migration rule for callsite propagation.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        id: Annotated[str, m.Field(description="Migration ID")] = "signature-migration"
        enabled: Annotated[bool, m.Field(description="Whether migration is active")] = (
            True
        )
        target_qualified_names: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Qualified symbol names targeted by the migration",
        )
        target_simple_names: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Simple symbol names targeted by the migration",
        )
        keyword_renames: t.StrMapping = m.Field(
            default_factory=lambda: MappingProxyType({}),
            description="Keyword rename mapping",
        )
        remove_keywords: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Keywords removed from matching callsites",
        )
        add_keywords: t.StrMapping = m.Field(
            default_factory=lambda: MappingProxyType({}), description="Keywords to add"
        )

    class ImportModernizerRuleConfig(m.ContractModel):
        """Configuration for a single import modernizer rule.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        module: Annotated[str, m.Field(description="Module path to modernize")] = ""
        symbol_mapping: t.StrMapping = m.Field(
            default_factory=lambda: MappingProxyType({}),
            description="Symbol-to-alias mapping",
        )

    class AccessorMigrationRule(m.ContractModel):
        """Declarative symbol-rename rule for accessor migration."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        source_name: Annotated[
            t.NonEmptyStr, m.Field(description="Canonical symbol name to replace")
        ]
        replacement_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical symbol name used as replacement"),
        ]
        reason: Annotated[
            t.NonEmptyStr,
            m.Field(description="Human-readable explanation for the rename"),
        ]
        origin: Annotated[
            str, m.Field(description="Canonical API origin this rewrite is tied to")
        ] = ""

    class AccessorMigrationChange(m.ArbitraryTypesModel):
        """Single automated rename or manual warning emitted by accessor migration."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        file: Annotated[t.NonEmptyStr, m.Field(description="Absolute file path")]
        line: Annotated[
            t.NonNegativeInt,
            m.Field(description="1-based source line number when available"),
        ]
        original_name: Annotated[
            t.NonEmptyStr, m.Field(description="Original accessor or helper name")
        ]
        replacement_name: Annotated[
            str, m.Field(description="Suggested or applied replacement name")
        ] = ""
        automated: Annotated[
            bool,
            m.Field(description="Whether the migration was performed automatically"),
        ]
        reason: Annotated[
            str, m.Field(description="Human-readable migration rationale")
        ]

    class AccessorMigrationFile(m.ArbitraryTypesModel):
        """Per-file preview for accessor migration dry-runs and applies.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        file: Annotated[t.NonEmptyStr, m.Field(description="Absolute file path")]
        lint_tools: t.VariadicTuple[str] = m.Field(
            default_factory=tuple,
            description="Selected lint tools used for preview rendering",
        )
        automated_changes: t.VariadicTuple[
            FlextInfraModelsRefactorGrep.AccessorMigrationChange
        ] = m.Field(
            default_factory=tuple,
            description="Automated rewrites captured for this file",
        )
        warnings: t.VariadicTuple[
            FlextInfraModelsRefactorGrep.AccessorMigrationChange
        ] = m.Field(
            default_factory=tuple, description="Manual follow-up warnings for this file"
        )
        diff: Annotated[
            str, m.Field(description="Unified diff preview for the file")
        ] = ""
        lint_before: Annotated[
            t.MappingKV[str, t.StrSequence],
            m.Field(description="Lint output before the proposed rewrite"),
        ] = m.Field(default_factory=lambda: MappingProxyType({}))
        lint_after: Annotated[
            t.MappingKV[str, t.StrSequence],
            m.Field(description="Lint output after the proposed rewrite"),
        ] = m.Field(default_factory=lambda: MappingProxyType({}))
        new_lint_errors: Annotated[
            t.MappingKV[str, t.StrSequence],
            m.Field(description="Lint errors introduced by the proposed rewrite"),
        ] = m.Field(default_factory=lambda: MappingProxyType({}))

    class AccessorMigrationReport(m.ArbitraryTypesModel):
        """Workspace-scale report for accessor migration orchestration.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        workspace: Annotated[t.NonEmptyStr, m.Field(description="Workspace root path")]
        dry_run: Annotated[bool, m.Field(description="Dry-run indicator")]
        files_scanned: Annotated[
            t.NonNegativeInt, m.Field(description="Total Python files scanned")
        ]
        files_with_changes: Annotated[
            t.NonNegativeInt, m.Field(description="Files with automated rewrites")
        ]
        automated_change_count: Annotated[
            t.NonNegativeInt, m.Field(description="Total automated rewrites detected")
        ]
        warning_count: Annotated[
            t.NonNegativeInt,
            m.Field(description="Total manual follow-up warnings detected"),
        ]
        lint_tools: t.VariadicTuple[str] = m.Field(
            default_factory=tuple,
            description="Canonical lint tool list used by this run",
        )
        lint_before_totals: Annotated[
            t.IntMapping,
            m.Field(description="Per-tool count of lint lines before rewrites"),
        ] = m.Field(default_factory=lambda: MappingProxyType({}))
        lint_after_totals: Annotated[
            t.IntMapping,
            m.Field(description="Per-tool count of lint lines after rewrites"),
        ] = m.Field(default_factory=lambda: MappingProxyType({}))
        new_lint_error_totals: Annotated[
            t.IntMapping,
            m.Field(description="Per-tool count of newly introduced lint lines"),
        ] = m.Field(default_factory=lambda: MappingProxyType({}))
        files: t.VariadicTuple[FlextInfraModelsRefactorGrep.AccessorMigrationFile] = (
            m.Field(
                default_factory=tuple,
                description="Preview entries included in this report",
            )
        )


__all__: list[str] = ["FlextInfraModelsRefactorGrep"]
