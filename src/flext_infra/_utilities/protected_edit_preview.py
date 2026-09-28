"""Preview and reverted-report flows for protected edit workflows."""

from __future__ import annotations

import operator
from collections.abc import Callable, MutableMapping
from pathlib import Path

from flext_infra import c, t

from .protected_edit_linting import FlextInfraUtilitiesProtectedEditLinting


class FlextInfraUtilitiesProtectedEditPreview(FlextInfraUtilitiesProtectedEditLinting):
    """Preview and revert-report helpers for protected edit workflows."""

    @staticmethod
    def _normalized_source_updates(
        updates: t.MappingKV[Path, str],
    ) -> MutableMapping[Path, str]:
        """Return one update map keyed by resolved path in deterministic order."""
        return {
            path.resolve(): content
            for path, content in sorted(updates.items(), key=operator.itemgetter(0))
        }

    @staticmethod
    def _preview_write_baselines(
        updates: t.MappingKV[Path, str],
        workspace: Path,
        gates: t.StrSequence | None = None,
    ) -> t.Pair[
        MutableMapping[Path, str | None], MutableMapping[Path, t.Infra.LintSnapshot]
    ]:
        """Preview write baselines."""
        before_sources: MutableMapping[Path, str | None] = {}
        before_lints: MutableMapping[Path, t.Infra.LintSnapshot] = {}
        existing_paths: list[Path] = []
        for path in updates:
            if path.exists():
                before_sources[path] = path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
                existing_paths.append(path)
                continue
            before_sources[path] = None
        if existing_paths:
            before_lints.update(
                FlextInfraUtilitiesProtectedEditPreview.lint_snapshots(
                    tuple(existing_paths), workspace, gates=gates
                )
            )
        for path in updates:
            if before_sources[path] is not None:
                continue
            before_lints[path] = (
                FlextInfraUtilitiesProtectedEditPreview._new_file_lint_baseline(
                    path, workspace, gates=gates
                )
            )
        return before_sources, before_lints

    @staticmethod
    def _restore_preview_sources(before_sources: t.MappingKV[Path, str | None]) -> None:
        """Restore preview sources."""
        for path, original_source in before_sources.items():
            if original_source is None:
                if path.exists():
                    path.unlink()
                continue
            path.write_text(original_source, encoding=c.Cli.ENCODING_DEFAULT)

    @staticmethod
    def _reverted_report_lines(
        path: Path,
        workspace: Path,
        before_source: str,
        new_errors: t.Infra.LintSnapshot,
        pytest_failure: str | None = None,
    ) -> list[str]:
        """Reverted report lines."""
        rel = FlextInfraUtilitiesProtectedEditPreview._relative_path(path, workspace)
        modified = path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        diff = FlextInfraUtilitiesProtectedEditPreview.unified_diff_lines(
            before_source,
            modified,
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            max_lines=30,
        )
        report_lines = [f"  REVERTED {rel}:"]
        report_lines.extend(f"    {line.rstrip()}" for line in diff)
        for tool, messages in new_errors.items():
            report_lines.extend((
                f"    NEW {tool} errors:",
                *(f"      {message}" for message in messages[:5]),
            ))
        if pytest_failure:
            report_lines.append(f"    pytest failure: {pytest_failure}")
        return report_lines

    @staticmethod
    def _preview_write_reports(
        updates: t.MappingKV[Path, str],
        before_sources: t.MappingKV[Path, str | None],
        before_lints: t.MappingKV[Path, t.Infra.LintSnapshot],
        workspace: Path,
        gates: t.StrSequence | None = None,
    ) -> t.Infra.EditResult:
        """Preview write reports."""
        reports: list[str] = []
        failed = False
        after_lints = FlextInfraUtilitiesProtectedEditPreview.lint_snapshots(
            tuple(updates), workspace, gates=gates
        )
        for path in updates:
            new_errors = FlextInfraUtilitiesProtectedEditPreview.lint_new_errors(
                before_lints[path], after_lints[path]
            )
            if not new_errors:
                continue
            failed = True
            reports.extend(
                FlextInfraUtilitiesProtectedEditPreview._reverted_report_lines(
                    path, workspace, before_sources[path] or "", new_errors
                )
            )
        return (not failed, reports)

    @staticmethod
    def preview_source_writes(
        updates: t.MappingKV[Path, str],
        *,
        workspace: Path,
        gates: t.StrSequence | None = None,
        post_write: Callable[[], None] | None = None,
    ) -> t.Infra.EditResult:
        """Preview multiple file writes transactionally and always restore sources."""
        if not updates:
            return (True, [])

        normalized_updates = (
            FlextInfraUtilitiesProtectedEditPreview._normalized_source_updates(updates)
        )
        before_sources, before_lints = (
            FlextInfraUtilitiesProtectedEditPreview._preview_write_baselines(
                normalized_updates, workspace, gates=gates
            )
        )

        try:
            for path, updated_source in normalized_updates.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(updated_source, encoding=c.Cli.ENCODING_DEFAULT)
            if post_write is not None:
                post_write()
            return FlextInfraUtilitiesProtectedEditPreview._preview_write_reports(
                normalized_updates, before_sources, before_lints, workspace, gates=gates
            )
        finally:
            FlextInfraUtilitiesProtectedEditPreview._restore_preview_sources(
                before_sources
            )


__all__: list[str] = ["FlextInfraUtilitiesProtectedEditPreview"]
