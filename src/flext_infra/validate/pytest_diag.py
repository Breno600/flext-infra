"""Pytest diagnostics extraction service.

Extracts strict pytest diagnostics from JUnit XML and structured report-log outputs,
producing structured failure/error/warning/skip/slow-test reports.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, ClassVar, override

from flext_infra import c, m, r, u
from flext_infra.base import s
from flext_infra.validate._pytest_diag_xml import FlextInfraPytestDiagXmlMixin

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraPytestDiagExtractor(FlextInfraPytestDiagXmlMixin, s[bool]):
    """Extracts pytest diagnostics from the runner's required report artifacts.

    Parses required JUnit XML for structured failure/error/skip/timing data
    and the explicit report-log for every warning occurrence.
    The human-readable pytest log remains required diagnostic evidence.
    """

    model_config: ClassVar[m.ConfigDict] = m.ConfigDict(populate_by_name=True)

    junit: Annotated[Path, m.Field(description="JUnit XML path")]
    log_path: Annotated[Path, m.Field(description="Pytest log path")] = m.Field(
        alias="log",
    )
    report_log: Annotated[Path, m.Field(description="Pytest report-log JSONL path")]
    failed: Annotated[
        Path | None,
        m.Field(description="Path to write failed cases"),
    ] = None
    errors: Annotated[
        Path | None,
        m.Field(description="Path to write error traces"),
    ] = None
    warnings: Annotated[Path | None, m.Field(description="Path to write warnings")] = (
        None
    )
    slowest: Annotated[
        Path | None,
        m.Field(description="Path to write slowest entries"),
    ] = None
    skips: Annotated[
        Path | None,
        m.Field(description="Path to write skipped cases"),
    ] = None

    @classmethod
    def _extract_report_events(cls, report_log: Path, diag: m.Infra.DiagResult) -> None:
        """Read real test attempts and every warning independently of terminal text.

        Every reported node must show one setup and one teardown phase, plus a
        call phase whenever setup passed; a missing or repeated phase fails.

        Raises:
            ValueError: If pytest report log contains no events; or if incomplete pytest
                lifecycle.

        """
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
        for nodeid, phases in diag.reported_phases.items():
            if (
                "setup" not in phases
                or "teardown" not in phases
                or (phases["setup"] == "passed" and "call" not in phases)
            ):
                msg = f"incomplete pytest lifecycle: {nodeid}: {dict(phases)}"
                raise ValueError(msg)

    @staticmethod
    def _record_case_event(
        event: m.Infra.PytestReportEvent,
        diag: m.Infra.DiagResult,
    ) -> None:
        if event.nodeid is None:
            return
        if event.report_type == "TestReport":
            if event.when is None or event.outcome is None:
                msg = f"TestReport without runtest phase or outcome: {event.nodeid}"
                raise ValueError(msg)
            phases = diag.reported_phases.setdefault(event.nodeid, {})
            if event.when in phases:
                msg = f"duplicate pytest phase: {event.nodeid} {event.when}"
                raise ValueError(msg)
            phases[event.when] = event.outcome
            if event.when == "call":
                FlextInfraPytestDiagExtractor._record_markdown_properties(event, diag)
        elif event.report_type == "CollectReport":
            if event.outcome == "failed":
                diag.collection_failed_cases.append(event.nodeid)
            elif event.outcome == "skipped":
                diag.collection_skip_cases.append(event.nodeid)

    @staticmethod
    def _record_markdown_properties(
        event: m.Infra.PytestReportEvent,
        diag: m.Infra.DiagResult,
    ) -> None:
        """Validate public properties once at their typed ingress boundary.

        Raises:
            TypeError: If Markdown evidence does not contain typed JSON text.
            ValueError: If Markdown origin differs from reported node; or if
                Markdown attempt proof differs from reported node.
        """
        for name, value in event.user_properties:
            if name not in {"flext_markdown_origin", "flext_markdown_attempt"}:
                continue
            if not isinstance(value, str):
                msg = "Markdown evidence must contain typed JSON text"
                raise TypeError(msg)
            if name == "flext_markdown_origin":
                item = m.Infra.PytestMarkdownItem.model_validate_json(value)
                if item.node_id != event.nodeid:
                    msg = "Markdown origin differs from reported node"
                    raise ValueError(msg)
                diag.markdown_items.append(item)
            else:
                proof = m.Infra.PytestMarkdownAttempt.model_validate_json(value)
                if proof.node_id != event.nodeid:
                    msg = "Markdown attempt proof differs from reported node"
                    raise ValueError(msg)
                diag.markdown_attempts.append(proof)

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

    def extract(
        self,
        junit_path: Path,
        log_path: Path,
        *,
        report_log: Path,
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
        cls,
        report_log: Path,
    ) -> p.Result[m.Infra.PytestDiagnostics]:
        """Read collection-only evidence through the same runtime event boundary.

        Returns:
            The resulting ``p.Result[m.Infra.PytestDiagnostics]``.

        """
        diag = m.Infra.DiagResult()
        cls._extract_report_events(report_log, diag)
        return r.ok(cls._diagnostics_model(diag))

    @staticmethod
    def _read_log_text(log_path: Path) -> str:
        """Read the required pytest log without exception normalization.

        Returns:
            The resulting ``str``.

        """
        return log_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)

    @staticmethod
    def _diagnostics_model(diag: m.Infra.DiagResult) -> m.Infra.PytestDiagnostics:
        """Convert mutable extraction state to the canonical diagnostics model.

        Returns:
            The resulting ``m.Infra.PytestDiagnostics``.

        """
        return m.Infra.PytestDiagnostics(
            failed_count=len(diag.failed_cases),
            error_count=len(diag.error_cases),
            warning_count=len(diag.warning_lines),
            skipped_count=len(diag.skip_cases),
            collection_failed_count=len(diag.collection_failed_cases),
            collection_skipped_count=len(diag.collection_skip_cases),
            collection_failed_cases=tuple(diag.collection_failed_cases),
            collection_skip_cases=tuple(diag.collection_skip_cases),
            reported_node_ids=tuple(sorted(diag.reported_phases)),
            phase_outcomes=tuple(
                m.Infra.PytestPhaseOutcome.model_validate({
                    "node_id": node_id,
                    "phase": phase,
                    "outcome": outcome,
                })
                for node_id, phases in sorted(diag.reported_phases.items())
                for phase, outcome in phases.items()
            ),
            markdown_attempts=tuple(diag.markdown_attempts),
            markdown_items=tuple(diag.markdown_items),
            failed_cases=diag.failed_cases,
            error_traces=diag.error_traces,
            warning_lines=diag.warning_lines,
            skip_cases=diag.skip_cases,
            slow_entries=diag.slow_entries,
        )

    def _extract_diagnostics(
        self,
        junit_path: Path,
        log_path: Path,
        *,
        report_log: Path,
    ) -> p.Result[m.Infra.PytestDiagnostics]:
        """Extract pytest diagnostics after input normalization.

        Returns:
            The resulting ``p.Result[m.Infra.PytestDiagnostics]``.

        """
        self._read_log_text(log_path)
        diag = m.Infra.DiagResult()
        self._parse_xml(junit_path, diag)
        self._extract_report_events(report_log, diag)
        return r[m.Infra.PytestDiagnostics].ok(self._diagnostics_model(diag))

    @override
    def execute(self) -> p.Result[bool]:
        """Execute the pytest diagnostics CLI flow.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        diagnostics = self.extract(
            self.junit,
            self.log_path,
            report_log=self.report_log,
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
                output_path,
                separator.join(items) + "\n",
            ).unwrap()
        sys.stdout.write(
            f"failed_count={diagnostics.failed_count}\n"
            f"error_count={diagnostics.error_count}\n"
            f"warning_count={diagnostics.warning_count}\n"
            f"skipped_count={diagnostics.skipped_count}\n",
        )
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraPytestDiagExtractor"]
