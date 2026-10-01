"""Observable public cached-pytest runtime contract."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraPytestDiagExtractor, c, config, m, t, u
from tests.fixtures.pytest_runner import PytestRunnerContract


class TestsFlextInfraPytestRunner(PytestRunnerContract):
    """Exercise the real pytest, testmon, coverage, and report lifecycle."""

    @pytest.mark.parametrize("ci_context", [True, False])
    def test_marker_selection_is_shared_by_collection_execution_and_coverage(
        self, cached_runner_project: Path, *, ci_context: bool
    ) -> None:
        """CI/pre-commit omit slow cases; local/pre-push keep them selectable."""
        runner = self.runner_for(cached_runner_project, ci_context=ci_context)
        report = (
            cached_runner_project
            / config.Infra.codegen.make.testmon_cache.reports_directory
        )
        expressions = []
        for command in (
            runner.build_selection_command(
                report_log=report / "selection.jsonl",
                manifest_path=report / "selection.json",
            ),
            runner.build_selection_command(
                report_log=report / "inventory.jsonl",
                manifest_path=report / "inventory.json",
                complete=True,
            ),
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
        runner = self.runner_for(cached_runner_project)
        report = (
            cached_runner_project
            / config.Infra.codegen.make.testmon_cache.reports_directory
        )
        suite_command = runner.build_command(report)
        names = []
        for command in (
            runner.build_selection_command(
                report_log=report / "selection.jsonl",
                manifest_path=report / "selection.json",
            ),
            runner.build_selection_command(
                report_log=report / "inventory.jsonl",
                manifest_path=report / "inventory.json",
                complete=True,
            ),
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

    @pytest.mark.slow
    def test_config_only_changes_invalidate_the_persistent_cache(
        self, cached_runner_project: Path
    ) -> None:
        """A governed YAML change executes again using the same Testmon database."""
        config_root = cached_runner_project / c.CONFIG_DIR_NAME
        config_root.mkdir()
        source = config_root / "behavior.yaml"
        source.write_text("value: initial\n", encoding="utf-8")
        cache = config.Infra.codegen.make.testmon_cache
        (cached_runner_project / cache.target_directory / "test_runtime.py").write_text(
            "from pathlib import Path\n"
            "from flext_cli import u\n\n"
            "def test_runtime():\n"
            f"    payload = u.Cli.config_load(Path({str(source)!r})).unwrap()\n"
            "    assert payload['value']\n",
            encoding="utf-8",
        )
        runner = self.runner_for(cached_runner_project)
        database = runner.testmon_db
        assert tm.ok(runner.execute()) == 0
        reports = cached_runner_project / runner.reports
        assert "executed=1" in self.summary(reports)
        warm = self.runner_for(cached_runner_project)
        assert tm.ok(warm.execute()) == 0
        assert "outcome=cache_hit" in self.summary(reports)
        warm_latest = (reports / "latest.txt").read_text().strip()
        warm_accounting = m.Infra.TestmonRunAccounting.model_validate_json(
            (reports / warm_latest / "run-accounting.json").read_text()
        )
        assert warm_accounting.cache_restored
        assert warm_accounting.executed_count == 0
        assert warm_accounting.deselected_count == warm_accounting.inventory_count
        source.write_text("value: changed\n", encoding="utf-8")
        changed = self.runner_for(cached_runner_project)
        assert changed.testmon_db == database
        assert tm.ok(changed.execute()) == 0
        assert "executed=1" in self.summary(reports)
        latest = (reports / "latest.txt").read_text().strip()
        accounting = m.Infra.TestmonRunAccounting.model_validate_json(
            (reports / latest / "run-accounting.json").read_text()
        )
        assert accounting.executed_count == accounting.reported_count
        assert (
            accounting.executed_count + accounting.deselected_count
            == accounting.inventory_count
        )

    def test_worker_ceiling_defaults_without_declared_project(
        self, cached_runner_project: Path
    ) -> None:
        """A tree without ``[project].name`` takes the fleet-wide ceiling."""
        policy = config.Infra.tooling.tools.pytest
        runner = self.runner_for(cached_runner_project)
        assert runner.parallel_worker_budget(policy) == policy.parallel_workers
        assert runner.run_timeout_seconds(policy) == policy.run_timeout_seconds

    def test_declared_project_uses_its_configured_run_wall(
        self, cached_runner_project: Path
    ) -> None:
        """The suite argv and process policy share one declared project budget."""
        policy = config.Infra.tooling.tools.pytest
        declared_name = next(iter(policy.run_timeout_overrides), config.Infra.name)
        expected = policy.run_timeout_overrides.get(
            declared_name, policy.run_timeout_seconds
        )
        pyproject = cached_runner_project / "pyproject.toml"
        pyproject.write_text(
            pyproject.read_text(encoding="utf-8")
            + f'\n[project]\nname = "{declared_name}"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        runner = self.runner_for(cached_runner_project)
        report = (
            cached_runner_project
            / config.Infra.codegen.make.testmon_cache.reports_directory
        )

        assert runner.run_timeout_seconds(policy) == expected
        command = runner.build_command(report)
        stop = next(
            item for item in command if item.startswith(c.Infra.PYTEST_SUITE_STOP_OPTION)
        )
        assert float(stop.partition("=")[2]) == (
            runner.started_at_monotonic
            + expected
            - policy.suite_stop_reserve_seconds
        )

    def test_worker_ceiling_follows_the_declared_project_override(
        self, cached_runner_project: Path
    ) -> None:
        """The runner resolves the declared project's override from the SSOT."""
        policy = config.Infra.tooling.tools.pytest
        assert policy.parallel_worker_overrides
        declared_name = next(iter(policy.parallel_worker_overrides))
        pyproject = cached_runner_project / "pyproject.toml"
        pyproject.write_text(
            pyproject.read_text(encoding="utf-8")
            + f'\n[project]\nname = "{declared_name}"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        runner = self.runner_for(cached_runner_project)
        report = (
            cached_runner_project
            / config.Infra.codegen.make.testmon_cache.reports_directory
        )
        declared_ceiling = policy.parallel_worker_overrides[declared_name]
        expected_workers = runner.resolve_worker_ceiling(
            declared_ceiling, os.process_cpu_count()
        )
        budget = runner.parallel_worker_budget(policy)
        assert budget == expected_workers
        command = runner.build_command(report)
        workers = command[command.index("-n") + 1]
        assert workers == str(budget)

    @pytest.mark.slow
    def test_complete_suite_persists_cache_and_zero_diagnostic_evidence(
        self, cached_runner_project: Path
    ) -> None:
        """One public execution collects every test and publishes real evidence."""
        cache = config.Infra.codegen.make.testmon_cache
        runner = self.runner_for(cached_runner_project)
        testmon_db = runner.testmon_db

        exit_code = tm.ok(runner.execute())

        tm.that(exit_code, eq=0)
        tm.that(testmon_db.is_file(), eq=True)
        tm.that(testmon_db.is_relative_to(cached_runner_project), eq=False)
        tm.that((cached_runner_project / cache.database_filename).exists(), eq=False)
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
        # A complete selection runs the whole target; the collection plugin
        # enforces exactly the selected node ids in the recorded order.
        tm.that(selection.splitlines(), has="tests/test_runtime.py::test_runtime")
        tm.that(command, has=c.Infra.PYTEST_SELECTED_COLLECTION_OPTION)
        tm.that(command, has="--no-cov")
        tm.that(command, has="--testmon --testmon-noselect")
        tm.that((reports_root / latest_name / "coverage.xml").is_file(), eq=False)
        # A cold run has no database to inspect before pytest; its only cache
        # receipt is the post-run seed decision.
        tm.that((reports_root / latest_name / "cache-before.json").exists(), eq=False)
        seeded = m.Infra.TestmonCacheState.model_validate_json(
            tm.ok(
                u.Cli.files_read_text(reports_root / latest_name / "cache-after.json")
            )
        )
        tm.that(seeded.seed_needed, eq=True)
        tm.that(seeded.saveable, eq=True)

    def _seed_cache(self, cached_runner_project: Path) -> Path:
        """Seed the persistent cache through one public cold run."""
        tm.that(tm.ok(self.runner_for(cached_runner_project).execute()), eq=0)
        return (
            cached_runner_project
            / config.Infra.codegen.make.testmon_cache.reports_directory
        )

    @pytest.mark.slow
    def test_warm_cache_deselects_the_unchanged_suite(
        self, cached_runner_project: Path
    ) -> None:
        """A second run restores the seeded cache and executes nothing."""
        reports_root = self._seed_cache(cached_runner_project)

        second_exit = tm.ok(self.runner_for(cached_runner_project).execute())
        tm.that(second_exit, eq=0)
        second_summary = self.summary(reports_root)
        tm.that(
            second_summary,
            has=["executed=0", "deselected=1", "cache_restored=True", "exit=0"],
        )
        warm_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        for receipt in ("cache-before.json", "cache-after.json"):
            warm_state = m.Infra.TestmonCacheState.model_validate_json(
                tm.ok(u.Cli.files_read_text(reports_root / warm_name / receipt))
            )
            tm.that(warm_state.restored_accepted, eq=True)
            tm.that(warm_state.seed_needed, eq=False)

    @pytest.mark.slow
    def test_seeded_cache_executes_only_an_added_test(
        self, cached_runner_project: Path
    ) -> None:
        """A test added after the seed is the only one the next run executes."""
        reports_root = self._seed_cache(cached_runner_project)
        (cached_runner_project / "tests" / "test_added.py").write_text(
            "def test_added_after_cache_seed():\n    assert True\n", encoding="utf-8"
        )
        added_exit = tm.ok(self.runner_for(cached_runner_project).execute())
        tm.that(added_exit, eq=0)
        tm.that(
            self.summary(reports_root),
            has=["executed=1", "failed=0", "errors=0", "exit=0"],
        )

    @pytest.mark.slow
    @pytest.mark.parametrize("omit_case", [False, True], ids=["order", "membership"])
    def test_warm_workers_follow_the_central_selection_order(
        self, cached_runner_project: Path, *, omit_case: bool
    ) -> None:
        """Real workers must agree even when a consumer hook reorders per worker."""
        cache = config.Infra.codegen.make.testmon_cache
        sample = cached_runner_project / cache.target_directory / "test_runtime.py"
        sample.write_text(
            "from runner_sample import answer\n\n"
            "def test_first():\n    assert answer() == 42\n\n"
            "def test_second():\n    assert answer() > 0\n\n"
            "def test_third():\n    assert isinstance(answer(), int)\n",
            encoding="utf-8",
        )
        assert tm.ok(self.runner_for(cached_runner_project).execute()) == 0
        worker_action = (
            "    if get_xdist_worker_id(session) == 'gw0':\n        items.pop()\n"
            if omit_case
            else "    items.sort(key=lambda item: item.nodeid,\n"
            "               reverse=get_xdist_worker_id(session) == 'gw0')\n"
        )
        (cached_runner_project / "conftest.py").write_text(
            "import pytest\nfrom xdist import get_xdist_worker_id\n\n"
            "@pytest.hookimpl(trylast=True)\n"
            "def pytest_collection_modifyitems(session, items):\n"
            f"{worker_action}",
            encoding="utf-8",
        )
        (cached_runner_project / "src" / "runner_sample" / "__init__.py").write_text(
            "def answer() -> int:\n    return sum((40, 2))\n", encoding="utf-8"
        )

        exit_code = tm.ok(self.runner_for(cached_runner_project).execute())
        reports_root = cached_runner_project / cache.reports_directory
        if omit_case:
            assert exit_code != 0
            logs = [path.read_text() for path in reports_root.glob("*/pytest.log")]
            assert any(
                "Runner collection differs from selection" in log for log in logs
            )
            return
        assert exit_code == 0
        tm.that(
            self.summary(reports_root),
            has=["executed=3", "cache_restored=True", "errors=0", "exit=0"],
        )

    @pytest.mark.slow
    def test_first_failure_stops_remaining_cases(
        self, cached_runner_project: Path
    ) -> None:
        """Expose the first failure and do not execute later failing cases."""
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

        exit_code = tm.ok(self.runner_for(cached_runner_project).execute())

        tm.that(exit_code, ne=0)
        reports_root = cached_runner_project / cache.reports_directory
        (report_path,) = reports_root.glob("*/junit.xml")
        report = tm.ok(u.Cli.files_read_text(report_path))
        tm.that(
            report,
            has=[
                'tests="1"',
                'failures="1"',
                'errors="0"',
                'skipped="0"',
                "first failure evidence",
            ],
        )
        tm.that(report, lacks=["second failure evidence", 'name="test_runtime"'])
        outcome = m.Cli.ProcessOutcome.model_validate_json(
            tm.ok(u.Cli.files_read_text(report_path.parent / "suite-outcome.json"))
        )
        tm.that(outcome.raw_return_code, eq=exit_code)
        tm.that(outcome.timed_out, eq=False)
        tm.that(outcome.forwarded_signal, none=True)
        # The declared max-failures stop interrupts the xdist session, which
        # pytest reports as INTERRUPTED; the summary carries that raw code.
        tm.that(
            self.summary(reports_root),
            has=["failed=1", f"exit={pytest.ExitCode.INTERRUPTED.value}"],
        )
        events = tm.ok(u.Cli.files_read_text(report_path.parent / "events.jsonl"))
        tm.that(events, has="first failure evidence", lacks="second failure evidence")

    @pytest.mark.slow
    @pytest.mark.parametrize(
        ("finding", "strict"),
        [
            ("skip", False),
            ("warning", False),
            ("suspended-warning", False),
            ("suspended-warning", True),
            ("homonymous-warning", False),
        ],
    )
    def test_runtime_findings_keep_complete_accounting(
        self, cached_runner_project: Path, finding: str, *, strict: bool
    ) -> None:
        """Real zero-exit pytest runs still reject skips and unsuspended warnings."""
        cache = config.Infra.codegen.make.testmon_cache
        suspended = 0
        if strict:
            with (cached_runner_project / "pyproject.toml").open("a") as stream:
                stream.write('\naddopts = ["--flext-enforce-strict"]\n')
        if finding == "skip":
            source = (
                "import pytest\n\n"
                "def test_finding():\n    pytest.skip('required runtime evidence')\n"
            )
        else:
            if finding == "suspended-warning":
                category = "ConsumerNotice"
                declaration = (
                    "from flext_core import c\n\n"
                    f"class {category}(c.FlextSmellViolation):\n    pass\n"
                )
                suspended = 2 * int(not strict)
            else:
                category = (
                    c.FlextSmellViolation.__name__
                    if finding == "homonymous-warning"
                    else "DomainNotice"
                )
                declaration = f"class {category}(UserWarning):\n    pass\n"
            (
                cached_runner_project
                / c.Infra.DEFAULT_SRC_DIR
                / "runner_sample"
                / "notices.py"
            ).write_text(declaration, encoding="utf-8")
            source = f"from runner_sample.notices import {category}\n"
            source += (
                "import warnings\n\n"
                "def test_finding():\n"
                "    warnings.simplefilter('always')\n"
                "    for _ in range(2):\n"
                f"        warnings.warn('repeated runtime evidence', {category})\n"
            )
        (
            cached_runner_project / cache.target_directory / "test_findings.py"
        ).write_text(source, encoding="utf-8")

        exit_code = tm.ok(self.runner_for(cached_runner_project).execute())

        warnings_count = 0 if finding == "skip" else 2
        blocked = warnings_count - suspended
        expected_exit = int(finding == "skip" or blocked > 0)
        tm.that(exit_code, eq=expected_exit)
        reports_root = cached_runner_project / cache.reports_directory
        tm.that(
            self.summary(reports_root),
            has=[
                "executed=2",
                f"warnings={warnings_count}",
                f"blocking_warnings={blocked}",
                f"suspended_warnings={suspended}",
                f"skipped={int(finding == 'skip')}",
                f"exit={expected_exit}",
            ],
        )
        (outcome_path,) = reports_root.glob("*/suite-outcome.json")
        outcome = m.Cli.ProcessOutcome.model_validate_json(outcome_path.read_text())
        tm.that(outcome.raw_return_code, eq=0)
        warning_evidence = (outcome_path.parent / "warnings.txt").read_text()
        tm.that(warning_evidence.count("repeated runtime evidence"), eq=warnings_count)
        suspended_evidence = (
            outcome_path.parent / "suspended-warnings.txt"
        ).read_text()
        tm.that(suspended_evidence.count("repeated runtime evidence"), eq=suspended)

    @pytest.mark.slow
    def test_setup_failure_is_accounted_without_a_call_phase(
        self, cached_runner_project: Path
    ) -> None:
        """A failed fixture is one complete lifecycle: setup and teardown, no call."""
        runner = self.runner_for(cached_runner_project)
        (cached_runner_project / runner.target / "test_setup.py").write_text(
            "import pytest\n\n@pytest.fixture\ndef broken():\n"
            "    raise RuntimeError('setup failure evidence')\n\n"
            "def test_setup(broken):\n    assert broken\n",
            encoding="utf-8",
        )

        tm.that(tm.ok(runner.execute()), ne=0)

        reports_root = cached_runner_project / runner.reports
        latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        tm.that(
            tm.ok(u.Cli.files_read_text(reports_root / latest_name / "errors.txt")),
            has="setup failure evidence",
        )
        tm.that(
            self.summary(reports_root),
            has=["executed=2", "errors=1", "accounting_complete=True"],
        )

    @pytest.mark.parametrize(
        ("phases", "expected"),
        [
            (("setup", "teardown"), "incomplete pytest lifecycle"),
            (("setup", "call"), "incomplete pytest lifecycle"),
            (("setup", "setup", "call", "teardown"), "duplicate pytest phase"),
        ],
        ids=["missing-call", "missing-teardown", "duplicate-setup"],
    )
    def test_report_log_rejects_incomplete_or_repeated_lifecycles(
        self, tmp_path: Path, phases: t.StrTuple, expected: str
    ) -> None:
        """Every reported node needs exactly one setup, call and teardown."""
        report_log = tmp_path / "suite.events.jsonl"
        report_log.write_text(
            "".join(
                m.Infra.PytestReportEvent.model_validate({
                    "$report_type": "TestReport",
                    "nodeid": "tests/test_lifecycle.py::test_case",
                    "when": phase,
                    "outcome": "passed",
                }).model_dump_json(by_alias=True, exclude_none=True)
                + "\n"
                for phase in phases
            ),
            encoding="utf-8",
        )
        report_log.with_suffix(c.Infra.PYTEST_WARNING_EVENTS_SUFFIX).write_text(
            "", encoding="utf-8"
        )

        with pytest.raises(ValueError, match=expected):
            FlextInfraPytestDiagExtractor.extract_report_log(report_log)

    @pytest.mark.slow
    def test_external_gate_markers_are_not_executed_offline(
        self, cached_runner_project: Path
    ) -> None:
        """An external-token gate is deselected, never a KeyError, and reported.

        gate-budget/engineering-core: incremental verification records external
        gates as not executed; the full verb owns their execution. The marker set is
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

        exit_code = tm.ok(self.runner_for(cached_runner_project).execute())

        tm.that(exit_code, eq=0)
        reports_root = cached_runner_project / cache.reports_directory
        latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        tm.that(
            self.summary(reports_root),
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
        runner = self.runner_for(cached_runner_project)

        exit_code = tm.ok(runner.execute_coverage())

        tm.that(exit_code, eq=0)
        latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        coverage = reports_root / latest_name / "coverage.xml"
        tm.that(coverage.is_file(), eq=True)
        tm.that(coverage.stat().st_size > 0, eq=True)
        summary = self.summary(reports_root)
        tm.that(summary, has=["executed=1", "failed=0", "exit=0"])
        command = tm.ok(
            u.Cli.files_read_text(reports_root / latest_name / "command.txt")
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
            [arg for arg in inventory_command if arg.startswith("--testmon")], eq=[]
        )
        tm.that(
            (reports_root / latest_name / "testmon-inventory.json").is_file(), eq=True
        )
        tm.that(runner.testmon_db.exists(), eq=False)

    @pytest.mark.slow
    def test_failed_coverage_suite_preserves_original_failure_and_accounting(
        self, cached_runner_project: Path
    ) -> None:
        """No-cov-on-fail omits coverage without hiding the failed test evidence."""
        runner = self.runner_for(cached_runner_project)
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
            tm.ok(u.Cli.files_read_text(report_dir / "suite-outcome.json"))
        )
        tm.that(outcome.raw_return_code, eq=exit_code)
        tm.that(outcome.timed_out, eq=False)
        tm.that(outcome.forwarded_signal, none=True)
        accounting = m.Infra.TestmonRunAccounting.model_validate_json(
            tm.ok(u.Cli.files_read_text(report_dir / "run-accounting.json"))
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
            self.summary(reports_root),
            has=["failed=1", "accounting_complete=True", f"exit={exit_code}"],
        )
        tm.that(runner.testmon_db.exists(), eq=False)

    @pytest.mark.slow
    def test_collection_policy_error_fails_loud_and_names_the_offender(
        self, policy_violation_project: Path
    ) -> None:
        """A collection-time policy error rejects the run and names the offender."""
        runner = self.runner_for(policy_violation_project)

        with pytest.raises(RuntimeError) as raised:
            runner.execute()

        tm.that(str(raised.value), has=["FLEXT slow timeout policy", "test_policy.py"])

    @pytest.mark.slow
    def test_warm_partial_selection_accounts_for_every_stable_test(
        self, cached_runner_project: Path
    ) -> None:
        """A changed dependency executes its consumer and accounts for stable IDs."""
        runner = self.runner_for(cached_runner_project)
        (cached_runner_project / runner.target / "test_stable.py").write_text(
            "def test_stable():\n    assert 17 == 17\n", encoding="utf-8"
        )
        tm.that(tm.ok(runner.execute()), eq=0)
        (
            cached_runner_project
            / c.Infra.DEFAULT_SRC_DIR
            / "runner_sample"
            / "__init__.py"
        ).write_text(
            "def answer() -> int:\n    return sum((40, 2))\n", encoding="utf-8"
        )

        tm.that(tm.ok(self.runner_for(cached_runner_project).execute()), eq=0)

        reports_root = cached_runner_project / runner.reports
        report_dir = reports_root / (reports_root / "latest.txt").read_text().strip()
        selection = m.Infra.PytestCollectionManifest.model_validate_json(
            (report_dir / "testmon-selection.json").read_text()
        )
        inventory = m.Infra.PytestCollectionManifest.model_validate_json(
            (report_dir / "testmon-inventory.json").read_text()
        )
        tm.that(len(selection.node_ids), eq=1)
        tm.that(len(inventory.node_ids), eq=2)
        tm.that(set(selection.node_ids) < set(inventory.node_ids), eq=True)
        accounting = m.Infra.TestmonRunAccounting.model_validate_json(
            (report_dir / "run-accounting.json").read_text()
        )
        tm.that(accounting.inventory_count, eq=len(inventory.node_ids))
        tm.that(accounting.executed_count, eq=len(selection.node_ids))
        tm.that(accounting.reported_count, eq=len(selection.node_ids))
        tm.that(
            accounting.deselected_count,
            eq=len(inventory.node_ids) - len(selection.node_ids),
        )
        tm.that(
            self.summary(reports_root),
            has=["outcome=executed", "executed=1", "deselected=1", "inventory=2"],
        )

    @pytest.mark.slow
    @pytest.mark.parametrize("finding", ["warning", "module-skip", "module-error"])
    def test_collection_findings_block_before_suite_execution(
        self, cached_runner_project: Path, finding: str
    ) -> None:
        """Collect-only warnings, skips and import failures retain native evidence."""
        runner = self.runner_for(cached_runner_project)
        if finding == "warning":
            (cached_runner_project / "conftest.py").write_text(
                "import warnings\n\n"
                "def pytest_collection_finish(session):\n"
                "    if session.config.getoption('collectonly'):\n"
                "        warnings.warn('collect-only finding', RuntimeWarning)\n",
                encoding="utf-8",
            )
        else:
            source = (
                "import pytest\npytest.skip('required module', allow_module_level=True)\n"
                if finding == "module-skip"
                else "raise RuntimeError('first collection failure')\n"
            )
            (cached_runner_project / runner.target / "test_collect.py").write_text(
                source, encoding="utf-8"
            )

        expected = (
            "first collection failure"
            if finding == "module-error"
            else "collection contains blocking findings"
        )
        with pytest.raises(RuntimeError, match=expected):
            runner.execute()

        (events,) = (cached_runner_project / runner.reports).glob(
            "*/testmon-selection.events.jsonl"
        )
        diagnostic = tm.ok(FlextInfraPytestDiagExtractor.extract_report_log(events))
        tm.that(diagnostic.blocking_warning_count, eq=int(finding == "warning"))
        tm.that(diagnostic.collection_skipped_count, eq=int(finding == "module-skip"))
        tm.that(diagnostic.collection_failed_count, eq=int(finding == "module-error"))
        tm.that((events.parent / "suite-outcome.json").exists(), eq=False)
        outcome = m.Cli.ProcessOutcome.model_validate_json(
            (events.parent / "selection-outcome.json").read_text()
        )
        tm.that(outcome.raw_return_code != 0, eq=finding == "module-error")

    @pytest.mark.slow
    @pytest.mark.parametrize(
        ("strict", "homonym"), [(False, False), (True, False), (False, True)]
    )
    def test_serial_collection_warning_policy_preserves_identity_and_strict(
        self, cached_runner_project: Path, *, strict: bool, homonym: bool
    ) -> None:
        """Serial collection applies the same runtime policy as xdist execution."""
        runner = self.runner_for(cached_runner_project)
        if strict:
            with (cached_runner_project / "pyproject.toml").open("a") as stream:
                stream.write('\naddopts = ["--flext-enforce-strict"]\n')
        category = c.FlextSmellViolation.__name__ if homonym else "ConsumerNotice"
        declaration = (
            f"class {category}(UserWarning):\n    pass\n"
            if homonym
            else f"from flext_core import c\n\nclass {category}(c.FlextSmellViolation):\n    pass\n"
        )
        (
            cached_runner_project
            / c.Infra.DEFAULT_SRC_DIR
            / "runner_sample"
            / "notices.py"
        ).write_text(declaration, encoding="utf-8")
        (cached_runner_project / "conftest.py").write_text(
            f"import warnings\nfrom runner_sample.notices import {category}\n\n"
            "def pytest_collection_finish(session):\n"
            "    if session.config.getoption('collectonly'):\n"
            "        warnings.simplefilter('always')\n"
            f"        warnings.warn('serial policy evidence', {category})\n",
            encoding="utf-8",
        )
        blocking = strict or homonym

        if blocking:
            with pytest.raises(
                RuntimeError, match="collection contains blocking findings"
            ):
                runner.execute()
        else:
            tm.that(tm.ok(runner.execute()), eq=0)

        (receipt,) = (cached_runner_project / runner.reports).glob(
            "*/testmon-selection.events.diagnostics.json"
        )
        diagnostics = m.Infra.PytestDiagnostics.model_validate_json(receipt.read_text())
        tm.that(diagnostics.warning_count, eq=1)
        tm.that(diagnostics.blocking_warning_count, eq=int(blocking))
        tm.that(diagnostics.suspended_warning_count, eq=int(not blocking))
        events = receipt.with_name("testmon-selection.events.jsonl")
        identity = m.Infra.PytestWarningEvent.model_validate_json(
            events.with_suffix(c.Infra.PYTEST_WARNING_EVENTS_SUFFIX).read_text().strip()
        )
        tm.that(identity.enforcement_strict, eq=strict)
        tm.that(identity.category_module, eq="runner_sample.notices")
        if not blocking:
            # A cold cache has no stored selection to verify, so the serial
            # selection pass is the only collection phase of this run.
            summary = self.summary(cached_runner_project / runner.reports).splitlines()
            for count in (
                "warnings=1",
                "suspended_warnings=1",
                "selection_warnings=1",
                "suite_warnings=0",
            ):
                tm.that(count in summary, eq=True)
            tm.that(any(line.startswith("inventory_") for line in summary), eq=False)
            evidence = (receipt.parent / "warnings.txt").read_text()
            tm.that(evidence.count("serial policy evidence"), eq=1)

    @pytest.mark.slow
    def test_warm_inventory_captures_warnings_from_stable_modules(
        self, cached_runner_project: Path
    ) -> None:
        """A file omitted by testmon remains covered by complete collection policy."""
        runner = self.runner_for(cached_runner_project)
        target = cached_runner_project / runner.target
        (target / "test_stable.py").write_text(
            "from pathlib import Path\nimport warnings\n\n"
            "if Path(__file__).with_name('emit-warning').exists():\n"
            "    warnings.warn('stable inventory finding', RuntimeWarning)\n\n"
            "def test_stable():\n    assert 17 == 17\n",
            encoding="utf-8",
        )
        tm.that(tm.ok(runner.execute()), eq=0)
        reports_root = cached_runner_project / runner.reports
        existing = set(reports_root.glob("*/run-context.json"))
        (target / "emit-warning").touch()

        inventory_runner = self.runner_for(cached_runner_project)
        with pytest.raises(RuntimeError, match="collection contains blocking findings"):
            inventory_runner.execute()

        (context,) = set(reports_root.glob("*/run-context.json")) - existing
        selection = m.Infra.PytestCollectionManifest.model_validate_json(
            (context.parent / "testmon-selection.json").read_text()
        )
        tm.that(selection.node_ids, eq=())
        diagnostics = m.Infra.PytestDiagnostics.model_validate_json(
            (context.parent / "testmon-inventory.events.diagnostics.json").read_text()
        )
        tm.that(diagnostics.blocking_warning_count, eq=1)
        tm.that(diagnostics.warning_lines[0], contains="stable inventory finding")
        tm.that((context.parent / "suite-outcome.json").exists(), eq=False)

    @pytest.mark.slow
    def test_missing_collection_manifest_preserves_file_failure(
        self, cached_runner_project: Path
    ) -> None:
        (cached_runner_project / "conftest.py").write_text(
            "from pathlib import Path\n\n"
            "def pytest_sessionfinish(session):\n"
            "    target = session.config.getoption(\n"
            f"        {c.Infra.PYTEST_COLLECTION_MANIFEST_OPTION!r})\n"
            "    if target:\n        Path(target).unlink()\n",
            encoding="utf-8",
        )
        runner = self.runner_for(cached_runner_project)

        with pytest.raises(FileNotFoundError, match=r"testmon-selection\.json"):
            runner.execute()

    @pytest.mark.slow
    def test_coverage_pass_fails_loud_on_collection_policy_error(
        self, policy_violation_project: Path
    ) -> None:
        """The coverage inventory rejects the same collection policy violation."""
        runner = self.runner_for(policy_violation_project)

        with pytest.raises(RuntimeError) as raised:
            runner.execute_coverage()

        tm.that(str(raised.value), has=["FLEXT slow timeout policy", "test_policy.py"])
