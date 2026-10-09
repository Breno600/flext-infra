"""Single-file pytest target contract.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, m
from tests import c, t, u
from tests.unit.validate.pytest_runner_support import runner_for, summary


@pytest.mark.unit
class TestsFlextInfraPytestTargetFile:
    """A declared file replaces the suite directory as the only node target."""

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.remote
    @pytest.mark.parametrize(
        ("budgeted", "slow", "failure"),
        [
            (True, False, ""),
            (False, True, ""),
            (True, True, ""),
            (False, False, ""),
            (True, True, "budgeted"),
            (True, True, "slow"),
            (True, True, "collection"),
        ],
    )
    def test_public_make_runs_requested_file_phases(
        provisioned_infra_checkout: t.Pair[str, Path],
        *,
        budgeted: bool,
        slow: bool,
        failure: str,
    ) -> None:
        """Native Make runs both scopes, preserves failures and rejects zero-run."""
        _, root = provisioned_infra_checkout
        generated = tm.ok(u.Tests.run_isolated_make(["gen"], cwd=root))
        tm.that(
            u.Cli.process_succeeded(generated.outcome),
            eq=True,
            msg=generated.stdout + generated.stderr,
        )
        make = config.Infra.codegen.make
        cache = make.testmon_cache
        probe = f"file_phase_probe_{budgeted}_{slow}_{failure or 'passed'}"
        filename = config.Infra.tooling.tools.pytest.python_files[0].replace("*", probe)
        relative = Path(cache.target_directory) / filename
        proof = root / f"{probe}.log"
        source, expected = TestsFlextInfraPytestTargetFile._probe_source(
            proof,
            budgeted=budgeted,
            slow=slow,
            failure=failure,
        )
        (root / relative).write_text(source, encoding=c.Infra.ENCODING_DEFAULT)
        # An unrelated failing module proves FILE remains the complete scope.
        (root / relative.with_name(filename.replace("probe", "unrelated"))).write_text(
            "def test_unrelated() -> None:\n    assert False\n",
            encoding=c.Infra.ENCODING_DEFAULT,
        )
        reports = root / cache.reports_directory
        before = set(reports.glob("*/run-context.json"))
        process = tm.ok(
            u.Tests.run_isolated_make(
                ["test-file", f"FILE={relative.as_posix()}"],
                cwd=root,
                env={make.ci.variable: make.ci.local_value},
            ),
        )
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=bool(expected) and not failure,
            msg=process.stdout + process.stderr,
        )
        tm.that(
            proof.read_text().splitlines() if proof.exists() else [],
            eq=expected,
        )
        receipts = [
            m.Infra.PytestRunContext.model_validate_json(path.read_text())
            for path in sorted(
                set(reports.glob("*/run-context.json")) - before,
                key=lambda path: path.stat().st_mtime_ns,
            )
        ]
        tm.that(len(receipts), eq=1 if failure in {"budgeted", "collection"} else 2)
        tm.that(len({receipt.testmon_db for receipt in receipts}), eq=1)
        if len(receipts) == 2:
            tm.that(receipts[0].deadline_monotonic, ne=receipts[1].deadline_monotonic)
        if not budgeted and not slow:
            tm.that(process.stderr, has="test-file executed zero requested tests")
        if expected and not failure:
            TestsFlextInfraPytestTargetFile._assert_rerun_executes_again(
                root,
                relative,
                proof,
                expected,
            )

    @staticmethod
    def _probe_source(
        proof: Path,
        *,
        budgeted: bool,
        slow: bool,
        failure: str,
    ) -> t.Pair[str, list[str]]:
        """Render the probe module and the phases it must record.

        Returns:
            The probe module source and the phases it must record, in order.

        """
        slow_marker = config.Infra.tooling.tools.pytest.slow_marker
        source = "import pytest\nfrom pathlib import Path\n\n"
        if failure == "collection":
            source += "raise RuntimeError('file-phase-collection-failure')\n"
        expected: list[str] = []
        for phase, enabled in (("budgeted", budgeted), ("slow", slow)):
            if not enabled:
                continue
            if phase == "slow":
                source += f"@pytest.mark.{slow_marker}\n"
            source += (
                f"def test_{phase}() -> None:\n"
                f"    with Path({str(proof)!r}).open('a') as stream:\n"
                f"        stream.write('{phase}\\n')\n"
                + ("    assert False\n" if failure == phase else "")
                + "\n"
            )
            if failure not in {"collection", "budgeted"} or (
                failure == "budgeted" and phase == "budgeted"
            ):
                expected.append(phase)
        return source, expected

    @staticmethod
    def _assert_rerun_executes_again(
        root: Path,
        relative: Path,
        proof: Path,
        expected: list[str],
    ) -> None:
        """A green declared file reruns through Make and records every phase."""
        make = config.Infra.codegen.make
        repeated = tm.ok(
            u.Tests.run_isolated_make(
                ["test-file", f"FILE={relative.as_posix()}"],
                cwd=root,
                env={make.ci.variable: make.ci.local_value},
            ),
        )
        tm.that(
            u.Cli.process_succeeded(repeated.outcome),
            eq=True,
            msg=repeated.stdout + repeated.stderr,
        )
        tm.that(
            proof.read_text(encoding=c.Infra.ENCODING_DEFAULT).splitlines(),
            eq=expected * 2,
        )

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
    def test_declared_file_edit_reruns_the_complete_file(
        cached_runner_project: Path,
    ) -> None:
        """A partly edited declared file stays green and runs every test.

        A declared file always executes under noselect: the cache never
        narrows the operator's chosen scope, so an edit touching one test
        still runs both tests of the file.
        """
        cache = config.Infra.codegen.make.testmon_cache
        relative = Path(cache.target_directory) / "partial_case.py"
        declared = cached_runner_project / relative
        kept = "def test_kept() -> None:\n    return None\n\n\n"
        for value in (1, 2):
            declared.write_text(
                kept + f"def test_edited() -> None:\n    assert {value}\n",
                encoding="utf-8",
            )
            runner = runner_for(cached_runner_project, target_file=relative)
            tm.that(tm.ok(runner.execute()), eq=pytest.ExitCode.OK.value)
            report = summary(cached_runner_project / cache.reports_directory)
            tm.that(report, has="executed=2\n")
