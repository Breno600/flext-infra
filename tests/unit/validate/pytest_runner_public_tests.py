"""Observable public cached-pytest runtime contract."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import (
    FlextInfraPytestDiagExtractor,
    FlextInfraPytestRunner,
    c,
    config,
    m,
    u,
)


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
            runner.build_selection_command(report_log=report / "selection.jsonl"),
            runner.build_selection_command(
                report_log=report / "inventory.jsonl", complete=True
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
        runner = self._runner_for(cached_runner_project)
        report = (
            cached_runner_project
            / config.Infra.codegen.make.testmon_cache.reports_directory
        )
        suite_command = runner.build_command(report)
        names = []
        for command in (
            runner.build_selection_command(report_log=report / "selection.jsonl"),
            runner.build_selection_command(
                report_log=report / "inventory.jsonl", complete=True
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

    def test_worker_ceiling_defaults_without_declared_project(
        self, cached_runner_project: Path
    ) -> None:
        """A tree without ``[project].name`` takes the fleet-wide ceiling."""
        policy = config.Infra.tooling.tools.pytest
        runner = self._runner_for(cached_runner_project)
        assert runner.parallel_worker_budget(policy) == policy.parallel_workers

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
        runner = self._runner_for(cached_runner_project)
        report = (
            cached_runner_project
            / config.Infra.codegen.make.testmon_cache.reports_directory
        )
        budget = runner.parallel_worker_budget(policy)
        assert budget == policy.parallel_worker_overrides[declared_name]
        command = runner.build_command(report)
        workers = command[command.index("-n") + 1]
        assert workers == str(budget)

    @staticmethod
    def _runner_for(
        cached_runner_project: Path, *, ci_context: bool = False
    ) -> FlextInfraPytestRunner:
        """Bind one runner to the fixture project's canonical cache paths."""
        cache = config.Infra.codegen.make.testmon_cache
        return FlextInfraPytestRunner(
            repository_root=cached_runner_project,
            ci_context=ci_context,
            started_at_monotonic=time.monotonic(),
            target=cache.target_directory,
            reports=cache.reports_directory,
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
        cache = config.Infra.codegen.make.testmon_cache
        # pytest-testmon keeps its own default database in the repository root.
        testmon_db = cached_runner_project / cache.database_filename
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
            has=["executed=0", "deselected=1", "cache_restored=True", "exit=0"],
        )

        (cached_runner_project / "tests" / "test_added.py").write_text(
            "def test_added_after_cache_seed():\n    assert True\n", encoding="utf-8"
        )
        added_exit = tm.ok(self._runner_for(cached_runner_project).execute())
        tm.that(added_exit, eq=0)
        tm.that(
            self._summary(reports_root),
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
        assert tm.ok(self._runner_for(cached_runner_project).execute()) == 0
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

        exit_code = tm.ok(self._runner_for(cached_runner_project).execute())
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
            self._summary(reports_root),
            has=["executed=3", "cache_restored=True", "errors=0", "exit=0"],
        )

    @pytest.mark.slow
    def test_warm_workers_follow_the_central_selection_order(
        self, cached_runner_project: Path
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
        assert tm.ok(self._runner_for(cached_runner_project).execute()) == 0
        (cached_runner_project / "conftest.py").write_text(
            "import pytest\nfrom xdist import get_xdist_worker_id\n\n"
            "@pytest.hookimpl(trylast=True)\n"
            "def pytest_collection_modifyitems(session, items):\n"
            "    items.sort(key=lambda item: item.nodeid,\n"
            "               reverse=get_xdist_worker_id(session) == 'gw1')\n",
            encoding="utf-8",
        )
        (cached_runner_project / "src" / "runner_sample" / "__init__.py").write_text(
            "def answer() -> int:\n    return sum((40, 2))\n", encoding="utf-8"
        )

        assert tm.ok(self._runner_for(cached_runner_project).execute()) == 0
        reports_root = cached_runner_project / cache.reports_directory
        tm.that(
            self._summary(reports_root),
            has=["executed=3", "cache_restored=True", "errors=0", "exit=0"],
        )

    @pytest.mark.slow
    def test_failed_cases_do_not_stop_remaining_cases(
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

        exit_code = tm.ok(self._runner_for(cached_runner_project).execute())

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
        tm.that(self._summary(reports_root), has=["failed=1", "exit=1"])
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

        exit_code = tm.ok(self._runner_for(cached_runner_project).execute())

        warnings_count = 0 if finding == "skip" else 2
        blocked = warnings_count - suspended
        expected_exit = int(finding == "skip" or blocked > 0)
        tm.that(exit_code, eq=expected_exit)
        reports_root = cached_runner_project / cache.reports_directory
        tm.that(
            self._summary(reports_root),
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
        runner = self._runner_for(cached_runner_project, ci_context=ci_context)
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
                complete=True,
                execution_mode=c.Infra.PytestExecutionMode.FULL,
            ),
            runner.build_command(full, execution_mode=c.Infra.PytestExecutionMode.FULL),
        ):
            tm.that("-m" in command[3:], eq=False)

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
        baseline = self._runner_for(cached_runner_project)
        tm.that(tm.ok(baseline.execute()), eq=0)
        reports_root = cached_runner_project / baseline.reports
        existing = set(reports_root.glob("*/run-context.json"))
        runner = self._runner_for(cached_runner_project)

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
        runner = self._runner_for(cached_runner_project)
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

        tm.that(tm.ok(self._runner_for(cached_runner_project).execute()), eq=0)

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
            self._summary(reports_root),
            has=["outcome=executed", "executed=1", "deselected=1", "inventory=2"],
        )

    @pytest.mark.slow
    @pytest.mark.parametrize("finding", ["warning", "module-skip", "module-error"])
    def test_collection_findings_block_before_suite_execution(
        self, cached_runner_project: Path, finding: str
    ) -> None:
        """Collect-only warnings, skips and import failures retain native evidence."""
        runner = self._runner_for(cached_runner_project)
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
        runner = self._runner_for(cached_runner_project)
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
            summary = self._summary(cached_runner_project / runner.reports).splitlines()
            for count in (
                "warnings=2",
                "suspended_warnings=2",
                "selection_warnings=1",
                "inventory_warnings=1",
                "suite_warnings=0",
            ):
                tm.that(count in summary, eq=True)
            evidence = (receipt.parent / "warnings.txt").read_text()
            tm.that(evidence.count("serial policy evidence"), eq=2)

    @pytest.mark.slow
    def test_warm_inventory_captures_warnings_from_stable_modules(
        self, cached_runner_project: Path
    ) -> None:
        """A file omitted by testmon remains covered by complete collection policy."""
        runner = self._runner_for(cached_runner_project)
        target = cached_runner_project / runner.target
        (target / "test_stable.py").write_text(
            "import os\nfrom pathlib import Path\nimport warnings\n\n"
            f"if os.environ.get({c.Infra.PYTEST_ENV_COLLECTION_MANIFEST!r}) and "
            "Path(__file__).with_name('emit-warning').exists():\n"
            "    warnings.warn('stable inventory finding', RuntimeWarning)\n\n"
            "def test_stable():\n    assert 17 == 17\n",
            encoding="utf-8",
        )
        tm.that(tm.ok(runner.execute()), eq=0)
        reports_root = cached_runner_project / runner.reports
        existing = set(reports_root.glob("*/run-context.json"))
        (target / "emit-warning").touch()

        inventory_runner = self._runner_for(cached_runner_project)
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
    def test_full_stops_at_the_first_incremental_failure(
        self, cached_runner_project: Path
    ) -> None:
        runner = self._runner_for(cached_runner_project)
        (cached_runner_project / runner.target / "test_failure.py").write_text(
            "def test_failure():\n    assert False, 'full must not follow failure'\n",
            encoding="utf-8",
        )

        tm.that(tm.ok(runner.execute_full()), eq=1)

        (context_path,) = (cached_runner_project / runner.reports).glob(
            "*/run-context.json"
        )
        context = m.Infra.PytestRunContext.model_validate_json(context_path.read_text())
        tm.that(context.execution_mode, eq="incremental")
        outcome = m.Cli.ProcessOutcome.model_validate_json(
            (context_path.parent / "suite-outcome.json").read_text()
        )
        tm.that(outcome.raw_return_code, eq=1)

    def test_full_preserves_corrupt_database_failure_before_execution(
        self, cached_runner_project: Path
    ) -> None:
        runner = self._runner_for(cached_runner_project)
        runner.testmon_db.parent.mkdir(parents=True)
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
            "import os\nfrom pathlib import Path\nfrom flext_infra import m\n\n"
            "def pytest_collection_modifyitems(config, items):\n"
            "    if config.getoption('collectonly'):\n"
            f"        target = Path(os.environ[{c.Infra.PYTEST_ENV_COLLECTION_MANIFEST!r}])\n"
            "        context = m.Infra.PytestRunContext.model_validate_json(\n"
            "            (target.parent / 'run-context.json').read_text())\n"
            "        if context.execution_mode == 'full':\n            items.clear()\n",
            encoding="utf-8",
        )
        runner = self._runner_for(cached_runner_project)

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

    @pytest.mark.slow
    def test_missing_collection_manifest_preserves_file_failure(
        self, cached_runner_project: Path
    ) -> None:
        (cached_runner_project / "conftest.py").write_text(
            "import os\nfrom pathlib import Path\n\n"
            "def pytest_sessionfinish(session):\n"
            f"    target = os.environ.get({c.Infra.PYTEST_ENV_COLLECTION_MANIFEST!r})\n"
            "    if target:\n        Path(target).unlink()\n",
            encoding="utf-8",
        )
        runner = self._runner_for(cached_runner_project)

        with pytest.raises(FileNotFoundError, match=r"testmon-selection\.json"):
            runner.execute()

    @pytest.mark.slow
    def test_coverage_pass_fails_loud_on_collection_policy_error(
        self, policy_violation_project: Path
    ) -> None:
        """The coverage pass also exits non-zero on the same policy violation."""
        runner = self._runner_for(policy_violation_project)

        exit_code = tm.ok(runner.execute_coverage())

        tm.that(exit_code, ne=0)
