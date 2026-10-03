"""Graceful suite stop keeps pytest-testmon progress across bounded runs.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraPytestRunner, c, config, m, t, u
from tests.unit.validate.pytest_runner_support import (
    declare_parallel_project,
    runner_for,
)


class TestsFlextInfraPytestRunnerSuiteStop:
    """Exercise the real runner when the entrypoint budget is already spent."""

    @staticmethod
    def _read(path: Path) -> str:
        """Read one published receipt through the files facade.

        Returns:
            The resulting ``str``.

        """
        return tm.ok(u.Cli.files_read_text(path))

    @staticmethod
    def _spent_runner(project: Path, *, serial: bool = False) -> FlextInfraPytestRunner:
        """Build the real runner whose derived stop instant has already passed.

        The entrypoint clock is placed so pytest stops dispatch at a durable
        testmon batch checkpoint, never through the deadline SIGTERM. The
        reserve matches the runner's own serial decision for the selection.

        Returns:
            The resulting ``FlextInfraPytestRunner``.

        """
        cache = config.Infra.codegen.make.testmon_cache
        policy = config.Infra.tooling.tools.pytest
        testmon_db = project.parent / ".testmon-cache" / cache.database_filename
        testmon_db.parent.mkdir(parents=True)
        runner = FlextInfraPytestRunner(
            repository_root=project,
            started_at_monotonic=time.monotonic(),
            target=cache.target_directory,
            reports=cache.reports_directory,
            testmon_db=testmon_db,
        )
        reserve = (
            policy.serial_suite_stop_reserve_seconds
            if serial or runner.parallel_worker_budget(policy) <= 1
            else policy.suite_stop_reserve_seconds
        )
        return runner.model_copy(
            update={
                "started_at_monotonic": time.monotonic()
                - policy.run_timeout_seconds
                + reserve,
            },
        )

    def _published_run(
        self,
        project: Path,
        *,
        expected_raw_exit: pytest.ExitCode,
    ) -> tuple[Path, t.StrTuple, int]:
        """Return the published run, its selection and its executed count.

        Returns:
            The published run, its selection and its executed count.

        """
        reports = config.Infra.codegen.make.testmon_cache.reports_directory
        (bounded,) = (path.parent for path in (project / reports).glob("*/summary.txt"))
        outcome = m.Cli.ProcessOutcome.model_validate_json(
            self._read(bounded / "suite-outcome.json"),
        )
        tm.that(outcome.raw_return_code, eq=expected_raw_exit.value)
        tm.that(outcome.timed_out, eq=False)
        tm.that(outcome.forwarded_signal, none=True)
        selected = m.Infra.PytestCollectionManifest.model_validate_json(
            self._read(bounded / "testmon-selection.json"),
        ).node_ids
        executed = m.Infra.TestmonRunAccounting.model_validate_json(
            self._read(bounded / "run-accounting.json"),
        ).executed_count
        return bounded, selected, executed

    @staticmethod
    def test_stop_reserve_matches_the_runner_dispatch_decision(
        cached_runner_project: Path,
    ) -> None:
        """The typed reserve follows the same serial decision as the workers.

        The reserve follows the actual worker budget. A one-worker selection
        executes serially and keeps only one in-flight item.
        """
        policy = config.Infra.tooling.tools.pytest

        def dispatch_plan(node_ids: t.StrSequence) -> m.Infra.PytestSelectionPlan:
            """Synthetic selection whose manifest path matches the real argv.

            Returns:
                The resulting ``m.Infra.PytestSelectionPlan``.

            """
            # The plan is a strict value: it takes typed fields, never the
            # JSON-shaped str/list a lax validation would coerce.
            return m.Infra.PytestSelectionPlan(
                manifest_path=Path("m.json"),
                node_ids=tuple(node_ids),
                whole_target=False,
                inventory_collected=False,
                owns_no_tests=False,
            )

        declare_parallel_project(cached_runner_project)
        multi = [f"tests/test_serial_{'x' * index}.py::test_one" for index in range(4)]
        runner = runner_for(cached_runner_project)
        multi_plan = dispatch_plan(multi)
        multi_command = runner.build_command(
            cached_runner_project / runner.reports,
            multi_plan,
        )
        serial_plan = dispatch_plan(multi[:1])
        serial_command = runner.build_command(
            cached_runner_project / runner.reports,
            serial_plan,
        )

        def stop_value(command: t.StrSequence) -> float:
            (raw,) = (
                argument
                for argument in command
                if argument.startswith(c.Infra.PYTEST_SUITE_STOP_OPTION)
            )
            return float(raw.partition("=")[2])

        workers_index = list(multi_command).index("-n") + 1
        budget = runner.parallel_worker_budget(policy)
        tm.that(budget > 1, eq=True)
        tm.that(list(multi_command)[workers_index], eq=str(min(budget, len(multi))))
        tm.that(
            stop_value(multi_command),
            eq=runner.started_at_monotonic
            + runner.run_timeout_seconds(policy)
            - policy.suite_stop_reserve_seconds,
        )
        serial_workers_index = list(serial_command).index("-n") + 1
        tm.that(list(serial_command)[serial_workers_index], eq="0")
        tm.that(
            stop_value(serial_command),
            eq=runner.started_at_monotonic
            + runner.run_timeout_seconds(policy)
            - policy.serial_suite_stop_reserve_seconds,
        )

    @pytest.mark.slow
    def test_suite_stop_instant_persists_the_executed_prefix(
        self,
        cached_runner_project: Path,
    ) -> None:
        """A run reaching its stop instant ends itself and testmon keeps progress.

        pytest must report a red incomplete run, and the testmon database must
        hold every executed test, so the next selection excludes them.
        """
        target = config.Infra.codegen.make.testmon_cache.target_directory
        (cached_runner_project / target / "test_budget.py").write_text(
            "from runner_sample import answer\n\n"
            + "".join(
                f"def test_budget_{index}() -> None:\n    assert answer() == 42\n\n"
                for index in range(260)
            ),
            encoding="utf-8",
        )
        runner = self._spent_runner(cached_runner_project)

        tm.that(tm.ok(runner.execute()), eq=pytest.ExitCode.INTERRUPTED.value)

        bounded, selected, executed = self._published_run(
            cached_runner_project,
            expected_raw_exit=pytest.ExitCode.INTERRUPTED,
        )
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

        # pytest-testmon's durable record is what the next selection excludes:
        # collected-but-unexecuted tests keep a row without a measured duration.
        with closing(
            sqlite3.connect(f"file:{runner.testmon_db}?mode=ro", uri=True),
        ) as connection:
            persisted = {
                name
                for (name,) in connection.execute(
                    "SELECT test_name FROM test_execution"
                    " WHERE failed = 0 AND duration IS NOT NULL",
                )
            }
        tm.that(len(persisted), eq=executed)
        tm.that(persisted <= set(selected), eq=True)

    @pytest.mark.slow
    def test_stop_instant_after_the_last_selected_test_completes_the_run(
        self,
        cached_runner_project: Path,
    ) -> None:
        """A stop requested on the last selected test's teardown ends nothing.

        The fixture project owns one test, so the serial dispatch applies and
        the stop request lands after the whole selection executed and passed:
        the accounting is complete and the run is green although pytest still
        reports its interrupt.
        """
        runner = self._spent_runner(cached_runner_project, serial=True)

        tm.that(tm.ok(runner.execute()), eq=pytest.ExitCode.OK.value)

        bounded, selected, executed = self._published_run(
            cached_runner_project,
            expected_raw_exit=pytest.ExitCode.OK,
        )
        tm.that(executed, eq=len(selected))
        tm.that(
            self._read(bounded / "summary.txt"),
            has=[
                "outcome=executed",
                f"selected={len(selected)}",
                f"executed={executed}",
                "accounting_complete=True",
                "failed=0",
                "exit=0",
            ],
        )
