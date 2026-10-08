"""Accessor migration orchestration for get_/set_/is_ modernization.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Annotated, override

from flext_cli import cli

from flext_infra import c, m, p, r, t, u
from flext_infra.base_selection import FlextInfraProjectSelectionServiceBase
from flext_infra.refactor._accessor_report import FlextInfraAccessorMigrationReportMixin
from flext_infra.refactor._accessor_rewrite import (
    FlextInfraAccessorMigrationRewriteMixin,
)
from flext_infra.refactor._import_enforcement import FlextInfraImportNormalization

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraAccessorMigrationOrchestrator(
    FlextInfraProjectSelectionServiceBase[m.Infra.AccessorMigrationReport],
    FlextInfraAccessorMigrationRewriteMixin,
    FlextInfraAccessorMigrationReportMixin,
):
    """Dry-run/apply orchestrator for public accessor migration candidates."""

    preview_limit: Annotated[
        int,
        m.Field(description="Maximum number of file previews to include in the report"),
    ] = 10
    gates: Annotated[
        str,
        m.Field(
            description=(
                "Comma-separated lint gates for preview/apply validation; empty"
                " selects the SSOT snapshot gates (make.check_gates_ci)."
            ),
        ),
    ] = ""

    @property
    @override
    def gate_names(self) -> t.StrSequence:
        """Normalized lint gate names."""
        return u.Infra.normalize_cli_values(self.gates)

    @property
    @override
    def lint_tool_names(self) -> t.StrSequence:
        """Selected lint tool names resolved from gate names."""
        return u.Infra.selected_lint_tool_names(self.gate_names)

    def _scope_selected(
        self,
        py_files: t.SequenceOf[Path],
    ) -> t.SequenceOf[Path]:
        """Apply the declared ``--module``/``--namespace`` file filters.

        ``namespace`` keeps files under a package directory of that name;
        ``module`` keeps files whose path contains the dotted module rendered
        as path segments. Empty filters keep every file.

        Returns:
            The resulting ``t.SequenceOf[Path]``.

        """
        namespace = (self.target_namespace or "").strip()
        module = (self.target_module or "").strip()
        if not namespace and not module:
            return py_files
        module_segments = module.replace(".", "/")
        return tuple(
            path
            for path in py_files
            if (not namespace or f"/{namespace}/" in path.as_posix())
            and (not module or module_segments in path.as_posix())
        )

    @override
    def execute(self) -> p.Result[m.Infra.AccessorMigrationReport]:
        """Execute.

        Returns:
            The resulting ``p.Result[m.Infra.AccessorMigrationReport]``.

        """
        selected_projects: t.StrSequence = (
            self.project_names if self.project_names is not None else ()
        )
        resolved = u.Infra.resolve_projects(self.repository_root, selected_projects)
        if resolved.failure:
            return r[m.Infra.AccessorMigrationReport].from_failure(resolved)
        iter_result = u.Infra.iter_python_files(
            m.Infra.SourceScanRequest(
                project_roots=tuple(project.path for project in resolved.value),
            ),
        )
        if iter_result.failure:
            return r[m.Infra.AccessorMigrationReport].from_failure(iter_result)
        scoped_files = self._scope_selected(iter_result.value)
        if not self.effective_dry_run:
            # The same canonical import-form pass fix-namespace and the mod
            # loop own: a migrated accessor lands in a file whose imports
            # already hold the canonical forms.
            FlextInfraImportNormalization.apply_files(
                self.repository_root,
                scoped_files,
            )
        previews: t.MutableSequenceOf[m.Infra.AccessorMigrationFile] = []
        files_with_changes = 0
        automated_change_count = 0
        warning_count = 0
        lint_before_totals: MutableMapping[str, int] = {}
        lint_after_totals: MutableMapping[str, int] = {}
        new_lint_error_totals: MutableMapping[str, int] = {}
        with u.Infra.open_project(self.repository_root) as rope_project:
            for py_file in scoped_files:
                read = u.Cli.files_read_text(py_file)
                if read.failure:
                    return r[m.Infra.AccessorMigrationReport].from_failure(read)
                file_report = self._process_file(
                    rope_project,
                    py_file,
                    read.value,
                    preview_available=len(previews) < self.preview_limit,
                )
                automated_change_count += len(file_report.automated_changes)
                warning_count += len(file_report.warnings)
                if file_report.automated_changes:
                    files_with_changes += 1
                if (file_report.automated_changes or file_report.warnings) and len(
                    previews,
                ) < self.preview_limit:
                    previews.append(file_report)
                self._accumulate_lint_totals(
                    lint_before_totals,
                    file_report.lint_before,
                )
                self._accumulate_lint_totals(lint_after_totals, file_report.lint_after)
                self._accumulate_lint_totals(
                    new_lint_error_totals,
                    file_report.new_lint_errors,
                )
        report = m.Infra.AccessorMigrationReport(
            workspace=str(self.repository_root),
            dry_run=self.effective_dry_run,
            files_scanned=len(scoped_files),
            files_with_changes=files_with_changes,
            automated_change_count=automated_change_count,
            warning_count=warning_count,
            lint_tools=tuple(self.lint_tool_names),
            lint_before_totals=lint_before_totals,
            lint_after_totals=lint_after_totals,
            new_lint_error_totals=new_lint_error_totals,
            files=tuple(previews),
        )
        published = u.Infra.publish_refactor_report_evidence(
            self.repository_root,
            report,
            relative_path=c.Infra.ACCESSOR_MIGRATION_REPORT_RELATIVE_PATH,
        )
        if published.failure:
            return r[m.Infra.AccessorMigrationReport].from_failure(published)
        return r[m.Infra.AccessorMigrationReport].ok(report)

    @classmethod
    def execute_payload(
        cls,
        params: m.Infra.AccessorMigrationInput,
    ) -> p.Result[m.Infra.AccessorMigrationReport]:
        """Execute accessor migration from the validated command service.

        Returns:
            The resulting ``p.Result[m.Infra.AccessorMigrationReport]``.

        """
        result = cls(
            repository_root=params.repository_root,
            selected_projects=params.projects,
            apply_changes=params.apply,
            target_module=params.module,
            target_namespace=params.namespace,
            preview_limit=params.preview_limit,
            gates=",".join(params.gates),
        ).execute()
        if result.failure:
            return r[m.Infra.AccessorMigrationReport].from_failure(result)
        cli.display_text(cls.render_text(result.value))
        return r[m.Infra.AccessorMigrationReport].ok(result.value)


__all__: list[str] = ["FlextInfraAccessorMigrationOrchestrator"]
