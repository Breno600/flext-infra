"""Observable public cached-pytest runtime contract."""

from __future__ import annotations

import pstats
import sqlite3
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m, u
from tests.unit.validate.pytest_runner_support import runner_for, summary


class TestsFlextInfraPytestRunner:
    """Exercise the real pytest, testmon, coverage, and report lifecycle."""

    @pytest.mark.parametrize("ci_context", [True, False])
    def test_marker_selection_is_shared_by_collection_execution_and_coverage(
        self, cached_runner_project: Path, *, ci_context: bool
    ) -> None:
        """CI/pre-commit omit slow cases; local/pre-push keep them selectable."""
        runner = runner_for(cached_runner_project, ci_context=ci_context)
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

    def test_only_the_bounded_incremental_verb_carries_testmon(
        self, cached_runner_project: Path
    ) -> None:
        """make test selects through testmon; test-full has no testmon or limit.

        The incremental argv names no per-toolchain environment, so every
        checkout and relock of a project shares one testmon history.
        """
        runner = runner_for(cached_runner_project)
        report = (
            cached_runner_project
            / config.Infra.codegen.make.testmon_cache.reports_directory
        )
        full = c.Infra.PytestExecutionMode.FULL
        selection = runner.build_selection_command(
            report_log=report / "selection.jsonl",
            manifest_path=report / "selection.json",
        )
        incremental = (
            selection,
            runner.build_selection_command(
                report_log=report / "inventory.jsonl",
                manifest_path=report / "inventory.json",
                complete=True,
            ),
            runner.build_command(report),
        )
        unbounded = (
            runner.build_selection_command(
                report_log=report / "full.jsonl",
                manifest_path=report / "full.json",
                complete=True,
                execution_mode=full,
            ),
            runner.build_command(report, execution_mode=full),
        )
        case_timeout = (
            f"--timeout={config.Infra.tooling.tools.pytest.case_timeout_seconds}"
        )
        tm.that("--testmon-forceselect" in selection, eq=True)
        for command in incremental:
            tm.that("--testmon" in command, eq=True)
            tm.that("--testmon-env" in command, eq=False)
            tm.that(case_timeout in command, eq=True)
        for command in (*unbounded, runner.build_coverage_command(report)):
            tm.that(any(arg.startswith("--testmon") for arg in command), eq=False)
        for command in unbounded:
            tm.that(case_timeout in command, eq=False)
            tm.that("--timeout=0" in command, eq=True)
            tm.that(
                f"{c.Infra.FLEXT_SLOW_TIMEOUT_SECONDS}=" in command, eq=True
            )
        for command, bounded in (
            (incremental[-1], True),
            (runner.build_coverage_command(report), True),
            (unbounded[-1], False),
        ):
            tm.that(
                any(
                    arg.startswith(c.Infra.PYTEST_SUITE_STOP_OPTION)
                    for arg in command
                ),
                eq=bounded,
            )

    def _seed_cache(self, cached_runner_project: Path) -> Path:
        """Seed the persistent cache through one public cold run."""
        tm.that(tm.ok(runner_for(cached_runner_project).execute()), eq=0)
        return (
            cached_runner_project
            / config.Infra.codegen.make.testmon_cache.reports_directory
        )

    @pytest.mark.slow
    @pytest.mark.parametrize("profile_collection", [False, True])
    def test_warm_cache_deselects_the_unchanged_suite(
        self, cached_runner_project: Path, *, profile_collection: bool
    ) -> None:
        """A second run restores the seeded cache and executes nothing."""
        reports_root = self._seed_cache(cached_runner_project)

        second_exit = tm.ok(
            runner_for(
                cached_runner_project, profile_collection=profile_collection
            ).execute()
        )
        tm.that(second_exit, eq=0)
        second_summary = summary(reports_root)
        tm.that(
            second_summary,
            has=["executed=0", "deselected=1", "cache_restored=True", "exit=0"],
        )
        warm_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        for phase in ("testmon-selection", "testmon-inventory"):
            profile = reports_root / warm_name / f"{phase}.pstats"
            assert profile.is_file() == profile_collection
            if profile_collection:
                assert pstats.Stats(str(profile)).get_stats_profile().func_profiles
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
        added_exit = tm.ok(runner_for(cached_runner_project).execute())
        tm.that(added_exit, eq=0)
        tm.that(
            summary(reports_root), has=["executed=1", "failed=0", "errors=0", "exit=0"]
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
        assert tm.ok(runner_for(cached_runner_project).execute()) == 0
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

        exit_code = tm.ok(runner_for(cached_runner_project).execute())
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
            summary(reports_root),
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

        exit_code = tm.ok(runner_for(cached_runner_project).execute())

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
            summary(reports_root),
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

        exit_code = tm.ok(runner_for(cached_runner_project).execute())

        warnings_count = 0 if finding == "skip" else 2
        blocked = warnings_count - suspended
        expected_exit = int(finding == "skip" or blocked > 0)
        tm.that(exit_code, eq=expected_exit)
        reports_root = cached_runner_project / cache.reports_directory
        tm.that(
            summary(reports_root),
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
        runner = runner_for(cached_runner_project)
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
            summary(reports_root),
            has=["executed=2", "errors=1", "accounting_complete=True"],
        )

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

        exit_code = tm.ok(runner_for(cached_runner_project).execute())

        tm.that(exit_code, eq=0)
        reports_root = cached_runner_project / cache.reports_directory
        latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        tm.that(
            summary(reports_root),
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
    @pytest.mark.parametrize("ci_context", [False, True])
    def test_full_includes_external_and_ci_markers(
        self, cached_runner_project: Path, *, ci_context: bool
    ) -> None:
        """The real full verb executes harmless consumers of every excluded marker."""
        policy = config.Infra.tooling.tools.pytest
        markers = tuple(
            sorted({*policy.external_gate_markers, *policy.ci_excluded_markers})
        )
        marker_lines = "".join(f'  "{marker}",\n' for marker in policy.standard_markers)
        (cached_runner_project / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            f'pythonpath = ["{c.Infra.DEFAULT_SRC_DIR}"]\n'
            f"markers = [\n{marker_lines}]\n",
            encoding="utf-8",
        )
        runner = runner_for(cached_runner_project, ci_context=ci_context, testmon=False)
        source = "import pytest\nfrom runner_sample import answer\n\n"
        for index, marker in enumerate(markers):
            source += (
                f"@pytest.mark.{marker}\n"
                f"def test_marked_{index}():\n    assert answer() == 42\n\n"
            )
        (cached_runner_project / runner.target / "test_marked.py").write_text(
            source, encoding="utf-8"
        )

        tm.that(tm.ok(runner.execute_full()), eq=0)

        reports_root = cached_runner_project / runner.reports
        (context_path,) = reports_root.glob("*/run-context.json")
        full = context_path.parent
        accounting = m.Infra.TestmonRunAccounting.model_validate_json(
            (full / "run-accounting.json").read_text()
        )
        tm.that(accounting.executed_count, eq=1 + len(markers))
        tm.that(accounting.inventory_count, eq=1 + len(markers))
        tm.that(accounting.deselected_count, eq=0)
        full_summary = (full / "summary.txt").read_text().splitlines()
        tm.that("not_executed_external_gates=" in full_summary, eq=True)
        tm.that("not_executed_ci_markers=" in full_summary, eq=True)
        for command in (
            runner.build_selection_command(
                report_log=full / "testmon-inventory.events.jsonl",
                manifest_path=full / "testmon-inventory.json",
                complete=True,
                execution_mode=c.Infra.PytestExecutionMode.FULL,
            ),
            runner.build_command(
                full, execution_mode=c.Infra.PytestExecutionMode.FULL
            ),
        ):
            tm.that("-m" in command[3:], eq=False)

    @pytest.mark.slow
    def test_full_runs_without_testmon_or_deadline_beside_a_warm_cache(
        self, cached_runner_project: Path
    ) -> None:
        """The full verb executes everything and never touches the warm database."""
        (cached_runner_project / "conftest.py").write_text(
            "import sys\n\n"
            "def pytest_collection_finish(session):\n"
            "    if session.config.getoption('collectonly'):\n"
            "        print('diagnostic::not-a-node')\n"
            "        sys.stderr.write('stderr::not-a-node\\n')\n",
            encoding="utf-8",
        )
        baseline = runner_for(cached_runner_project)
        tm.that(tm.ok(baseline.execute()), eq=0)
        database = baseline.required_testmon_db()
        seeded = database.read_bytes()
        reports_root = cached_runner_project / baseline.reports
        existing = set(reports_root.glob("*/run-context.json"))
        runner = runner_for(cached_runner_project, testmon=False)

        tm.that(tm.ok(runner.execute_full()), eq=0)

        (context_path,) = set(reports_root.glob("*/run-context.json")) - existing
        context = m.Infra.PytestRunContext.model_validate_json(context_path.read_text())
        tm.that(context.execution_mode, eq="full")
        tm.that(context.testmon_db, eq=None)
        tm.that(context.deadline_monotonic, eq=None)
        tm.that(database.read_bytes(), eq=seeded)
        full = context_path.parent
        tm.that(
            (full / "summary.txt").read_text(),
            has=["outcome=executed", "executed=1", "exit=0"],
        )
        tm.that((full / "cache-before.json").exists(), eq=False)
        command = (full / "command.txt").read_text()
        tm.that(command, lacks=["--testmon", c.Infra.PYTEST_SUITE_STOP_OPTION])
        tm.that(command, has="--timeout=0")
        manifest = m.Infra.PytestCollectionManifest.model_validate_json(
            (full / "testmon-inventory.json").read_text()
        )
        tm.that(
            any("not-a-node" in node_id for node_id in manifest.node_ids), eq=False
        )
        tm.that(
            (full / "testmon-inventory.log").read_text(),
            has=["diagnostic::not-a-node", "stderr::not-a-node"],
        )

    @pytest.mark.slow
    def test_warm_partial_selection_accounts_for_every_stable_test(
        self, cached_runner_project: Path
    ) -> None:
        """A changed dependency executes its consumer and accounts for stable IDs."""
        runner = runner_for(cached_runner_project)
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

        tm.that(tm.ok(runner_for(cached_runner_project).execute()), eq=0)

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
            summary(reports_root),
            has=["outcome=executed", "executed=1", "deselected=1", "inventory=2"],
        )

    @pytest.mark.slow
    def test_full_stops_at_the_first_failure(
        self, cached_runner_project: Path
    ) -> None:
        """A failing full run publishes its failure receipts and stays red."""
        runner = runner_for(cached_runner_project, testmon=False)
        (cached_runner_project / runner.target / "test_failure.py").write_text(
            "def test_failure():\n    assert False, 'the full verb is red'\n",
            encoding="utf-8",
        )

        exit_code = tm.ok(runner.execute_full())

        # Items run in randomized order: a failure that leaves items behind
        # stops xdist through max-failures (INTERRUPTED); a last-item failure
        # completes the suite (TESTS_FAILED). Both are the full red.
        tm.that(
            (pytest.ExitCode.TESTS_FAILED.value, pytest.ExitCode.INTERRUPTED.value),
            has=exit_code,
        )
        (context_path,) = (cached_runner_project / runner.reports).glob(
            "*/run-context.json"
        )
        context = m.Infra.PytestRunContext.model_validate_json(context_path.read_text())
        tm.that(context.execution_mode, eq="full")
        outcome = m.Cli.ProcessOutcome.model_validate_json(
            (context_path.parent / "suite-outcome.json").read_text()
        )
        tm.that(outcome.raw_return_code, eq=exit_code)

    def test_incremental_preserves_corrupt_database_failure_before_execution(
        self, cached_runner_project: Path
    ) -> None:
        """make test fails loud on a corrupt database before any suite runs."""
        runner = runner_for(cached_runner_project)
        runner.required_testmon_db().write_bytes(b"not a SQLite database")

        with pytest.raises(sqlite3.DatabaseError):
            runner.execute()

        tm.that(
            list((cached_runner_project / runner.reports).glob("*/command.txt")), eq=[]
        )

    @pytest.mark.slow
    def test_full_rejects_an_empty_complete_collection(
        self, cached_runner_project: Path
    ) -> None:
        (cached_runner_project / "conftest.py").write_text(
            "from pathlib import Path\nfrom flext_infra import m\n\n"
            "def pytest_collection_modifyitems(config, items):\n"
            "    if config.getoption('collectonly'):\n"
            "        target = Path(config.getoption(\n"
            f"            {c.Infra.PYTEST_COLLECTION_MANIFEST_OPTION!r}))\n"
            "        context = m.Infra.PytestRunContext.model_validate_json(\n"
            "            (target.parent / 'run-context.json').read_text())\n"
            "        if context.execution_mode == 'full':\n            items.clear()\n",
            encoding="utf-8",
        )
        runner = runner_for(cached_runner_project, testmon=False)

        with pytest.raises(RuntimeError):
            runner.execute_full()

        (context_path,) = (cached_runner_project / runner.reports).glob(
            "*/run-context.json"
        )
        full = context_path.parent
        context = m.Infra.PytestRunContext.model_validate_json(context_path.read_text())
        tm.that(context.execution_mode, eq="full")
        full_outcome = m.Cli.ProcessOutcome.model_validate_json(
            (full / "inventory-outcome.json").read_text()
        )
        tm.that(full_outcome.raw_return_code, ne=0)
        tm.that(
            (cached_runner_project / runner.reports / "latest.txt").read_text().strip(),
            eq=full.name,
        )
        tm.that((full / "suite-outcome.json").exists(), eq=False)
        inventory = m.Infra.PytestCollectionManifest.model_validate_json(
            (full / "testmon-inventory.json").read_text()
        )
        tm.that(inventory.node_ids, eq=())
