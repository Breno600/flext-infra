"""Accessor per-file lint processing + report rendering — extracted concern.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from flext_infra import m, u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import t


class FlextInfraAccessorMigrationReportMixin:
    """Per-file lint snapshot/write and CLI report rendering.

    Composed into FlextInfraAccessorMigrationOrchestrator via inheritance; the
    facade provides ``dry_run`` / ``repository_root`` / the gate-name properties
    through FLEXT (declared below for static resolution).
    """

    if TYPE_CHECKING:
        dry_run: bool
        repository_root: Path

        @property
        def gate_names(self) -> t.StrSequence: ...

        @property
        def lint_tool_names(self) -> t.StrSequence: ...

        def _apply_automated_rewrites(
            self,
            rope_project: t.Infra.RopeProject,
            py_file: Path,
            source: str,
        ) -> t.Pair[str, t.SequenceOf[m.Infra.AccessorMigrationChange]]: ...

        def _collect_manual_warnings(
            self,
            py_file: Path,
            source: str,
        ) -> t.SequenceOf[m.Infra.AccessorMigrationChange]: ...

    @staticmethod
    def _accumulate_lint_totals(
        totals: MutableMapping[str, int],
        snapshot: t.Infra.LintSnapshot,
    ) -> None:
        """Accumulate lint totals."""
        for tool, lines in snapshot.items():
            totals[tool] = totals.get(tool, 0) + len(tuple(lines))

    def _process_file(
        self,
        rope_project: t.Infra.RopeProject,
        py_file: Path,
        source: str,
        *,
        preview_available: bool,
    ) -> m.Infra.AccessorMigrationFile:
        """Rewrite one file, collect its manual warnings and lint evidence.

        Returns:
            The resulting ``m.Infra.AccessorMigrationFile``.

        """
        updated_source, automated_changes = self._apply_automated_rewrites(
            rope_project,
            py_file,
            source,
        )
        warnings = list(self._collect_manual_warnings(py_file, source))
        include_preview = bool(automated_changes or warnings) and preview_available
        lint_before: MutableMapping[str, t.StrSequence] = {}
        lint_after: MutableMapping[str, t.StrSequence] = {}
        new_lint_errors: MutableMapping[str, t.StrSequence] = {}
        before: t.Infra.LintSnapshot = {}
        after: t.Infra.LintSnapshot = {}
        if automated_changes:
            if self.dry_run and include_preview:
                before, after = u.Infra.preview_source_lint(
                    py_file,
                    self.repository_root,
                    updated_source=updated_source,
                    gates=self.gate_names,
                )
            elif not self.dry_run:
                before = (
                    u.Infra.lint_snapshot(
                        py_file,
                        self.repository_root,
                        gates=self.gate_names,
                    )
                    if include_preview
                    else {}
                )
                ok, report = u.Infra.protected_source_write(
                    py_file,
                    request=m.Infra.ProtectedSourceWriteRequest(
                        workspace=self.repository_root,
                        updated_source=updated_source,
                        gates=self.gate_names,
                    ),
                )
                if not ok:
                    warnings.append(
                        m.Infra.AccessorMigrationChange(
                            file=str(py_file),
                            line=0,
                            original_name="protected_write",
                            replacement_name="",
                            automated=False,
                            reason=" ; ".join(report[:3]) or "protected write failed",
                        ),
                    )
                after = (
                    u.Infra.lint_snapshot(
                        py_file,
                        self.repository_root,
                        gates=self.gate_names,
                    )
                    if include_preview
                    else {}
                )
            else:
                before = {}
                after = {}
            if include_preview:
                lint_before = self._freeze_lints(before)
                lint_after = self._freeze_lints(after)
                new_lint_errors = self._freeze_lints(
                    u.Infra.lint_new_errors(before, after),
                )
        return m.Infra.AccessorMigrationFile(
            file=str(py_file),
            lint_tools=tuple(self.lint_tool_names)
            if automated_changes and include_preview
            else (),
            automated_changes=tuple(automated_changes),
            warnings=tuple(warnings),
            diff=self._diff(py_file, source, updated_source)
            if automated_changes and include_preview
            else "",
            lint_before=lint_before,
            lint_after=lint_after,
            new_lint_errors=new_lint_errors,
        )

    @staticmethod
    def _freeze_lints(
        snapshot: t.Infra.LintSnapshot,
    ) -> MutableMapping[str, t.StrSequence]:
        """Freeze lints.

        Returns:
            The resulting ``MutableMapping[str, t.StrSequence]``.

        """
        return {tool: tuple(lines) for tool, lines in snapshot.items()}

    @staticmethod
    def _diff(py_file: Path, before: str, after: str) -> str:
        """Diff.

        Returns:
            The resulting ``str``.

        """
        diff_lines = u.Infra.unified_diff_lines(
            before,
            after,
            fromfile=f"a/{py_file}",
            tofile=f"b/{py_file}",
            max_lines=80,
        )
        return "".join(diff_lines)

    @staticmethod
    def render_text(report: m.Infra.AccessorMigrationReport) -> str:
        """Render an accessor migration report as CLI text.

        Returns:
            The resulting ``str``.

        """
        lines: t.MutableSequenceOf[str] = [
            "Accessor Migration",
            f"workspace: {report.workspace}",
            f"mode: {'dry-run' if report.dry_run else 'apply'}",
            f"files_scanned: {report.files_scanned}",
            f"files_with_changes: {report.files_with_changes}",
            f"automated_changes: {report.automated_change_count}",
            f"warnings: {report.warning_count}",
            f"lint_tools: {', '.join(report.lint_tools)}",
        ]
        for tool in report.lint_tools:
            lines.append(
                f"lint-totals:{tool} "
                f"before={report.lint_before_totals.get(tool, 0)} "
                f"after={report.lint_after_totals.get(tool, 0)} "
                f"new={report.new_lint_error_totals.get(tool, 0)}",
            )
        for file_report in report.files:
            lines.append(f"\n{file_report.file}")
            for change in file_report.automated_changes:
                lines.append(
                    f"  auto:{change.line} {change.original_name} "
                    f"-> {change.replacement_name}",
                )
            for warning in file_report.warnings:
                target = (
                    f" -> {warning.replacement_name}"
                    if warning.replacement_name
                    else ""
                )
                lines.append(f"  warn:{warning.line} {warning.original_name}{target}")
                lines.append(f"    {warning.reason}")
            for tool in file_report.lint_tools:
                issues = tuple(file_report.lint_after.get(tool, ()))
                lines.append(f"  lint-after:{tool}")
                if not issues:
                    lines.append("    ok")
                    continue
                lines.extend(f"    {issue}" for issue in issues[:4])
            for tool in file_report.lint_tools:
                issues = tuple(file_report.new_lint_errors.get(tool, ()))
                if not issues:
                    continue
                lines.append(f"  new-lint:{tool}")
                lines.extend(f"    {issue}" for issue in issues[:4])
            if file_report.diff:
                lines.append("  diff:")
                lines.extend(
                    f"    {line}"
                    for line in file_report.diff.rstrip().splitlines()[:40]
                )
        return "\n".join(lines)


__all__: list[str] = ["FlextInfraAccessorMigrationReportMixin"]
