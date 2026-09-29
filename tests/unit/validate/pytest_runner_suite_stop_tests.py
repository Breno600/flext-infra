"""Graceful suite stop keeps pytest-testmon progress across bounded runs."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraPytestRunner, config, m, u


class TestsFlextInfraPytestRunnerSuiteStop:
    """Exercise the real runner when the entrypoint budget is already spent."""

    @staticmethod
    def _read(path: Path) -> str:
        """Read one published receipt through the files facade."""
        return tm.ok(u.Cli.files_read_text(path))

    @pytest.mark.slow
    def test_suite_stop_instant_persists_the_executed_prefix(
        self, cached_runner_project: Path
    ) -> None:
        """A run reaching its stop instant ends itself and testmon keeps progress.

        The entrypoint clock is placed so the derived stop instant has already
        passed: pytest must stop dispatch gracefully (never the deadline
        SIGTERM), report a red incomplete run, and the next run must select
        only the tests the bounded run did not execute.
        """
        cache = config.Infra.codegen.make.testmon_cache
        policy = config.Infra.tooling.tools.pytest
        (cached_runner_project / cache.target_directory / "test_budget.py").write_text(
            "".join(
                f"def test_budget_{index}() -> None:\n    assert {index} >= 0\n\n"
                for index in range(12)
            ),
            encoding="utf-8",
        )
        testmon_db = (
            cached_runner_project.parent / ".testmon-cache" / cache.database_filename
        )
        testmon_db.parent.mkdir(parents=True)
        spent = policy.run_timeout_seconds - policy.suite_stop_reserve_seconds
        runners = [
            FlextInfraPytestRunner(
                repository_root=cached_runner_project,
                started_at_monotonic=time.monotonic() - elapsed,
                target=cache.target_directory,
                reports=cache.reports_directory,
                testmon_db=testmon_db,
            )
            for elapsed in (spent, 0)
        ]
        reports_root = cached_runner_project / cache.reports_directory

        tm.that(tm.ok(runners[0].execute()), eq=pytest.ExitCode.INTERRUPTED.value)

        (bounded,) = (path.parent for path in reports_root.glob("*/summary.txt"))
        outcome = m.Cli.ProcessOutcome.model_validate_json(
            self._read(bounded / "suite-outcome.json")
        )
        tm.that(outcome.timed_out, eq=False)
        tm.that(outcome.forwarded_signal, none=True)
        selected = m.Infra.PytestCollectionManifest.model_validate_json(
            self._read(bounded / "testmon-selection.json")
        ).node_ids
        executed = m.Infra.TestmonRunAccounting.model_validate_json(
            self._read(bounded / "run-accounting.json")
        ).executed_count
        tm.that(executed, gt=0)
        tm.that(executed, lt=len(selected))
        tm.that(
            self._read(bounded / "summary.txt"),
            has=[
                "outcome=incomplete",
                f"selected={len(selected)}",
                f"executed={executed}",
                "accounting_complete=False",
                "failed=0",
            ],
        )

        tm.that(tm.ok(runners[1].execute()), eq=0)

        (warm,) = (
            path.parent
            for path in reports_root.glob("*/summary.txt")
            if path.parent != bounded
        )
        remaining = m.Infra.PytestCollectionManifest.model_validate_json(
            self._read(warm / "testmon-selection.json")
        ).node_ids
        tm.that(len(remaining), eq=len(selected) - executed)
        tm.that(
            self._read(warm / "summary.txt"),
            has=["outcome=executed", f"executed={len(remaining)}", "exit=0"],
        )
