"""Pytest diagnostics extraction service.

Extracts strict pytest diagnostics from JUnit XML and structured report-log outputs,
producing structured failure/error/warning/skip/slow-test reports.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, override

from flext_core import r
from flext_infra import c, m, u

from ..base import s
from ._pytest_diag_xml import FlextInfraPytestDiagXmlMixin

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraPytestDiagExtractor(FlextInfraPytestDiagXmlMixin, s[bool]):
    """Extracts pytest diagnostics from the runner's required report artifacts.

    Parses required JUnit XML for structured failure/error/skip/timing data
    and the explicit report-log for every warning occurrence.
    The human-readable pytest log remains required diagnostic evidence.
    """

    junit: Annotated[Path, m.Field(description="JUnit XML path")]
    log_path: Annotated[Path, m.Field(description="Pytest log path")] = m.Field(
        alias="log"
    )
    report_log: Annotated[Path, m.Field(description="Pytest report-log JSONL path")]
    failed: Annotated[
        Path | None, m.Field(description="Path to write failed cases")
    ] = None
    errors: Annotated[
        Path | None, m.Field(description="Path to write error traces")
    ] = None
    warnings: Annotated[Path | None, m.Field(description="Path to write warnings")] = (
        None
    )
    slowest: Annotated[
        Path | None, m.Field(description="Path to write slowest entries")
    ] = None
    skips: Annotated[
        Path | None, m.Field(description="Path to write skipped cases")
    ] = None

    @classmethod
    def _extract_report_events(cls, report_log: Path, diag: m.Infra.DiagResult) -> None:
        """Read real test attempts and every warning independently of terminal text."""
        lines = report_log.read_text(encoding=c.Cli.ENCODING_DEFAULT).splitlines()
        if not lines:
            msg = f"pytest report log contains no events: {report_log}"
            raise ValueError(msg)
        warnings = []
        for line in lines:
            event = m.Infra.PytestReportEvent.model_validate_json(line)
            if event.report_type == "WarningMessage":
                warnings.append(event)
            else:
                cls._record_case_event(event, diag)
        identities = [
            m.Infra.PytestWarningEvent.model_validate_json(line)
            for line in report_log
            .with_suffix(c.Infra.PYTEST_WARNING_EVENTS_SUFFIX)
            .read_text(encoding=c.Cli.ENCODING_DEFAULT)
            .splitlines()
        ]
        for event, identity in zip(warnings, identities, strict=True):
            cls._record_warning(event, identity, diag)

    @staticmethod
    def _record_case_event(
        event: m.Infra.PytestReportEvent, diag: m.Infra.DiagResult
    ) -> None:
        if event.nodeid is None:
            return
        if event.report_type == "TestReport":
            diag.reported_node_ids.append(event.nodeid)
        elif event.report_type == "CollectReport":
            if event.outcome == "failed":
                diag.collection_failed_cases.append(event.nodeid)
            elif event.outcome == "skipped":
                diag.collection_skip_cases.append(event.nodeid)

    @staticmethod
    def _record_warning(
        event: m.Infra.PytestReportEvent,
        identity: m.Infra.PytestWarningEvent,
        diag: m.Infra.DiagResult,
    ) -> None:
        if (event.category, event.filename, event.lineno, event.message) != (
            identity.category,
            identity.filename,
            identity.lineno,
            identity.message,
        ):
            msg = "WarningMessage differs from its recorded runtime identity"
            raise ValueError(msg)
        warning = (
            f"{identity.filename}:{identity.lineno}: "
            f"{identity.category_module}.{identity.category_qualname}: "
            f"{identity.message}"
        )
        diag.warning_lines.append(warning)
        if identity.suspended:
            diag.suspended_warning_lines.append(warning)

    def extract(
        self, junit_path: Path, log_path: Path, *, report_log: Path
    ) -> p.Result[m.Infra.PytestDiagnostics]:
        """Extract diagnostics from JUnit XML, pytest log and explicit report-log.

        Args:
            junit_path: Path to JUnit XML result file.
            log_path: Path to raw pytest log output.
            report_log: Path to the structured pytest report-log.

        Returns:
            r with diagnostics dict containing counts and entries.

        """
        return self._extract_diagnostics(junit_path, log_path, report_log=report_log)

    @classmethod
    def extract_report_log(
        cls, report_log: Path
    ) -> p.Result[m.Infra.PytestDiagnostics]:
        """Read collection-only evidence through the same runtime event boundary."""
        diag = m.Infra.DiagResult()
        cls._extract_report_events(report_log, diag)
        return r.ok(cls._diagnostics_model(diag))

    @staticmethod
    def _read_log_text(log_path: Path) -> str:
        """Read the required pytest log without exception normalization."""
        return log_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)

    @staticmethod
    def _diagnostics_model(diag: m.Infra.DiagResult) -> m.Infra.PytestDiagnostics:
        """Convert mutable extraction state to the canonical diagnostics model."""
        return m.Infra.PytestDiagnostics(
            failed_count=len(diag.failed_cases),
            error_count=len(diag.error_cases),
            warning_count=len(diag.warning_lines),
            blocking_warning_count=(
                len(diag.warning_lines) - len(diag.suspended_warning_lines)
            ),
            suspended_warning_count=len(diag.suspended_warning_lines),
            skipped_count=len(diag.skip_cases),
            collection_failed_count=len(diag.collection_failed_cases),
            collection_skipped_count=len(diag.collection_skip_cases),
            collection_failed_cases=tuple(diag.collection_failed_cases),
            collection_skip_cases=tuple(diag.collection_skip_cases),
            reported_node_ids=tuple(sorted(set(diag.reported_node_ids))),
            failed_cases=diag.failed_cases,
            error_traces=diag.error_traces,
            warning_lines=diag.warning_lines,
            suspended_warning_lines=diag.suspended_warning_lines,
            skip_cases=diag.skip_cases,
            slow_entries=diag.slow_entries,
        )

    def _extract_diagnostics(
        self, junit_path: Path, log_path: Path, *, report_log: Path
    ) -> p.Result[m.Infra.PytestDiagnostics]:
        """Extract pytest diagnostics after input normalization."""
        self._read_log_text(log_path)
        diag = m.Infra.DiagResult()
        self._parse_xml(junit_path, diag)
        self._extract_report_events(report_log, diag)
        return r[m.Infra.PytestDiagnostics].ok(self._diagnostics_model(diag))

    @override
    def execute(self) -> p.Result[bool]:
        """Execute the pytest diagnostics CLI flow."""
        diagnostics = self.extract(
            self.junit, self.log_path, report_log=self.report_log
        ).unwrap()
        for output_path, attr_name, separator in [
            (self.failed, "failed_cases", "\n\n"),
            (self.errors, "error_traces", "\n\n"),
            (self.warnings, "warning_lines", "\n"),
            (self.slowest, "slow_entries", "\n"),
            (self.skips, "skip_cases", "\n"),
        ]:
            if output_path is None:
                continue
            items = getattr(diagnostics, attr_name)
            u.Cli.atomic_write_text_file(
                output_path, separator.join(items) + "\n"
            ).unwrap()
        sys.stdout.write(
            f"failed_count={diagnostics.failed_count}\n"
            f"error_count={diagnostics.error_count}\n"
            f"warning_count={diagnostics.warning_count}\n"
            f"blocking_warning_count={diagnostics.blocking_warning_count}\n"
            f"suspended_warning_count={diagnostics.suspended_warning_count}\n"
            f"skipped_count={diagnostics.skipped_count}\n"
        )
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraPytestDiagExtractor"]
