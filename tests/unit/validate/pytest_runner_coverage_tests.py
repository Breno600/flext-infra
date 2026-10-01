"""Coverage verb contract of the public cached-pytest runner."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m, u
from tests.unit.validate.pytest_runner_support import runner_for, summary


class TestsFlextInfraPytestRunnerCoverage:
    """Exercise the real coverage pass and its published accounting."""

    @pytest.mark.slow
    def test_coverage_verb_publishes_artifact_without_testmon(
        self,
        cached_runner_project: Path,
    ) -> None:
        """The coverage pass runs its own process: real artifact, zero testmon."""
        codegen = config.Infra.codegen
        cache = codegen.make.testmon_cache
        reports_root = cached_runner_project / cache.reports_directory
        runner = runner_for(cached_runner_project)

        exit_code = tm.ok(runner.execute_coverage())

        tm.that(exit_code, eq=0)
        latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        coverage = reports_root / latest_name / "coverage.xml"
        tm.that(coverage.is_file(), eq=True)
        tm.that(coverage.stat().st_size > 0, eq=True)
        summary_text = summary(reports_root)
        tm.that(summary_text, has=["executed=1", "failed=0", "exit=0"])
        command = tm.ok(
            u.Cli.files_read_text(reports_root / latest_name / "command.txt"),
        )
        tm.that(command, has="--cov")
        tm.that("--testmon" in command, eq=False)
        inventory_command = runner.build_selection_command(
            report_log=reports_root / latest_name / "testmon-inventory.events.jsonl",
            manifest_path=reports_root / latest_name / "testmon-inventory.json",
            complete=True,
            execution_mode=c.Infra.PytestExecutionMode.COVERAGE,
        )
        tm.that(
            [arg for arg in inventory_command if arg.startswith("--testmon")],
            eq=[],
        )
        tm.that(
            (reports_root / latest_name / "testmon-inventory.json").is_file(),
            eq=True,
        )
        tm.that(runner.testmon_db.exists(), eq=False)

    @pytest.mark.slow
    def test_failed_coverage_suite_preserves_original_failure_and_accounting(
        self,
        cached_runner_project: Path,
    ) -> None:
        """No-cov-on-fail omits coverage without hiding the failed test evidence."""
        runner = runner_for(cached_runner_project)
        (cached_runner_project / runner.target / "test_coverage_failure.py").write_text(
            "def test_coverage_failure() -> None:\n"
            "    assert False, 'original coverage suite failure'\n",
            encoding="utf-8",
        )

        exit_code = tm.ok(runner.execute_coverage())

        tm.that(exit_code, ne=0)
        reports_root = cached_runner_project / runner.reports
        latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        report_dir = reports_root / latest_name
        outcome = m.Cli.ProcessOutcome.model_validate_json(
            tm.ok(u.Cli.files_read_text(report_dir / "suite-outcome.json")),
        )
        tm.that(outcome.raw_return_code, eq=exit_code)
        tm.that(outcome.timed_out, eq=False)
        tm.that(outcome.forwarded_signal, none=True)
        accounting = m.Infra.TestmonRunAccounting.model_validate_json(
            tm.ok(u.Cli.files_read_text(report_dir / "run-accounting.json")),
        )
        tm.that(accounting.executed_count, eq=accounting.reported_count)
        tm.that(accounting.executed_count > 0, eq=True)
        tm.that(accounting.inventory_count, none=True)
        tm.that((report_dir / "coverage.xml").exists(), eq=False)
        # failed-tests.txt names each failed case; errors.txt keeps its trace.
        tm.that(
            tm.ok(u.Cli.files_read_text(report_dir / "failed-tests.txt")),
            has="test_coverage_failure",
        )
        tm.that(
            tm.ok(u.Cli.files_read_text(report_dir / "errors.txt")),
            has="original coverage suite failure",
        )
        tm.that(
            summary(reports_root),
            has=["failed=1", "accounting_complete=True", f"exit={exit_code}"],
        )
        tm.that(runner.testmon_db.exists(), eq=False)
