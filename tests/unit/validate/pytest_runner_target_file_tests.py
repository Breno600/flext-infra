"""Single-file pytest target contract.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from tests.unit.validate.pytest_runner_support import runner_for, summary


@pytest.mark.unit
class TestsFlextInfraPytestTargetFile:
    """A declared file replaces the suite directory as the only node target."""

    @staticmethod
    def test_declared_file_replaces_the_suite_directory(
        cached_runner_project: Path,
    ) -> None:
        """Selection and suite argv both name the declared file."""
        cache = config.Infra.codegen.make.testmon_cache
        relative = Path(cache.target_directory) / "declared_case.py"
        declared = cached_runner_project / relative
        declared.write_text(
            "def test_declared() -> None:\n    return None\n",
            encoding="utf-8",
        )
        runner = runner_for(cached_runner_project, target_file=relative)
        report = cached_runner_project / cache.reports_directory
        suite = runner.build_command(report)
        selection = runner.build_selection_command(
            report_log=report / "selection.jsonl",
            manifest_path=report / "selection.json",
        )
        expected = relative.as_posix()
        tm.that(suite[3], eq=expected)
        tm.that(selection[3], eq=expected)

    @staticmethod
    def test_missing_target_file_fails(cached_runner_project: Path) -> None:
        """An absent declared file fails before pytest starts."""
        outcome = "raised"
        try:
            runner_for(
                cached_runner_project,
                target_file=Path("tests/missing_declared_case.py"),
            )
        except ValueError as exc:
            tm.that("existing file" in str(exc), eq=True)
            outcome = "value-error"
        tm.that(outcome, eq="value-error")

    @staticmethod
    def test_declared_file_execution_never_lets_the_cache_deselect_it(
        cached_runner_project: Path,
    ) -> None:
        """An empty cache selection cannot deselect the declared file.

        A file never run before has no testmon traces, so its selection
        resolves empty; the execution must still run the file (noselect),
        because the declared file is the operator's chosen scope.
        """
        cache = config.Infra.codegen.make.testmon_cache
        relative = Path(cache.target_directory) / "fresh_case.py"
        declared = cached_runner_project / relative
        declared.write_text(
            "def test_fresh() -> None:\n    return None\n",
            encoding="utf-8",
        )
        runner = runner_for(cached_runner_project, target_file=relative)
        report = cached_runner_project / cache.reports_directory
        suite = runner.build_command(report, selection_plan=None)
        argv = " ".join(suite)
        tm.that("--testmon-noselect" in argv, eq=True)
        tm.that("--testmon-forceselect" not in argv, eq=True)
        tm.that(relative.as_posix() in argv, eq=True)

    @staticmethod
    @pytest.mark.slow
    def test_declared_file_rerun_over_a_warm_cache_executes_again(
        cached_runner_project: Path,
    ) -> None:
        """An unchanged declared file reruns green, never as a cache hit."""
        cache = config.Infra.codegen.make.testmon_cache
        relative = Path(cache.target_directory) / "rerun_case.py"
        (cached_runner_project / relative).write_text(
            "def test_rerun() -> None:\n    return None\n",
            encoding="utf-8",
        )
        for _ in range(2):
            runner = runner_for(cached_runner_project, target_file=relative)
            tm.that(tm.ok(runner.execute()), eq=pytest.ExitCode.OK.value)
            report = summary(cached_runner_project / cache.reports_directory)
            tm.that(report, has="executed=1\n")

    @staticmethod
    @pytest.mark.slow
    def test_declared_file_partial_selection_stays_green(
        cached_runner_project: Path,
    ) -> None:
        """A partly selected declared file runs only its selected tests."""
        cache = config.Infra.codegen.make.testmon_cache
        relative = Path(cache.target_directory) / "partial_case.py"
        declared = cached_runner_project / relative
        kept = "def test_kept() -> None:\n    return None\n\n\n"
        for expected, value in ((2, 1), (1, 2)):
            declared.write_text(
                kept + f"def test_edited() -> None:\n    assert {value}\n",
                encoding="utf-8",
            )
            runner = runner_for(cached_runner_project, target_file=relative)
            tm.that(tm.ok(runner.execute()), eq=pytest.ExitCode.OK.value)
            report = summary(cached_runner_project / cache.reports_directory)
            tm.that(report, has=f"executed={expected}\n")
