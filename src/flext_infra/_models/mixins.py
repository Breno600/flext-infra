"""Shared model mixins for flext-infra contracts and CLI payloads."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar

from flext_core import m
from flext_infra import c, t


class FlextInfraModelsMixins:
    """Centralized reusable field and helper mixins for models.

    Structure (flat — no sub-namespaces): CLI parameter mixins, field
    contract mixins, violation/detail mixins, release mixins, github
    mixins, and project-name variants. All exposed directly under
    ``mm.<Mixin>`` for consumers.
    """

    # ═══════════════════ CLI PARAMETER MIXINS ═══════════════════

    class ScopeMixin:
        """Canonical CLI scope contract — workspace + project selection.

        Consolidates the former ``BaseMixin`` and ``ProjectMixin``
        surfaces into a single flat mixin used by every read/write
        command.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(populate_by_name=True)

        repository_root: Annotated[
            Path,
            m.BeforeValidator(lambda value: Path(value).resolve()),
            m.Field(description="Repository root"),
        ] = Path()
        projects: Annotated[
            t.StrSequence | None,
            m.Field(
                description="Projects to process; repeat --projects NAME as needed"
            ),
        ] = None
        module: Annotated[
            str | None,
            m.Field(
                description=(
                    "Dotted module path to scope verb to a single module "
                    "(e.g. flext_core.result). Mutually compatible with "
                    "--projects/--repository-root; narrows the run."
                )
            ),
        ] = None
        namespace: Annotated[
            str | None,
            m.Field(
                description=(
                    "Alias namespace (c|m|p|t|u|r|e|h|s|x[.<Domain>]) to scope "
                    "the verb to a single facade slot."
                )
            ),
        ] = None
        fail_fast: Annotated[bool, m.Field(description="Stop on first failure")] = True
        verbose: Annotated[bool, m.Field(description="Verbose output")] = False

        @property
        def project_names(self) -> t.StrSequence | None:
            """Normalized project names from repeated selectors."""
            names = tuple(
                item.strip()
                for value in (self.projects or ())
                for group in (value or "").split(",")
                for item in group.split()
                if item.strip()
            )
            return names or None

    class ReadMixin(ScopeMixin):
        """Read-only commands — report file + output directory only.

        Previous ``check`` and ``json_output`` fields removed (YAGNI —
        single canonical report path and a directory for multi-file
        outputs).
        """

        report: Annotated[
            str | None, m.Field(description="Output report file path")
        ] = None
        output_dir: Annotated[
            str | None, m.Field(description="Output directory for reports")
        ] = None

        @property
        def report_path(self) -> Path | None:
            """Resolved report path when provided."""
            if self.report is None:
                return None
            return Path(self.report).resolve()

        @property
        def output_dir_path(self) -> Path | None:
            """Resolved output directory when provided."""
            if self.output_dir is None:
                return None
            # The validated field is a string; resolve it at the Path boundary.
            return Path(self.output_dir).resolve()

    class WriteMixin(ScopeMixin):
        """Canonical write contract — apply/dry-run + safety gates.

        Gates are stored as ``t.StrSequence`` — CSV strings are parsed
        by ``@field_validator`` so downstream consumers always see a
        normalized list.
        """

        apply: Annotated[
            bool,
            m.Field(
                description="Apply changes instead of running in dry-run mode",
                json_schema_extra={
                    "typer_param_decls": list(c.Infra.CLI_APPLY_OPTION_DECLS)
                },
            ),
        ] = False
        gates: t.StrSequence = m.Field(
            default=(),
            description=(
                "Gate names for post-transform validation; empty selects the SSOT"
                " snapshot gates (make.check_gates_ci)."
            ),
        )

        @m.field_validator("gates", mode="before")
        @classmethod
        def _parse_gates(cls, value: str | t.SequenceOf[str] | None) -> t.StrSequence:
            """Accept CSV string, sequence, or None; normalize to StrSequence."""
            if value is None:
                return ()
            if isinstance(value, str):
                return tuple(part.strip() for part in value.split(",") if part.strip())
            normalized: list[str] = []
            for part in value:
                if not part:
                    continue
                normalized.extend(
                    token.strip() for token in part.split(",") if token.strip()
                )
            return tuple(normalized)

        @m.computed_field
        @property
        def dry_run(self) -> bool:
            """Whether writes are disabled (inverse of apply)."""
            return not self.apply

    # ═══════════════════ RELEASE MIXINS ═══════════════════

    class VersionTagMixin:
        """Shared release identity fields."""

        version: Annotated[str, m.Field(description="Version string")] = ""
        tag: Annotated[str, m.Field(description="Git tag (e.g. v1.0.0)")] = ""

    # ═══════════════════ FIELD CONTRACT MIXINS ═══════════════════

    class FilePathMixin:
        """Shared required file path field."""

        file: Annotated[t.NonEmptyStr, m.Field(description="File path")]

    class AbsoluteFilePathTextMixin:
        """Shared absolute file-path text field."""

        file_path: Annotated[t.NonEmptyStr, m.Field(description="Absolute file path")]

    class PositiveLineMixin:
        """Shared positive line-number field."""

        line: Annotated[t.PositiveInt, m.Field(description="Line number")]

    class RequiredNonNegativeLineMixin:
        """Shared required non-negative line-number field."""

        line: Annotated[t.NonNegativeInt, m.Field(description="Line number")]

    class NonNegativeLineMixin:
        """Shared non-negative line-number field with default zero."""

        line: Annotated[t.NonNegativeInt, m.Field(description="Line number")] = 0

    class NestedClassPathMixin:
        """Shared optional nested class-path field."""

        class_path: Annotated[str, m.Field(description="Nested class path")] = ""

    class FileLineViolationMixin(FilePathMixin, PositiveLineMixin):
        """Shared file plus positive line fields for violations."""

    class CurrentImportMixin:
        """Shared current import statement field."""

        current_import: Annotated[str, m.Field(description="Current import statement")]

    # ═══════════════════ VIOLATION/DETAIL MIXINS ═══════════════════

    class ViolationDetailMixin:
        """Shared violation detail field."""

        detail: Annotated[str, m.Field(description="Violation detail")] = ""

    class ErrorDetailMixin:
        """Shared error detail field."""

        detail: Annotated[str, m.Field(description="Error detail")] = ""

    # ═══════════════════ PROJECT NAME / PATH VARIANTS ═══════════════════

    class ProjectNameMixin:
        """Shared required project-name field."""

        project: Annotated[t.NonEmptyStr, m.Field(description="Project name")]

    class ProjectEntryNameMixin:
        """Shared required project entry name field."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Project name")]

    class RepositoryRootPathMixin:
        """Shared repository root path field."""

        repository_root: Annotated[Path, m.Field(description="Repository root path")]

    class CheckpointRefMixin:
        """Shared safety checkpoint reference field."""

        checkpoint_ref: Annotated[
            str, m.Field(description="Safety checkpoint reference")
        ] = ""

    class ProjectNamesOptionalMixin:
        """Shared optional project-name collection."""

        project_names: Annotated[
            t.StrSequence | None, m.Field(description="Project names")
        ] = None

    class ProjectNamesListMixin:
        """Shared concrete project-name collection."""

        project_names: Annotated[t.StrSequence, m.Field(default_factory=tuple)] = (
            m.Field(default_factory=tuple)
        )


__all__: list[str] = ["FlextInfraModelsMixins"]
