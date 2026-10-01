"""Public complete-suite pytest runtime contracts."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m
from tests.fixtures.pytest_runner import PytestRunnerContract


class TestsFlextInfraPytestRunnerFull(PytestRunnerContract):
    """Exercise complete-suite execution and prerequisite failures."""

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
        runner = self.runner_for(cached_runner_project, ci_context=ci_context)
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
        baseline = self.runner_for(cached_runner_project)
        tm.that(tm.ok(baseline.execute()), eq=0)
        reports_root = cached_runner_project / baseline.reports
        existing = set(reports_root.glob("*/run-context.json"))
        runner = self.runner_for(cached_runner_project)

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
                + runner.run_timeout_seconds(config.Infra.tooling.tools.pytest)
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
    def test_full_stops_at_the_first_incremental_failure(
        self, cached_runner_project: Path
    ) -> None:
        runner = self.runner_for(cached_runner_project)
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
        runner = self.runner_for(cached_runner_project)
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
        runner = self.runner_for(cached_runner_project)

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
