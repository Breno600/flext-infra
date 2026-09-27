"""Durable diagnostics and execution accounting for pytest."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from defusedxml import ElementTree as DefusedET

from flext_core import e, r
from flext_infra import c, config, m, u
from flext_infra.validate.pytest_diag import FlextInfraPytestDiagExtractor

from .base import FlextInfraPytestRunnerBase

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraPytestRunnerReports(FlextInfraPytestRunnerBase):
    """Validate and persist pytest evidence."""

    @staticmethod
    def _failure_detail(message: str, pytest_log: Path) -> str:
        """Preserve the original log with an artifact failure."""
        return f"{message}\n{pytest_log.read_text(encoding='utf-8')}"

    @staticmethod
    def _events(path: Path) -> tuple[m.Infra.PytestReportEvent, ...]:
        """Read native reportlog records through their typed boundary."""
        return tuple(
            m.Infra.PytestReportEvent.model_validate_json(line)
            for line in path.read_text(encoding=c.Cli.ENCODING_DEFAULT).splitlines()
            if line.strip()
        )

    @classmethod
    def _executed_nodes(cls, report_dir: Path) -> tuple[str, ...]:
        """Require a complete setup/call/teardown lifecycle for each selected node."""
        phases: dict[str, dict[str, str]] = {}
        for event in cls._events(report_dir / "events.jsonl"):
            if event.report_type != "TestReport":
                continue
            if (
                not event.nodeid
                or event.when not in {"setup", "call", "teardown"}
                or event.outcome is None
            ):
                msg = f"invalid pytest test report: {event.model_dump_json()}"
                raise ValueError(msg)
            node = phases.setdefault(event.nodeid, {})
            if event.when in node:
                msg = f"duplicate pytest phase: {event.nodeid} {event.when}"
                raise ValueError(msg)
            node[event.when] = event.outcome
        for nodeid, node in phases.items():
            if (
                "setup" not in node
                or "teardown" not in node
                or (node["setup"] == "passed" and "call" not in node)
            ):
                msg = f"incomplete pytest lifecycle: {nodeid}: {node}"
                raise ValueError(msg)
        return tuple(sorted(phases))

    def _accounting(
        self,
        junit: Path,
        log: Path,
        *,
        cache_restored: bool,
        mode: Literal["incremental", "full", "coverage"],
        inventory: t.StrSequence,
        selected: t.StrSequence,
    ) -> p.Result[m.Infra.TestmonRunAccounting]:
        """Parse typed executed/deselected accounting from durable artifacts."""
        if not junit.exists():
            raise FileNotFoundError(junit)
        if not junit.is_file():
            msg = f"JUnit must be a regular file: {junit}"
            raise ValueError(msg)
        if junit.stat().st_size == 0:
            msg = self._failure_detail(f"empty JUnit: {junit}", log)
            raise ValueError(msg)
        root = DefusedET.parse(junit).getroot()
        if root is None:
            msg = self._failure_detail(f"JUnit has no document root: {junit}", log)
            raise ValueError(msg)
        executed = self._executed_nodes(log.parent)
        if not executed or set(executed) != set(selected):
            msg_0 = (
                f"pytest execution differs from selection: missing={sorted(set(selected) - set(executed))} "
                f"unexpected={sorted(set(executed) - set(selected))}"
            )
            raise ValueError(msg_0)
        if sum(1 for _ in root.iter("testcase")) < len(executed):
            msg_0 = "JUnit omits executed pytest nodes"
            raise ValueError(msg_0)
        deselected = tuple(sorted(set(inventory) - set(selected)))
        return r.ok(
            m.Infra.TestmonRunAccounting(
                mode=mode,
                inventory=tuple(inventory),
                selected=tuple(selected),
                executed=executed,
                deselected=deselected,
                database=str(self.testmon_db),
                executed_count=len(executed),
                deselected_count=len(deselected),
                cache_restored=cache_restored,
            )
        )

    @classmethod
    def _warning_events(cls, report_dir: Path) -> tuple[m.Infra.PytestReportEvent, ...]:
        """Count native warning events once instead of matching rendered lines."""
        return tuple(
            event
            for path in sorted(report_dir.glob("*events.jsonl"))
            for event in cls._events(path)
            if event.report_type == "WarningMessage"
        )

    @classmethod
    def _collection_skip_lines(cls, report_dir: Path) -> tuple[str, ...]:
        """Retain native collection skips, including their original reason and phase."""
        return tuple(
            f"{path.name}: {event.model_dump_json(by_alias=True)}"
            for path in sorted(report_dir.glob("*events.jsonl"))
            for event in cls._events(path)
            if event.report_type == "CollectReport" and event.outcome == "skipped"
        )

    @staticmethod
    def _warning_suspended(event: m.Infra.PytestReportEvent) -> bool:
        """Apply the shared operator suspension only to owned policy warnings."""
        return (
            config.Infra.codegen.make.policy_check_suspension_reason is not None
            and event.category in {e.MroViolation.__name__, e.SmellViolation.__name__}
        )

    def _diagnostics(self, report_dir: Path) -> p.Result[m.Infra.PytestDiagnostics]:
        """Extract diagnostics through the canonical typed service."""
        extractor = FlextInfraPytestDiagExtractor(
            repository_root=self.root,
            junit=report_dir / "junit.xml",
            log_path=report_dir / "pytest.log",
        )
        diagnostics = extractor.extract(extractor.junit, extractor.log_path).unwrap()
        return r.ok(self._complete_diagnostics(report_dir, diagnostics))

    def _complete_diagnostics(
        self, report_dir: Path, diagnostics: m.Infra.PytestDiagnostics
    ) -> m.Infra.PytestDiagnostics:
        """Combine execution diagnostics with native warnings and collection skips."""
        warnings = self._warning_events(report_dir)
        collection_skips = self._collection_skip_lines(report_dir)
        return diagnostics.model_copy(
            update={
                "warning_count": len(warnings),
                "warning_lines": tuple(
                    f"{event.filename}:{event.lineno}: {event.category}: {event.message}"
                    for event in warnings
                ),
                "skipped_count": diagnostics.skipped_count + len(collection_skips),
                "skip_cases": (*diagnostics.skip_cases, *collection_skips),
            }
        )

    def _validate_coverage(self, report_dir: Path) -> p.Result[bool]:
        """Require a non-empty coverage artifact and no hidden threshold failure."""
        coverage = report_dir / "coverage.xml"
        log = report_dir / "pytest.log"
        if not coverage.exists():
            raise FileNotFoundError(coverage)
        if not coverage.is_file():
            msg = f"coverage artifact must be a regular file: {coverage}"
            raise ValueError(msg)
        if coverage.stat().st_size == 0:
            msg = self._failure_detail(f"empty coverage artifact: {coverage}", log)
            raise ValueError(msg)
        body = log.read_text(encoding="utf-8")
        if c.Infra.PYTEST_COVERAGE_FAILURE_RE.search(body):
            msg = self._failure_detail("coverage threshold failed", log)
            raise RuntimeError(msg)
        return r.ok(True)

    @staticmethod
    def _write_diagnostics(
        report_dir: Path, diagnostics: m.Infra.PytestDiagnostics
    ) -> None:
        """Persist each typed diagnostics channel."""
        outputs: t.VariadicTuple[t.Triple[str, t.StrSequence, str]] = (
            ("failed-tests.txt", diagnostics.failed_cases, "\n\n"),
            ("errors.txt", diagnostics.error_traces, "\n\n"),
            ("warnings.txt", diagnostics.warning_lines, "\n"),
            ("skipped-tests.txt", diagnostics.skip_cases, "\n"),
            ("slowest-tests.txt", diagnostics.slow_entries, "\n"),
        )
        for filename, values, separator in outputs:
            body = separator.join(values) + ("\n" if values else "")
            u.Cli.atomic_write_text_file(report_dir / filename, body).unwrap()


__all__: list[str] = ["FlextInfraPytestRunnerReports"]
