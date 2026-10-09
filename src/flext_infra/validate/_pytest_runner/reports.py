"""Durable diagnostics and execution accounting for pytest.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from defusedxml import ElementTree as DefusedET

from flext_infra import c, m, r, u
from flext_infra.validate._pytest_runner.base import FlextInfraPytestRunnerBase
from flext_infra.validate.pytest_diag import FlextInfraPytestDiagExtractor

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraPytestRunnerReports(FlextInfraPytestRunnerBase):
    """Validate and persist pytest evidence."""

    @staticmethod
    def _write_run_context(report_dir: Path, context: m.Infra.PytestRunContext) -> None:
        """Name the mode and database before any subprocess can fail."""
        u.Cli.atomic_write_text_file(
            report_dir / "run-context.json",
            context.model_dump_json(indent=2) + "\n",
        ).unwrap()
        u.Cli.atomic_write_text_file(
            report_dir.parent / "latest.txt",
            f"{report_dir.name}\n",
        ).unwrap()

    @staticmethod
    def _failure_detail(message: str, pytest_log: Path) -> str:
        """Attach the bounded log tail to an artifact failure.

        Returns:
            The resulting ``str``.

        """
        tail = "\n".join(pytest_log.read_text(encoding="utf-8").splitlines()[-40:])
        return f"{message}\n--- pytest.log (tail) ---\n{tail}" if tail else message

    def _accounting(
        self,
        junit: Path,
        log: Path,
        *,
        cache_restored: bool,
        reported_count: int,
    ) -> p.Result[m.Infra.TestmonRunAccounting]:
        """Parse typed executed/deselected accounting from durable artifacts.

        Returns:
            The resulting ``p.Result[m.Infra.TestmonRunAccounting]``.

        Raises:
            FileNotFoundError: If ``not junit.exists()``.
            RuntimeError: Always; or if non-coverage accounting requires the durable
                selection plan; or if testmon selected node IDs outside the complete
                collection inventory.
            ValueError: If JUnit must be a regular file; or if ``junit.stat().st_size ==
                0``; or if ``root is None``.

        """
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
        executed = sum(1 for _ in root.iter("testcase"))
        context = m.Infra.PytestRunContext.model_validate_json(
            (log.parent / "run-context.json").read_text(encoding="utf-8"),
        )
        deselected = 0
        inventory_count = None
        owns_no_tests = False
        selection_plan: m.Infra.PytestSelectionPlan | None = None
        if context.execution_mode != c.Infra.PytestExecutionMode.COVERAGE:
            selection_plan = m.Infra.PytestSelectionPlan.model_validate_json(
                (log.parent / "selection-plan.json").read_text(encoding="utf-8"),
            )
            owns_no_tests = selection_plan.owns_no_tests
        if owns_no_tests and selection_plan is not None:
            # The declared empty suite produces no manifest artifacts: zero
            # execution with typed accounting IS the receipt.
            accounting = m.Infra.TestmonRunAccounting(
                executed_count=executed,
                reported_count=reported_count,
                deselected_count=0,
                inventory_count=0,
                cache_restored=cache_restored,
                owns_no_tests=True,
            )
            return r.ok(accounting)
        if context.execution_mode != c.Infra.PytestExecutionMode.COVERAGE:
            if selection_plan is None:
                msg = (
                    "non-coverage accounting requires the durable selection plan: "
                    f"{log.parent / 'selection-plan.json'}"
                )
                raise RuntimeError(msg)
            selected = (
                m.Infra.PytestCollectionManifest.model_validate_json(
                    selection_plan.manifest_path.read_text(encoding="utf-8"),
                )
                if context.execution_mode == c.Infra.PytestExecutionMode.FULL
                else m.Infra.PytestCollectionManifest.model_validate_json(
                    (log.parent / "testmon-selection.json").read_text(encoding="utf-8"),
                )
            )
            inventory = (
                selected
                if not selection_plan.inventory_collected
                else m.Infra.PytestCollectionManifest.model_validate_json(
                    (log.parent / "testmon-inventory.json").read_text(encoding="utf-8"),
                )
            )
            if not set(selected.node_ids).issubset(inventory.node_ids):
                msg = (
                    "testmon selected node IDs outside the complete "
                    "collection inventory"
                )
                raise RuntimeError(msg)
            inventory_count = len(inventory.node_ids)
            deselected = inventory_count - len(selected.node_ids)
        accounting = m.Infra.TestmonRunAccounting(
            executed_count=executed,
            reported_count=reported_count,
            deselected_count=deselected,
            inventory_count=inventory_count,
            cache_restored=cache_restored,
            owns_no_tests=owns_no_tests,
        )
        if executed:
            return r.ok(accounting)
        if cache_restored and deselected:
            return r.ok(accounting)
        msg = self._failure_detail("pytest executed zero tests", log)
        raise RuntimeError(msg)

    def _diagnostics(self, report_dir: Path) -> p.Result[m.Infra.PytestDiagnostics]:
        """Extract diagnostics through the canonical typed service.

        Returns:
            The resulting ``p.Result[m.Infra.PytestDiagnostics]``.

        """
        extractor = FlextInfraPytestDiagExtractor(
            repository_root=self.root,
            junit=report_dir / "junit.xml",
            log=report_dir / "pytest.log",
            report_log=report_dir / "events.jsonl",
        )
        return extractor.extract(
            extractor.junit,
            extractor.log_path,
            report_log=extractor.report_log,
        )

    @staticmethod
    def _collection_diagnostics(report_log: Path) -> None:
        """Require complete collection evidence before accepting a selection.

        Raises:
            RuntimeError: If pytest collection contains blocking findings.

        """
        diagnostics = FlextInfraPytestDiagExtractor.extract_report_log(
            report_log,
        ).unwrap()
        receipt = report_log.with_suffix(".diagnostics.json")
        u.Cli.atomic_write_text_file(
            receipt,
            diagnostics.model_dump_json(indent=2) + "\n",
        ).unwrap()
        if any((
            diagnostics.collection_failed_count,
            diagnostics.collection_skipped_count,
            diagnostics.warning_count,
        )):
            msg = f"pytest collection contains blocking findings: {receipt}"
            raise RuntimeError(msg)

    @staticmethod
    def _phase_diagnostics(
        report_dir: Path,
        *,
        context: m.Infra.PytestRunContext,
        suite: m.Infra.PytestDiagnostics,
    ) -> t.VariadicTuple[t.Pair[str, m.Infra.PytestDiagnostics]]:
        """Read each subprocess receipt once in execution order.

        Returns:
            The resulting ``t.VariadicTuple[t.Pair[str, m.Infra.PytestDiagnostics]]``.

        """
        phases: t.MutableSequenceOf[t.Pair[str, m.Infra.PytestDiagnostics]] = []
        if context.execution_mode != c.Infra.PytestExecutionMode.COVERAGE:
            selection_plan = m.Infra.PytestSelectionPlan.model_validate_json(
                (report_dir / "selection-plan.json").read_text(encoding="utf-8"),
            )
            if selection_plan.owns_no_tests:
                # The declared empty suite ran no collection subprocess, so no
                # per-phase receipt exists: only the suite diagnostics.
                return (("suite", suite),)
            names = (
                (
                    ("selection", "inventory")
                    if selection_plan.inventory_collected
                    else ("selection",)
                )
                if context.execution_mode == c.Infra.PytestExecutionMode.INCREMENTAL
                else ("inventory",)
            )
            for phase in names:
                receipt = report_dir / f"testmon-{phase}.events.diagnostics.json"
                phases.append((
                    phase,
                    m.Infra.PytestDiagnostics.model_validate_json(
                        receipt.read_text(encoding="utf-8"),
                    ),
                ))
        return (*phases, ("suite", suite))

    def _validate_coverage(self, report_dir: Path) -> p.Result[bool]:
        """Require a non-empty coverage report; the percentage is never a gate.

        Returns:
            The resulting ``p.Result[bool]``.

        Raises:
            FileNotFoundError: If ``not coverage.exists()``.
            ValueError: If coverage artifact must be a regular file; or if
                ``coverage.stat().st_size == 0``.

        """
        coverage = report_dir / "coverage.xml"
        if not coverage.exists():
            raise FileNotFoundError(coverage)
        if not coverage.is_file():
            msg = f"coverage artifact must be a regular file: {coverage}"
            raise ValueError(msg)
        if coverage.stat().st_size == 0:
            msg = self._failure_detail(
                f"empty coverage artifact: {coverage}",
                report_dir / "pytest.log",
            )
            raise ValueError(msg)
        return r.ok(value=True)

    @staticmethod
    def _write_diagnostics(
        report_dir: Path,
        diagnostics: m.Infra.PytestDiagnostics,
        *,
        phases: t.VariadicTuple[t.Pair[str, m.Infra.PytestDiagnostics]],
    ) -> None:
        """Persist each typed diagnostics channel."""
        outputs: t.VariadicTuple[t.Triple[str, t.StrSequence, str]] = (
            ("failed-tests.txt", diagnostics.failed_cases, "\n\n"),
            ("errors.txt", diagnostics.error_traces, "\n\n"),
            (
                "warnings.txt",
                tuple(
                    f"{phase}: {line}"
                    for phase, item in phases
                    for line in item.warning_lines
                ),
                "\n",
            ),
            ("skipped-tests.txt", diagnostics.skip_cases, "\n"),
            ("slowest-tests.txt", diagnostics.slow_entries, "\n"),
        )
        for filename, values, separator in outputs:
            body = separator.join(values) + ("\n" if values else "")
            u.Cli.atomic_write_text_file(report_dir / filename, body).unwrap()


__all__: list[str] = ["FlextInfraPytestRunnerReports"]
