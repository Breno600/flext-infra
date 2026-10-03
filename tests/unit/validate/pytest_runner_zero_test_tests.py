"""Zero-test projects run to a typed green receipt instead of rc=5 (6n6u).

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraPytestRunner, c, config, m, u


class TestsFlextInfraPytestRunnerZeroTest:
    """A project whose config-owned roots own no test module is a receipt, not red.

    The invest workspace shell is the real consumer: its root collects zero
    tests by declared design, and every fresh checkout used to die with
    ``pytest executed zero tests`` / ``empty incremental selection`` before
    the contract existed (bead invest-6n6u).
    """

    @staticmethod
    def _zero_test_project(tmp_path: Path) -> Path:
        """Build a real consumer project that owns no test module at all.

        The tracked tests root exists (the fleet scaffold materializes it and
        the invest root carries ``tests/fixtures``), but it holds no
        ``test_*.py``/``*_test.py`` module — an empty suite by design.

        Returns:
            The resulting ``Path``.

        """
        project_root = tmp_path / "zero_test_project"
        cache = config.Infra.codegen.make.testmon_cache
        package_root = project_root / c.Infra.DEFAULT_SRC_DIR / "zero_sample"
        package_root.mkdir(parents=True)
        (project_root / cache.target_directory).mkdir(exist_ok=True)
        (project_root / "pyproject.toml").write_text(
            f'[tool.pytest.ini_options]\npythonpath = ["{c.Infra.DEFAULT_SRC_DIR}"]\n',
            encoding="utf-8",
        )
        (package_root / "__init__.py").write_text("VALUE = 41\n", encoding="utf-8")
        return project_root

    @staticmethod
    def _runner(
        project_root: Path,
        tmp_path: Path,
        *,
        slow_phase: bool = False,
        elapsed_seconds: float = 0.0,
    ) -> FlextInfraPytestRunner:
        """Build the public runner exactly as the make verbs do.

        Returns:
            The resulting ``FlextInfraPytestRunner``.

        """
        cache = config.Infra.codegen.make.testmon_cache
        testmon_db = tmp_path / ".testmon-cache" / cache.database_filename
        testmon_db.parent.mkdir(parents=True, exist_ok=True)
        return FlextInfraPytestRunner(
            repository_root=project_root,
            started_at_monotonic=time.monotonic() - elapsed_seconds,
            target=cache.target_directory,
            reports=cache.reports_directory,
            testmon_db=testmon_db,
            apply_changes=True,
            slow_phase=slow_phase,
        )

    @pytest.mark.slow
    def test_plural_module_form_still_owns_its_tests(
        self,
        tmp_path: Path,
    ) -> None:
        """A ``*_tests.py``-only suite owns tests: the SSOT patterns decide.

        The module patterns come from the pytest ``python-files`` SSOT; a
        hardcoded copy that omitted the plural form answered "owns no tests"
        for a live suite, and the accounting then rejected a fully green
        run (selected=0 vs executed=N, exit 1 on a cold checkout).
        """
        project_root = self._zero_test_project(tmp_path)
        cache = config.Infra.codegen.make.testmon_cache
        module = project_root / cache.target_directory / "sample_suite_tests.py"
        module.write_text(
            "def test_value() -> None:\n    from zero_sample import VALUE\n"
            "    tm_value = VALUE == 41\n    assert tm_value\n",
            encoding="utf-8",
        )
        outcome = tm.ok(self._runner(project_root, tmp_path).execute())

        tm.that(outcome, eq=pytest.ExitCode.OK.value)
        summary = self._latest_summary(project_root / cache.reports_directory)
        plan = m.Infra.PytestSelectionPlan.model_validate_json(
            self._read(summary.parent / "selection-plan.json"),
        )
        tm.that(plan.owns_no_tests, eq=False)

    def test_held_testmon_database_lease_refuses_a_concurrent_run(
        self,
        tmp_path: Path,
    ) -> None:
        """A second run on one shared database fails loud before any effect."""
        project = self._zero_test_project(tmp_path)
        runner = self._runner(
            project,
            tmp_path,
            elapsed_seconds=config.Infra.tooling.tools.pytest.run_timeout_seconds,
        )

        with (
            u.Infra.codegen_transaction_lease(runner.testmon_db),
            pytest.raises(TimeoutError, match="held elsewhere"),
        ):
            runner.execute()

        reports_root = (
            project / config.Infra.codegen.make.testmon_cache.reports_directory
        )
        tm.that(list(reports_root.glob("*/run-context.json")), eq=[])

    @pytest.mark.slow
    def test_slow_phase_without_slow_items_publishes_receipt(
        self,
        tmp_path: Path,
    ) -> None:
        """A project whose suite has no slow-marked item closes its slow phase green.

        The budgeted phase executes the suite; the slow phase then owns no
        item in its scope and publishes the typed zero-test receipt.
        """
        project = self._zero_test_project(tmp_path)
        cache = config.Infra.codegen.make.testmon_cache
        (project / cache.target_directory / "test_budgeted.py").write_text(
            "from zero_sample import VALUE\n\n\n"
            "def test_value() -> None:\n    assert VALUE\n",
            encoding="utf-8",
        )
        tm.that(
            tm.ok(self._runner(project, tmp_path).execute()),
            eq=pytest.ExitCode.OK.value,
        )

        outcome = tm.ok(self._runner(project, tmp_path, slow_phase=True).execute())

        tm.that(outcome, eq=pytest.ExitCode.OK.value)
        summary = self._latest_summary(project / cache.reports_directory)
        plan = m.Infra.PytestSelectionPlan.model_validate_json(
            self._read(summary.parent / "selection-plan.json"),
        )
        tm.that(plan.owns_no_tests, eq=True)
        accounting = m.Infra.TestmonRunAccounting.model_validate_json(
            self._read(summary.parent / "run-accounting.json"),
        )
        tm.that(accounting.executed_count, eq=0)

    @pytest.mark.slow
    def test_incremental_run_publishes_receipt_for_zero_test_project(
        self,
        tmp_path: Path,
    ) -> None:
        """Make test on a zero-test project exits 0 with typed accounting."""
        project = self._zero_test_project(tmp_path)
        runner = self._runner(project, tmp_path)

        outcome = tm.ok(runner.execute())

        tm.that(outcome, eq=pytest.ExitCode.OK.value)
        cache = config.Infra.codegen.make.testmon_cache
        reports_root = project / cache.reports_directory
        summary = self._latest_summary(reports_root)
        accounting = m.Infra.TestmonRunAccounting.model_validate_json(
            self._read(summary.parent / "run-accounting.json"),
        )
        tm.that(accounting.executed_count, eq=0)
        plan = m.Infra.PytestSelectionPlan.model_validate_json(
            self._read(summary.parent / "selection-plan.json"),
        )
        tm.that(plan.owns_no_tests, eq=True)

    @pytest.mark.slow
    def test_full_run_publishes_receipt_for_zero_test_project(
        self,
        tmp_path: Path,
    ) -> None:
        """Make test-full on a zero-test project exits 0 with typed accounting."""
        project = self._zero_test_project(tmp_path)
        runner = self._runner(project, tmp_path)

        outcome = tm.ok(runner.execute_full())

        tm.that(outcome, eq=pytest.ExitCode.OK.value)
        cache = config.Infra.codegen.make.testmon_cache
        reports_root = project / cache.reports_directory
        summary = self._latest_summary(reports_root)
        plan = m.Infra.PytestSelectionPlan.model_validate_json(
            self._read(summary.parent / "selection-plan.json"),
        )
        tm.that(plan.owns_no_tests, eq=True)
        accounting = m.Infra.TestmonRunAccounting.model_validate_json(
            self._read(summary.parent / "run-accounting.json"),
        )
        tm.that(accounting.executed_count, eq=0)

    @staticmethod
    def _read(path: Path) -> str:
        """Read one published receipt through the files facade.

        Returns:
            The resulting ``str``.

        """
        return tm.ok(u.Cli.files_read_text(path))

    @staticmethod
    def _latest_summary(reports_root: Path) -> Path:
        """Return the newest bounded report directory's summary receipt.

        Returns:
            The newest bounded report directory's summary receipt.

        """
        summaries = sorted(
            reports_root.glob("*/summary.txt"),
            key=lambda path: path.stat().st_mtime,
        )
        return summaries[-1]
