"""Zero-test projects run to a typed green receipt instead of rc=5 (6n6u)."""

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
        """
        project_root = tmp_path / "zero_test_project"
        cache = config.Infra.codegen.make.testmon_cache
        package_root = project_root / c.Infra.DEFAULT_SRC_DIR / "zero_sample"
        package_root.mkdir(parents=True)
        (project_root / cache.target_directory).mkdir(exist_ok=True)
        (project_root / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            f'pythonpath = ["{c.Infra.DEFAULT_SRC_DIR}"]\n',
            encoding="utf-8",
        )
        (package_root / "__init__.py").write_text(
            "VALUE = 41\n", encoding="utf-8"
        )
        return project_root

    @staticmethod
    def _runner(project_root: Path, tmp_path: Path) -> FlextInfraPytestRunner:
        """Build the public runner exactly as the make verbs do."""
        cache = config.Infra.codegen.make.testmon_cache
        testmon_db = tmp_path / ".testmon-cache" / cache.database_filename
        testmon_db.parent.mkdir(parents=True, exist_ok=True)
        return FlextInfraPytestRunner(
            repository_root=project_root,
            started_at_monotonic=time.monotonic(),
            target=cache.target_directory,
            reports=cache.reports_directory,
            testmon_db=testmon_db,
            apply_changes=True,
        )

    def test_owns_no_tests_reads_the_project_roots(self, tmp_path: Path) -> None:
        """The detection is project-rooted: no test module means True."""
        project = self._zero_test_project(tmp_path)
        runner = self._runner(project, tmp_path)
        tm.that(runner._owns_no_tests(), eq=True)
        tests_root = project / config.Infra.codegen.make.testmon_cache.target_directory
        tests_root.mkdir(exist_ok=True)
        (tests_root / "test_present.py").write_text(
            "def test_present() -> None:\n    assert 41 == 41\n",
            encoding="utf-8",
        )
        tm.that(runner._owns_no_tests(), eq=False)

    @pytest.mark.slow
    def test_incremental_run_publishes_receipt_for_zero_test_project(
        self, tmp_path: Path
    ) -> None:
        """make test on a zero-test project exits 0 with typed accounting."""
        project = self._zero_test_project(tmp_path)
        runner = self._runner(project, tmp_path)

        outcome = tm.ok(runner.execute())

        tm.that(outcome, eq=pytest.ExitCode.OK.value)
        cache = config.Infra.codegen.make.testmon_cache
        reports_root = project / cache.reports_directory
        summary = self._latest_summary(reports_root)
        accounting = m.Infra.TestmonRunAccounting.model_validate_json(
            self._read(summary.parent / "run-accounting.json")
        )
        tm.that(accounting.executed_count, eq=0)
        plan = m.Infra.PytestSelectionPlan.model_validate_json(
            self._read(summary.parent / "selection-plan.json")
        )
        tm.that(plan.owns_no_tests, eq=True)

    @pytest.mark.slow
    def test_full_run_publishes_receipt_for_zero_test_project(
        self, tmp_path: Path
    ) -> None:
        """make test-full on a zero-test project exits 0 with typed accounting."""
        project = self._zero_test_project(tmp_path)
        runner = self._runner(project, tmp_path)

        outcome = tm.ok(runner.execute_full())

        tm.that(outcome, eq=pytest.ExitCode.OK.value)
        cache = config.Infra.codegen.make.testmon_cache
        reports_root = project / cache.reports_directory
        summary = self._latest_summary(reports_root)
        plan = m.Infra.PytestSelectionPlan.model_validate_json(
            self._read(summary.parent / "selection-plan.json")
        )
        tm.that(plan.owns_no_tests, eq=True)
        accounting = m.Infra.TestmonRunAccounting.model_validate_json(
            self._read(summary.parent / "run-accounting.json")
        )
        tm.that(accounting.executed_count, eq=0)

    @staticmethod
    def _read(path: Path) -> str:
        """Read one published receipt through the files facade."""
        return tm.ok(u.Cli.files_read_text(path))

    @staticmethod
    def _latest_summary(reports_root: Path) -> Path:
        """Return the newest bounded report directory's summary receipt."""
        summaries = sorted(
            reports_root.glob("*/summary.txt"), key=lambda path: path.stat().st_mtime
        )
        return summaries[-1]
