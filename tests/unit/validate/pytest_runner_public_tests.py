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
            runner.build_inventory_command(),
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
            suite_command,
            runner.build_command(report, ("tests/test_runtime.py::test_runtime",)),
        ):
            assert "--testmon-forceselect" in command
            assert "--testmon-noselect" not in command
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
        tm.that(command, has="--testmon --testmon-forceselect")
        tm.that((reports_root / latest_name / "coverage.xml").is_file(), eq=False)

        cache_identity = testmon_db.stat().st_ino
        second_exit = tm.ok(self._runner_for(cached_runner_project).execute())
        tm.that(second_exit, eq=0)
        tm.that(testmon_db.stat().st_ino, eq=cache_identity)
        second_summary = self._summary(reports_root)
        tm.that(
            second_summary,
            has=["executed=0", "deselected=1", "cache_restored=True", "exit=0"],
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

        exit_code = tm.ok(runner.execute_coverage())

        tm.that(exit_code, ne=0)


__all__: list[str] = []
