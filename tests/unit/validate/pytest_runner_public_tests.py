"""Observable public cached-pytest runtime contract."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraPytestRunner, c, config, m, u


class TestsFlextInfraPytestRunner:
    """Exercise the real pytest, testmon, coverage, and report lifecycle."""

    @pytest.mark.parametrize("ci_context", [True, False])
    def test_marker_selection_is_shared_by_collection_execution_and_coverage(
        self, cached_runner_project: Path, *, ci_context: bool
    ) -> None:
        """CI/pre-commit omit slow cases; local/pre-push keep them selectable."""
        runner = self._runner_for(cached_runner_project, ci_context=ci_context)
        report = (
            cached_runner_project
            / config.Infra.codegen.make.testmon_cache.reports_directory
        )
        expressions = []
        for command in (
            runner.build_selection_command(),
            runner.build_selection_command(complete=True),
            runner.build_command(report),
            runner.build_coverage_command(report),
        ):
            marker_index = command.index("-m", 3)
            expressions.append(command[marker_index + 1])
        assert len(set(expressions)) == 1
        for marker in config.Infra.tooling.tools.pytest.ci_excluded_markers:
            assert (marker in expressions[0]) == ci_context
        for marker in config.Infra.tooling.tools.pytest.external_gate_markers:
            assert marker in expressions[0]

    def test_testmon_commands_name_the_toolchain_environment(
        self, cached_runner_project: Path
    ) -> None:
        """Every testmon argv names one stable toolchain-fingerprinted env."""
        runner = self._runner_for(cached_runner_project)
        report = (
            cached_runner_project
            / config.Infra.codegen.make.testmon_cache.reports_directory
        )
        suite_command = runner.build_command(report)
        names = []
        for command in (
            runner.build_selection_command(),
            runner.build_selection_command(complete=True),
            suite_command,
        ):
            env_index = command.index("--testmon-env")
            names.append(command[env_index + 1])
        assert len(set(names)) == 1
        (name,) = {name.strip("'") for name in names}
        assert name.startswith("toolchain-")
        assert len(name) == len("toolchain-") + 12
        # The coverage verb owns no testmon plugin, so it never names one.
        assert "--testmon-env" not in runner.build_coverage_command(report)
        # Rebuilding any argv reuses the same cached fingerprint.
        assert (
            runner.build_command(report)[suite_command.index("--testmon-env") + 1]
            == names[-1]
        )

    @staticmethod
    def _runner_for(
        cached_runner_project: Path, *, ci_context: bool = False
    ) -> FlextInfraPytestRunner:
        """Bind one runner to the fixture project's canonical cache paths."""
        codegen = config.Infra.codegen
        cache = codegen.make.testmon_cache
        testmon_db = (
            cached_runner_project.parent
            / codegen.toolchain.state_directory_name
            / cached_runner_project.name
            / cache.namespace
            / cache.database_filename
        )
        return FlextInfraPytestRunner(
            repository_root=cached_runner_project,
            ci_context=ci_context,
            started_at_monotonic=time.monotonic(),
            target=cache.target_directory,
            reports=cache.reports_directory,
            testmon_db=testmon_db,
        )

    @staticmethod
    def _summary(reports_root: Path) -> str:
        """Read the latest report summary through the files facade."""
        latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        return tm.ok(u.Cli.files_read_text(reports_root / latest_name / "summary.txt"))

    @pytest.mark.slow
    def test_complete_suite_persists_cache_and_zero_diagnostic_evidence(
        self, cached_runner_project: Path
    ) -> None:
        """One public execution collects every test and publishes real evidence."""
        codegen = config.Infra.codegen
        cache = codegen.make.testmon_cache
        testmon_db = (
            cached_runner_project.parent
            / codegen.toolchain.state_directory_name
            / cached_runner_project.name
            / cache.namespace
            / cache.database_filename
        )
        runner = self._runner_for(cached_runner_project)

        exit_code = tm.ok(runner.execute())

        tm.that(exit_code, eq=0)
        tm.that(testmon_db.is_file(), eq=True)
        reports_root = cached_runner_project / cache.reports_directory
        latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        summary = tm.ok(
            u.Cli.files_read_text(reports_root / latest_name / "summary.txt")
        )
        tm.that(
            summary,
            has=[
                "executed=1",
                "failed=0",
                "errors=0",
                "warnings=0",
                "skipped=0",
                "exit=0",
            ],
        )
        tm.that((reports_root / latest_name / "junit.xml").is_file(), eq=True)
        # The testmon verb owns no coverage plugin (testmon 2.x refuses branch
        # coverage through the cov plugin), so its command carries --no-cov and
        # the coverage artifact belongs to the coverage verb alone.
        selection = tm.ok(
            u.Cli.files_read_text(reports_root / latest_name / "testmon-selection.txt")
        )
        command = tm.ok(
            u.Cli.files_read_text(reports_root / latest_name / "command.txt")
        )
        for node_id in (line for line in selection.splitlines() if line):
            tm.that(command, has=node_id)
        tm.that(command, has="--no-cov")
        tm.that(command, has="--testmon --testmon-noselect")
        tm.that((reports_root / latest_name / "coverage.xml").is_file(), eq=False)

        second_exit = tm.ok(self._runner_for(cached_runner_project).execute())
        tm.that(second_exit, eq=0)
        second_summary = self._summary(reports_root)
        tm.that(
            second_summary,
            has=[
                "result=cache_hit",
                "executed=0",
                "deselected=1",
                "cache_restored=True",
                "exit=0",
            ],
        )
        second_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        cached = m.Infra.TestmonRunAccounting.model_validate_json(
            tm.ok(u.Cli.files_read_text(reports_root / second_name / "accounting.json"))
        )
        assert cached.cache_hit
        assert cached.inventory == cached.deselected
        assert not cached.selected
        assert not cached.executed
        assert not (reports_root / second_name / "junit.xml").exists()

        (cached_runner_project / cache.target_directory / "test_added.py").write_text(
            "def test_added() -> None:\n    assert 1 + 1 == 2\n", encoding="utf-8"
        )
        assert tm.ok(self._runner_for(cached_runner_project).execute()) == 0
        incremental_name = tm.ok(
            u.Cli.files_read_text(reports_root / "latest.txt")
        ).strip()
        incremental = m.Infra.TestmonRunAccounting.model_validate_json(
            tm.ok(
                u.Cli.files_read_text(
                    reports_root / incremental_name / "accounting.json"
                )
            )
        )
        assert incremental.executed_count == 1
        assert incremental.deselected == cached.inventory
        assert set(incremental.inventory) == set(incremental.selected) | set(
            incremental.deselected
        )

        assert tm.ok(self._runner_for(cached_runner_project).execute_full()) == 0
        full_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        full = m.Infra.TestmonRunAccounting.model_validate_json(
            tm.ok(u.Cli.files_read_text(reports_root / full_name / "accounting.json"))
        )
        assert full.mode == "full"
        assert not full.cache_hit
        assert set(full.executed) == set(incremental.inventory)
        assert full.database == cached.database
        assert not full.deselected
        assert (reports_root / full_name / "cache-before.json").is_file()
        assert (reports_root / full_name / "cache-after.json").is_file()

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "category", ["UserWarning", "MroViolation", "SmellViolation"]
    )
    def test_native_warning_events_remain_visible_and_policy_suspension_is_bounded(
        self, cached_runner_project: Path, category: str
    ) -> None:
        """One multiline native warning is one event, with a bounded policy decision."""
        cache = config.Infra.codegen.make.testmon_cache
        warning_class = category if category == "UserWarning" else f"e.{category}"
        (cached_runner_project / cache.target_directory / "test_warning.py").write_text(
            "import warnings\nfrom flext_core import e\n\n"
            "def test_warning() -> None:\n"
            f"    warnings.warn('first line\\nsecond line', {warning_class}, stacklevel=1)\n",
            encoding="utf-8",
        )
        exit_code = tm.ok(self._runner_for(cached_runner_project).execute())
        suspended = (
            category != "UserWarning"
            and config.Infra.codegen.make.policy_check_suspension_reason is not None
        )
        assert (exit_code == 0) == suspended
        reports = cached_runner_project / cache.reports_directory
        latest = tm.ok(u.Cli.files_read_text(reports / "latest.txt")).strip()
        summary = self._summary(reports)
        assert "warnings=1\n" in summary
        assert f"suspended_policy_warnings={int(suspended)}\n" in summary
        warnings = tm.ok(u.Cli.files_read_text(reports / latest / "warnings.txt"))
        assert "first line\nsecond line" in warnings

    @pytest.mark.slow
    def test_setup_failure_is_accounted_without_a_call_phase(
        self, cached_runner_project: Path
    ) -> None:
        """A failed fixture accounts for its selected node and preserves later outcomes."""
        cache = config.Infra.codegen.make.testmon_cache
        (cached_runner_project / cache.target_directory / "test_setup.py").write_text(
            "import pytest\n\n@pytest.fixture\ndef broken():\n"
            "    raise RuntimeError('setup failure evidence')\n\n"
            "def test_setup(broken):\n    assert broken\n",
            encoding="utf-8",
        )
        assert tm.ok(self._runner_for(cached_runner_project).execute()) != 0
        reports = cached_runner_project / cache.reports_directory
        latest = tm.ok(u.Cli.files_read_text(reports / "latest.txt")).strip()
        accounting = m.Infra.TestmonRunAccounting.model_validate_json(
            tm.ok(u.Cli.files_read_text(reports / latest / "accounting.json"))
        )
        assert set(accounting.selected) == set(accounting.executed)
        assert accounting.executed_count == 2
        assert "setup failure evidence" in tm.ok(
            u.Cli.files_read_text(reports / latest / "errors.txt")
        )

    @pytest.mark.slow
    def test_failed_cases_do_not_stop_remaining_cases(
        self, cached_runner_project: Path
    ) -> None:
        """Retain all failures and later outcomes in one persistent-cache run."""
        cache = config.Infra.codegen.make.testmon_cache
        (
            cached_runner_project / cache.target_directory / "test_failures.py"
        ).write_text(
            "def test_first_failure() -> None:\n"
            "    assert False, 'first failure evidence'\n\n"
            "def test_second_failure() -> None:\n"
            "    assert False, 'second failure evidence'\n",
            encoding="utf-8",
        )

        exit_code = tm.ok(self._runner_for(cached_runner_project).execute())

        tm.that(exit_code, ne=0)
        reports_root = cached_runner_project / cache.reports_directory
        (report_path,) = reports_root.glob("*/junit.xml")
        report = tm.ok(u.Cli.files_read_text(report_path))
        tm.that(
            report,
            has=[
                'tests="3"',
                'failures="2"',
                'errors="0"',
                'skipped="0"',
                'name="test_runtime"',
                "first failure evidence",
                "second failure evidence",
            ],
        )
        outcome = m.Cli.ProcessOutcome.model_validate_json(
            tm.ok(u.Cli.files_read_text(report_path.parent / "suite-outcome.json"))
        )
        tm.that(outcome.raw_return_code, eq=exit_code)
        tm.that(outcome.timed_out, eq=False)
        tm.that(outcome.forwarded_signal, none=True)
        tm.that(self._summary(reports_root), has=["failed=2", "exit=1"])
        events = tm.ok(u.Cli.files_read_text(report_path.parent / "events.jsonl"))
        tm.that(events, has=["first failure evidence", "second failure evidence"])

    @pytest.mark.slow
    def test_external_gate_markers_are_not_executed_offline(
        self, cached_runner_project: Path
    ) -> None:
        """An external-token gate is deselected, never a KeyError, and reported.

        gate-budget/engineering-core: offline verification never runs a gate
        whose environment only a direct invocation provides. The marker set is
        the SSOT ``external-gate-markers``; every expectation derives from it.
        """
        pytest_policy = config.Infra.tooling.tools.pytest
        markers = pytest_policy.external_gate_markers
        cache = config.Infra.codegen.make.testmon_cache
        marker_lines = "".join(
            f'  "{marker}",\n' for marker in pytest_policy.standard_markers
        )
        (cached_runner_project / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            f'pythonpath = ["{c.Infra.DEFAULT_SRC_DIR}"]\n'
            f"markers = [\n{marker_lines}]\n",
            encoding="utf-8",
        )
        (
            cached_runner_project / cache.target_directory / "test_external.py"
        ).write_text(
            "import os\n\nimport pytest\n\n\n"
            f"@pytest.mark.{markers[0]}\n"
            "def test_needs_external_environment() -> None:\n"
            '    os.environ["RUNNER_SAMPLE_EXTERNAL_TOKEN"]\n',
            encoding="utf-8",
        )

        exit_code = tm.ok(self._runner_for(cached_runner_project).execute())

        tm.that(exit_code, eq=0)
        reports_root = cached_runner_project / cache.reports_directory
        latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        tm.that(
            self._summary(reports_root),
            has=[
                "executed=1",
                f"not_executed_external_gates={','.join(markers)}",
                "failed=0",
                "errors=0",
                "exit=0",
            ],
        )
        command = tm.ok(
            u.Cli.files_read_text(reports_root / latest_name / "command.txt")
        )
        tm.that(command, has=pytest_policy.external_gate_deselection)

    @pytest.mark.slow
    def test_coverage_verb_publishes_artifact_without_testmon(
        self, cached_runner_project: Path
    ) -> None:
        """The coverage pass runs its own process: real artifact, zero testmon."""
        codegen = config.Infra.codegen
        cache = codegen.make.testmon_cache
        reports_root = cached_runner_project / cache.reports_directory
        runner = self._runner_for(cached_runner_project)

        exit_code = tm.ok(runner.execute_coverage())

        tm.that(exit_code, eq=0)
        latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        coverage = reports_root / latest_name / "coverage.xml"
        tm.that(coverage.is_file(), eq=True)
        tm.that(coverage.stat().st_size > 0, eq=True)
        summary = self._summary(reports_root)
        tm.that(summary, has=["executed=1", "failed=0", "exit=0"])
        command = tm.ok(
            u.Cli.files_read_text(reports_root / latest_name / "command.txt")
        )
        tm.that(command, has="--cov")
        tm.that("--testmon" in command, eq=False)

    @pytest.mark.slow
    def test_collection_skip_blocks_full_execution_and_incremental_cache_hit(
        self, cached_runner_project: Path
    ) -> None:
        """A skipped module cannot disappear when execution receives explicit node ids."""
        cache = config.Infra.codegen.make.testmon_cache
        (
            cached_runner_project / cache.target_directory / "test_collection_skip.py"
        ).write_text(
            "import pytest\n"
            "pytest.skip('original collection skip reason', allow_module_level=True)\n",
            encoding="utf-8",
        )
        reports = cached_runner_project / cache.reports_directory
        for complete in (True, False):
            runner = self._runner_for(cached_runner_project)
            exit_code = tm.ok(runner.execute_full() if complete else runner.execute())
            assert exit_code != 0
            latest = tm.ok(u.Cli.files_read_text(reports / "latest.txt")).strip()
            report = reports / latest
            skips = tm.ok(u.Cli.files_read_text(report / "skipped-tests.txt"))
            assert "original collection skip reason" in skips
            assert "inventory-events.jsonl" in skips
            accounting = m.Infra.TestmonRunAccounting.model_validate_json(
                tm.ok(u.Cli.files_read_text(report / "accounting.json"))
            )
            assert accounting.cache_hit == (not complete)
            assert "collection_skipped=0\n" not in self._summary(reports)

    @pytest.mark.slow
    def test_failed_coverage_suite_preserves_original_failure_and_accounting(
        self, cached_runner_project: Path
    ) -> None:
        """No-cov-on-fail omits coverage without hiding the failed test evidence."""
        cache = config.Infra.codegen.make.testmon_cache
        (
            cached_runner_project / cache.target_directory / "test_coverage_failure.py"
        ).write_text(
            "def test_coverage_failure() -> None:\n"
            "    assert False, 'original coverage suite failure'\n",
            encoding="utf-8",
        )

        exit_code = tm.ok(self._runner_for(cached_runner_project).execute_coverage())

        assert exit_code == pytest.ExitCode.TESTS_FAILED
        reports = cached_runner_project / cache.reports_directory
        latest = tm.ok(u.Cli.files_read_text(reports / "latest.txt")).strip()
        report = reports / latest
        accounting = m.Infra.TestmonRunAccounting.model_validate_json(
            tm.ok(u.Cli.files_read_text(report / "accounting.json"))
        )
        outcome = m.Cli.ProcessOutcome.model_validate_json(
            tm.ok(u.Cli.files_read_text(report / "suite-outcome.json"))
        )
        assert accounting.mode == "coverage"
        assert set(accounting.executed) == set(accounting.selected)
        assert accounting.executed_count == len(accounting.inventory) == 2
        assert outcome.raw_return_code == exit_code
        assert not outcome.timed_out
        assert outcome.forwarded_signal is None
        assert not (report / "coverage.xml").exists()
        assert "original coverage suite failure" in tm.ok(
            u.Cli.files_read_text(report / "failed-tests.txt")
        )
        assert "original coverage suite failure" in tm.ok(
            u.Cli.files_read_text(report / "pytest.log")
        )
        assert "failed=1\n" in self._summary(reports)

    @pytest.mark.slow
    def test_collection_policy_error_fails_loud_and_names_the_offender(
        self, policy_violation_project: Path
    ) -> None:
        """A collection-time policy error rejects the run and names the offender."""
        runner = self._runner_for(policy_violation_project)

        with pytest.raises(RuntimeError) as raised:
            runner.execute()

        tm.that(str(raised.value), has=["FLEXT slow timeout policy", "test_policy.py"])

    @pytest.mark.slow
    def test_coverage_pass_fails_loud_on_collection_policy_error(
        self, policy_violation_project: Path
    ) -> None:
        """The coverage pass also exits non-zero on the same policy violation."""
        runner = self._runner_for(policy_violation_project)

        with pytest.raises(RuntimeError, match="FLEXT slow timeout policy"):
            runner.execute_coverage()


__all__: list[str] = []
