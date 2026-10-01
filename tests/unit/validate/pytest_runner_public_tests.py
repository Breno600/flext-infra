"""Observable public cached-pytest runtime contract."""

from __future__ import annotations

import pstats
import sqlite3
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m, t, u
from tests.unit.validate.pytest_runner_support import (
    declare_parallel_project,
    runner_for,
    summary,
)


class TestsFlextInfraPytestRunner:
    """Exercise the real pytest, testmon, coverage, and report lifecycle."""

    @pytest.mark.parametrize("ci_context", [True, False])
    def test_marker_selection_is_shared_by_collection_execution_and_coverage(
        self, cached_runner_project: Path, *, ci_context: bool
    ) -> None:
        """Selection, inventory and execution share one budgeted expression.

        Premise (rules/workflow/gate-budget.md): slow cases run in their own
        phase, so the budgeted phase always deselects the slow marker; the
        coverage run keeps CI-excluded markers selectable outside CI.
        """
        runner = runner_for(cached_runner_project, ci_context=ci_context)
        report = (
            cached_runner_project
            / config.Infra.codegen.make.testmon_cache.reports_directory
        )
        pytest_policy = config.Infra.tooling.tools.pytest

        def marker_expression(command: t.StrSequence) -> str:
            return command[command.index("-m", 3) + 1]

        budgeted = {
            marker_expression(command)
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
            )
        }
        tm.that(budgeted, length=1)
        budgeted_expression = next(iter(budgeted))
        coverage_expression = marker_expression(runner.build_coverage_command(report))
        tm.that(budgeted_expression, has=pytest_policy.slow_marker)
        for marker in pytest_policy.ci_excluded_markers:
            tm.that(marker in coverage_expression, eq=ci_context)
        for marker in pytest_policy.external_gate_markers:
            tm.that(budgeted_expression, has=marker)
            tm.that(coverage_expression, has=marker)

    def test_testmon_commands_name_the_toolchain_environment(
        self, cached_runner_project: Path
    ) -> None:
        """Every testmon argv names one stable toolchain-fingerprinted env."""
        runner = runner_for(cached_runner_project)
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
        declare_parallel_project(cached_runner_project)
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
        declare_parallel_project(cached_runner_project)
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
        "finding", ["skip", "warning", "mro-warning", "homonymous-warning"]
    )
    def test_runtime_findings_keep_complete_accounting(
        self, cached_runner_project: Path, finding: str
    ) -> None:
        """Real zero-exit pytest runs still reject every skip and every warning."""
        cache = config.Infra.codegen.make.testmon_cache
        if finding == "skip":
            source = (
                "import pytest\n\n"
                "def test_finding():\n    pytest.skip('required runtime evidence')\n"
            )
        else:
            if finding == "mro-warning":
                category = "ConsumerNotice"
                declaration = (
                    "from flext_core import c\n\n"
                    f"class {category}(c.FlextSmellViolation):\n    pass\n"
                )
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
        tm.that(exit_code, eq=1)
        reports_root = cached_runner_project / cache.reports_directory
        tm.that(
            summary(reports_root),
            has=[
                "executed=2",
                f"warnings={warnings_count}",
                f"skipped={int(finding == 'skip')}",
                "exit=1",
            ],
        )
        (outcome_path,) = reports_root.glob("*/suite-outcome.json")
        outcome = m.Cli.ProcessOutcome.model_validate_json(outcome_path.read_text())
        tm.that(outcome.raw_return_code, eq=0)
        warning_evidence = (outcome_path.parent / "warnings.txt").read_text()
        tm.that(warning_evidence.count("repeated runtime evidence"), eq=warnings_count)

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
    def test_full_includes_external_and_ci_markers_after_incremental_scope(
        self, cached_runner_project: Path, *, ci_context: bool
    ) -> None:
        """The real full phase executes harmless consumers of every excluded marker."""
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
        runner = runner_for(cached_runner_project, ci_context=ci_context)
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
        contexts = sorted(reports_root.glob("*/run-context.json"))
        tm.that(len(contexts), eq=2)
        incremental, full = (path.parent for path in contexts)
        excluded = set(policy.external_gate_markers)
        if ci_context:
            excluded.update(policy.ci_excluded_markers)
        for report_dir, expected in (
            (incremental, 1 + len(set(markers) - excluded)),
            (full, 1 + len(markers)),
        ):
            accounting = m.Infra.TestmonRunAccounting.model_validate_json(
                (report_dir / "run-accounting.json").read_text()
            )
            tm.that(accounting.executed_count, eq=expected)
            tm.that(accounting.inventory_count, eq=expected)
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
            runner.build_command(full, execution_mode=c.Infra.PytestExecutionMode.FULL),
        ):
            tm.that("-m" in command[3:], eq=False)

    @pytest.mark.slow
    def test_full_runs_after_warm_cache_and_ignores_node_like_diagnostics(
        self, cached_runner_project: Path
    ) -> None:
        """Cold, warm, and full collection use final items and one physical DB."""
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
        reports_root = cached_runner_project / baseline.reports
        existing = set(reports_root.glob("*/run-context.json"))
        runner = runner_for(cached_runner_project)

        tm.that(tm.ok(runner.execute_full()), eq=0)

        contexts = sorted(set(reports_root.glob("*/run-context.json")) - existing)
        tm.that(len(contexts), eq=2)
        parsed = [
            m.Infra.PytestRunContext.model_validate_json(path.read_text())
            for path in contexts
        ]
        tm.that(
            [context.execution_mode for context in parsed], eq=["incremental", "full"]
        )
        tm.that({context.testmon_db for context in parsed}, eq={runner.testmon_db})
        tm.that(runner.testmon_db.is_absolute(), eq=True)
        tm.that(
            runner.testmon_db.is_relative_to(cached_runner_project.resolve()), eq=False
        )
        tm.that(runner.testmon_db.is_file(), eq=True)
        tm.that(
            (
                cached_runner_project
                / config.Infra.codegen.make.testmon_cache.database_filename
            ).exists(),
            eq=False,
        )
        tm.that(
            {context.deadline_monotonic for context in parsed},
            eq={
                runner.started_at_monotonic
                + config.Infra.tooling.tools.pytest.run_timeout_seconds
            },
        )
        incremental, full = (path.parent for path in contexts)
        tm.that(
            (incremental / "summary.txt").read_text(),
            has=["outcome=cache_hit", "executed=0", "deselected=1"],
        )
        tm.that(
            (full / "summary.txt").read_text(),
            has=["outcome=executed", "executed=1", "exit=0"],
        )
        for report_dir in (incremental, full):
            accounting = m.Infra.TestmonRunAccounting.model_validate_json(
                (report_dir / "run-accounting.json").read_text()
            )
            tm.that(accounting.cache_restored, eq=True)
            for receipt in ("cache-before.json", "cache-after.json"):
                state = m.Infra.TestmonCacheState.model_validate_json(
                    (report_dir / receipt).read_text()
                )
                tm.that(state.restored_accepted, eq=True)
            manifests = [report_dir / "testmon-inventory.json"]
            if report_dir == incremental:
                manifests.append(report_dir / "testmon-selection.json")
            for manifest_path in manifests:
                manifest = m.Infra.PytestCollectionManifest.model_validate_json(
                    manifest_path.read_text()
                )
                tm.that(
                    any("not-a-node" in node_id for node_id in manifest.node_ids),
                    eq=False,
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
    def test_full_stops_at_the_first_incremental_failure(
        self, cached_runner_project: Path
    ) -> None:
        runner = runner_for(cached_runner_project)
        (cached_runner_project / runner.target / "test_failure.py").write_text(
            "def test_failure():\n    assert False, 'full must not follow failure'\n",
            encoding="utf-8",
        )

        exit_code = tm.ok(runner.execute_full())

        # Items run in randomized order: a failure that leaves items behind
        # stops xdist through max-failures (INTERRUPTED); a last-item failure
        # completes the suite (TESTS_FAILED). Both are the incremental red.
        tm.that(
            (pytest.ExitCode.TESTS_FAILED.value, pytest.ExitCode.INTERRUPTED.value),
            has=exit_code,
        )
        (context_path,) = (cached_runner_project / runner.reports).glob(
            "*/run-context.json"
        )
        context = m.Infra.PytestRunContext.model_validate_json(context_path.read_text())
        tm.that(context.execution_mode, eq="incremental")
        outcome = m.Cli.ProcessOutcome.model_validate_json(
            (context_path.parent / "suite-outcome.json").read_text()
        )
        tm.that(outcome.raw_return_code, eq=exit_code)

    def test_full_preserves_corrupt_database_failure_before_execution(
        self, cached_runner_project: Path
    ) -> None:
        runner = runner_for(cached_runner_project)
        runner.testmon_db.write_bytes(b"not a SQLite database")

        with pytest.raises(sqlite3.DatabaseError):
            runner.execute_full()

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
        runner = runner_for(cached_runner_project)

        with pytest.raises(RuntimeError):
            runner.execute_full()

        contexts = sorted(
            (cached_runner_project / runner.reports).glob("*/run-context.json")
        )
        tm.that(len(contexts), eq=2)
        context = m.Infra.PytestRunContext.model_validate_json(contexts[-1].read_text())
        tm.that(context.execution_mode, eq="full")
        tm.that((contexts[0].parent / "summary.txt").read_text(), has="exit=0")
        incremental_outcome = m.Cli.ProcessOutcome.model_validate_json(
            (contexts[0].parent / "suite-outcome.json").read_text()
        )
        tm.that(incremental_outcome.raw_return_code, eq=0)
        full_outcome = m.Cli.ProcessOutcome.model_validate_json(
            (contexts[-1].parent / "inventory-outcome.json").read_text()
        )
        tm.that(full_outcome.raw_return_code, ne=0)
        tm.that(
            (cached_runner_project / runner.reports / "latest.txt").read_text().strip(),
            eq=contexts[-1].parent.name,
        )
        tm.that((contexts[-1].parent / "suite-outcome.json").exists(), eq=False)
        inventory = m.Infra.PytestCollectionManifest.model_validate_json(
            (contexts[-1].parent / "testmon-inventory.json").read_text()
        )
        tm.that(inventory.node_ids, eq=())
