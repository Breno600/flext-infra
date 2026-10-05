"""Strict process lifecycle for the canonical pytest runner.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shlex
import sys
import time
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, override

import pytest

from flext_core import r
from flext_infra import c, config, m, t, u
from flext_infra.validate._pytest_runner.command import FlextInfraPytestRunnerCommand
from flext_infra.validate._pytest_runner.reports import FlextInfraPytestRunnerReports
from flext_infra.validate.testmon_db import FlextInfraTestmonDbInspector

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraPytestRunnerExecution(
    FlextInfraPytestRunnerCommand,
    FlextInfraPytestRunnerReports,
):
    """Execute pytest once and reject incomplete evidence."""

    def _inspect_cache(
        self,
        *,
        digest: str | None,
    ) -> p.Result[m.Infra.TestmonCacheState]:
        """Run the SQLite integrity owner for the testmon database.

        Returns:
            The resulting ``p.Result[m.Infra.TestmonCacheState]``.

        """
        return FlextInfraTestmonDbInspector(
            repository_root=self.root,
            db_path=self.testmon_db,
            pre_run_digest=digest,
        ).execute()

    def _selection_env(
        self,
        *,
        execution_mode: c.Infra.PytestExecutionMode,
    ) -> MutableMapping[str, str]:
        """Return the child environment shared by every runner invocation.

        The coverage verb owns no testmon plugin, so its children neither
        receive nor inherit a testmon database location.

        Returns:
            The child environment shared by every runner invocation.

        """
        testmon_keys = (
            config.Infra.codegen.make.testmon_cache.database_environment_variable,
            c.Infra.PYTEST_ENV_TESTMON_DATAFILE,
        )
        coverage = execution_mode == c.Infra.PytestExecutionMode.COVERAGE
        overrides = {
            c.Infra.ORCHESTRATOR_ENV_PYTHONPATH: str(
                self.root / c.Infra.DEFAULT_SRC_DIR,
            ),
        }
        if not coverage:
            overrides.update(dict.fromkeys(testmon_keys, str(self.testmon_db)))
        remove_keys = (
            *c.Infra.PYTEST_INHERITED_ENV_REMOVE_KEYS,
            *(testmon_keys if coverage else ()),
        )
        return u.Cli.process_env(remove_keys=remove_keys, overrides=overrides)

    def _resolve_selection(
        self,
        report_dir: Path,
        *,
        execution_mode: c.Infra.PytestExecutionMode,
        complete: bool = False,
        verify_inventory: bool = True,
    ) -> m.Infra.PytestSelectionPlan:
        """Return the typed testmon selection and its manifest owner.

        Each collection is one deadline-bound child of the flext-cli process
        owner, which runs deadline processes on the main interpreter thread
        only; the selection and the complete inventory therefore run in order.

        Returns:
            The typed testmon selection and its manifest owner.

        Raises:
            RuntimeError: If testmon selected node IDs outside the complete collection
                inventory.

        """
        selection = self._collect_selection(
            report_dir,
            complete=complete,
            execution_mode=execution_mode,
        )
        if complete or not verify_inventory:
            return selection
        inventory = self._collect_selection(
            report_dir,
            complete=True,
            execution_mode=execution_mode,
        )
        if inventory.owns_no_tests:
            return inventory
        if not set(selection.node_ids).issubset(inventory.node_ids):
            msg = "testmon selected node IDs outside the complete collection inventory"
            raise RuntimeError(msg)
        return selection.model_copy(
            update={
                "whole_target": selection.node_ids == inventory.node_ids,
                "inventory_collected": True,
            },
        )

    def _collect_selection(
        self,
        report_dir: Path,
        *,
        execution_mode: c.Infra.PytestExecutionMode,
        complete: bool,
    ) -> m.Infra.PytestSelectionPlan:
        """Run one read-only collection and publish its manifest artifacts.

        Returns:
            The selection plan of the published manifest.

        Raises:
            RuntimeError: If the collection exits with an unaccepted code, times
                out or is signalled; if pytest reports no collection with a
                nonempty manifest; or if a complete inventory outside the slow
                phase holds no test.

        """
        artifact = "testmon-inventory" if complete else "testmon-selection"
        selection_log = report_dir / f"{artifact}.log"
        manifest_path = report_dir / f"{artifact}.json"
        report_log = report_dir / f"{artifact}.events.jsonl"
        command = self.build_selection_command(
            report_log=report_log,
            manifest_path=manifest_path,
            complete=complete,
            execution_mode=execution_mode,
        )
        if self.collection_command_prefix:
            sys.stdout.write(
                f"pytest {artifact} profile: {manifest_path.with_suffix('.pstats')}\n",
            )
        outcome = u.Cli.run_to_file(
            command,
            selection_log,
            cwd=self.root,
            env=self._selection_env(execution_mode=execution_mode),
            deadline=self._process_deadline(),
        ).unwrap()
        self._record_process_outcome(
            report_dir,
            "inventory" if complete else "selection",
            outcome,
        )
        log_text = selection_log.read_text(encoding="utf-8")
        # Exit code 5 is pytest's "no tests ran": testmon selected nothing.
        # For a zero-test project (no test module under the config-owned
        # roots) rc=5 is the DECLARED inventory outcome in both phases.
        owns_no_tests = self._owns_no_tests()
        # A slow phase may own no slow item, and a declared file may sit
        # entirely outside this phase's marker. Both are empty scopes. A
        # whole-suite budgeted inventory that collects nothing stays a failure.
        scope_may_be_empty = self.slow_phase or self.target_file is not None
        accepted = {pytest.ExitCode.OK} | (
            set()
            if complete and not scope_may_be_empty
            else {pytest.ExitCode.NO_TESTS_COLLECTED}
        )
        if owns_no_tests:
            accepted = {pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED}
        if (
            outcome.raw_return_code not in accepted
            or outcome.timed_out
            or outcome.forwarded_signal is not None
        ):
            detail = log_text.strip()
            msg = f"testmon selection failed ({outcome.raw_return_code}): {detail}"
            raise RuntimeError(msg)
        if self.collection_command_prefix:
            self._bind_child_profile(report_dir, manifest_path.with_suffix(".pstats"))
        if not owns_no_tests:
            self._collection_diagnostics(report_log)
        if (
            owns_no_tests
            and outcome.raw_return_code == pytest.ExitCode.NO_TESTS_COLLECTED
        ):
            # No manifest artifact is produced for an empty declared suite.
            return m.Infra.PytestSelectionPlan(
                manifest_path=manifest_path,
                node_ids=(),
                whole_target=True,
                inventory_collected=complete,
                owns_no_tests=True,
            )
        manifest = m.Infra.PytestCollectionManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8"),
        )
        node_ids = manifest.node_ids
        if outcome.raw_return_code == pytest.ExitCode.NO_TESTS_COLLECTED and node_ids:
            msg = "pytest reported no collection with a nonempty manifest"
            raise RuntimeError(msg)
        if complete and not node_ids and not owns_no_tests and not scope_may_be_empty:
            msg = "complete pytest inventory must contain at least one test"
            raise RuntimeError(msg)
        # An empty complete inventory in an allowed scope owns no in-scope
        # test. Collection diagnostics already ran, so a collection failure
        # never becomes this receipt.
        owns_no_tests = owns_no_tests or (
            complete and not node_ids and scope_may_be_empty
        )
        u.Cli.atomic_write_text_file(
            report_dir / f"{artifact}.txt",
            "\n".join(node_ids) + "\n",
        ).unwrap()
        return m.Infra.PytestSelectionPlan(
            manifest_path=manifest_path,
            node_ids=node_ids,
            whole_target=True,
            inventory_collected=complete,
            owns_no_tests=owns_no_tests,
        )

    def _owns_no_tests(self) -> bool:
        """Return whether the project owns zero test files by design.

        The config-owned collection roots (``pytest.test-paths`` SSOT) contain
        no test module at all: an empty suite is the declared topology (a
        content-only workspace shell), not a broken collection. A project that
        DOES own test files but collects nothing keeps the loud failure —
        zero-execution of an existing suite is never a silent pass (law 14).

        Returns:
            Whether the project owns zero test files by design.

        """
        pytest_settings = config.Infra.tooling.tools.pytest
        # The module patterns are the pytest SSOT's own python-files: a
        # project whose suites use another declared form (``*_tests.py``)
        # still owns its tests, and a hardcoded copy of the list here would
        # answer "owns no tests" for a live suite again.
        patterns = pytest_settings.python_files
        for root in pytest_settings.test_paths:
            base = self.root / root
            if not base.is_dir():
                continue
            for pattern in patterns:
                if any(base.rglob(pattern)):
                    return False
        return True

    def _process_deadline(self) -> p.Cli.ProcessDeadline:
        """Use the entrypoint clock for selection, execution, and cleanup.

        Returns:
            The resulting ``p.Cli.ProcessDeadline``.

        """
        pytest_settings = config.Infra.tooling.tools.pytest
        return m.Cli.ProcessDeadline(
            expires_at_monotonic=self.started_at_monotonic
            + self.run_timeout_seconds(pytest_settings),
            termination_grace_seconds=pytest_settings.termination_grace_seconds,
        )

    def _run_suite(
        self,
        command: t.VariadicTuple[str],
        report_dir: Path,
        *,
        execution_mode: c.Infra.PytestExecutionMode,
    ) -> p.Cli.ProcessOutcome:
        """Execute one suite argv under the shared deadline and environment.

        Returns:
            The resulting ``p.Cli.ProcessOutcome``.

        """
        u.Cli.atomic_write_text_file(
            report_dir / "command.txt",
            f"{shlex.join(command)}\n",
        ).unwrap()
        outcome = u.Cli.run_to_file(
            command,
            report_dir / "pytest.log",
            cwd=self.root,
            env=self._selection_env(execution_mode=execution_mode),
            live=True,
            deadline=self._process_deadline(),
        ).unwrap()
        self._record_process_outcome(report_dir, "suite", outcome)
        return outcome

    @staticmethod
    def _record_process_outcome(
        report_dir: Path,
        phase: str,
        outcome: p.Cli.ProcessOutcome,
    ) -> None:
        """Preserve the process owner's causal fields even when JUnit is absent.

        Raises:
            RuntimeError: If pytest.

        """
        recorded = m.Cli.ProcessOutcome.model_validate(outcome, from_attributes=True)
        receipt = report_dir / f"{phase}-outcome.json"
        u.Cli.atomic_write_text_file(
            receipt,
            recorded.model_dump_json(indent=2) + "\n",
        ).unwrap()
        if not u.Cli.process_succeeded(outcome):
            sys.stderr.write(
                f"pytest {phase}: raw_return_code={outcome.raw_return_code} "
                f"timed_out={outcome.timed_out} "
                f"forwarded_signal={outcome.forwarded_signal}; receipt={receipt}\n",
            )
        if outcome.raw_return_code == 0 and not u.Cli.process_succeeded(outcome):
            msg = (
                f"pytest {phase} reported zero after an interrupted "
                f"lifecycle: {receipt}"
            )
            raise RuntimeError(msg)

    @staticmethod
    def _completed_failure(outcome: p.Cli.ProcessOutcome) -> bool:
        """Return whether a failing suite still finished its lifecycle.

        Under xdist the declared max-failures stop exits as Interrupted, not
        TestsFailed; it is still one completed suite lifecycle whose bounded
        evidence must be published. An operator signal keeps forwarded_signal
        set and never qualifies.

        Returns:
            Whether a failing suite still finished its lifecycle.

        """
        return (
            outcome.raw_return_code
            in {pytest.ExitCode.TESTS_FAILED, pytest.ExitCode.INTERRUPTED}
            and not outcome.timed_out
            and outcome.forwarded_signal is None
        )

    @staticmethod
    def _record_cache_state(
        report_dir: Path,
        name: str,
        state: m.Infra.TestmonCacheState,
    ) -> None:
        """Persist one testmon integrity decision before it is acted upon."""
        u.Cli.atomic_write_text_file(
            report_dir / f"{name}.json",
            state.model_dump_json(indent=2) + "\n",
        ).unwrap()

    def _finalize(
        self,
        report_dir: Path,
        *,
        cache_restored: bool = False,
        raw_return_code: int = 0,
        cache_hit: bool = False,
    ) -> p.Result[int]:
        """Reject incomplete evidence and publish one bounded summary.

        Returns:
            The resulting ``p.Result[int]``.

        Raises:
            RuntimeError: If zero execution is accepted only for a verified incremental
                cache hit; or if a testmon cache hit cannot contain executed tests.

        """
        diagnostics = self._diagnostics(report_dir).unwrap()
        accounting = self._accounting(
            report_dir / "junit.xml",
            report_dir / "pytest.log",
            cache_restored=cache_restored,
            reported_count=len(diagnostics.reported_node_ids),
        ).unwrap()
        context = m.Infra.PytestRunContext.model_validate_json(
            (report_dir / "run-context.json").read_text(encoding="utf-8"),
        )
        # The zero-test receipt travels on the typed accounting the reports
        # owner parsed from the durable selection plan.
        if (
            not accounting.executed_count
            and not accounting.owns_no_tests
            and not (
                cache_hit
                and context.execution_mode == c.Infra.PytestExecutionMode.INCREMENTAL
                and raw_return_code
                in {pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED}
            )
        ):
            msg = "zero execution is accepted only for a verified incremental cache hit"
            raise RuntimeError(msg)
        if cache_hit and accounting.executed_count:
            msg = "a testmon cache hit cannot contain executed tests"
            raise RuntimeError(msg)
        phases = self._phase_diagnostics(report_dir, context=context, suite=diagnostics)
        self._write_diagnostics(report_dir, diagnostics, phases=phases)
        warnings = sum(item.warning_count for _, item in phases)
        accounting_complete = (
            accounting.executed_count == accounting.reported_count
            and (
                accounting.inventory_count is None
                or accounting.executed_count + accounting.deselected_count
                == accounting.inventory_count
            )
        )
        markdown_complete = (
            True
            if context.execution_mode == c.Infra.PytestExecutionMode.COVERAGE
            else self._reconcile_markdown(
                report_dir,
                diagnostics,
                cache_hit=cache_hit,
            )
        )
        rejected = any((
            diagnostics.failed_count,
            diagnostics.error_count,
            warnings,
            diagnostics.skipped_count,
            diagnostics.collection_failed_count,
            diagnostics.collection_skipped_count,
            not accounting_complete,
            not markdown_complete,
        ))
        accepted_cache_hit = cache_hit and not rejected
        # The zero-test receipt exits green: the suite owns nothing to execute
        # and the run published its typed accounting.
        accepted_zero_tests = accounting.owns_no_tests and not rejected
        selected_count = (
            None
            if accounting.inventory_count is None
            else accounting.inventory_count - accounting.deselected_count
        )
        final_exit = (
            0
            if (accepted_cache_hit or accepted_zero_tests)
            else raw_return_code or int(rejected)
        )
        # A graceful stop at the suite stop instant publishes the executed
        # prefix and remains red: the unexecuted remainder is the next run's
        # testmon selection.
        incomplete = (
            selected_count is not None
            and accounting.executed_count < selected_count
            and not (diagnostics.failed_count or diagnostics.error_count)
        )
        if final_exit and incomplete:
            result = "incomplete"
        elif final_exit:
            result = "failed"
        elif accepted_cache_hit:
            result = "cache_hit"
        else:
            result = "executed"
        external_gates = (
            ""
            if context.execution_mode == c.Infra.PytestExecutionMode.FULL
            else ",".join(config.Infra.tooling.tools.pytest.external_gate_markers)
        )
        ci_excluded = self.ci_excluded_markers(execution_mode=context.execution_mode)
        phase_counts = "".join(
            f"{phase}_warnings={item.warning_count}\n" for phase, item in phases
        )
        summary = (
            f"outcome={result}\n"
            f"selected={selected_count}\n"
            f"executed={accounting.executed_count}\n"
            f"reported={accounting.reported_count}\n"
            f"accounting_complete={accounting_complete}\n"
            f"deselected={accounting.deselected_count}\n"
            f"inventory={accounting.inventory_count}\n"
            f"not_executed_external_gates={external_gates}\n"
            f"not_executed_ci_markers={','.join(ci_excluded)}\n"
            f"cache_restored={cache_restored}\n"
            f"failed={diagnostics.failed_count}\nerrors={diagnostics.error_count}\n"
            f"warnings={warnings}\n"
            f"{phase_counts}"
            f"skipped={diagnostics.skipped_count}\n"
            f"collection_errors={diagnostics.collection_failed_count}\n"
            f"collection_skips={diagnostics.collection_skipped_count}\n"
            f"exit={final_exit}\n"
        )
        u.Cli.atomic_write_text_file(
            report_dir / "run-accounting.json",
            accounting.model_dump_json(indent=2) + "\n",
        ).unwrap()
        u.Cli.atomic_write_text_file(report_dir / "summary.txt", summary).unwrap()
        sys.stderr.write(f"Reports: {report_dir}\n")
        return r.ok(final_exit)

    @override
    def execute(self) -> p.Result[int]:
        """Execute the incremental testmon operation.

        Returns:
            The resulting ``p.Result[int]``.

        """
        return self._execute_testmon(complete=False)

    def execute_full(self) -> p.Result[int]:
        """Run incremental then full under one deadline and persistent database.

        Returns:
            The resulting ``p.Result[int]``.

        """
        incremental_exit = self.execute().unwrap()
        if incremental_exit:
            return r.ok(incremental_exit)
        return self._execute_testmon(complete=True)

    def _execute_testmon(self, *, complete: bool) -> p.Result[int]:
        """Execute one selected testmon phase without resetting shared state.

        Returns:
            The resulting ``p.Result[int]``.

        """
        execution_mode = (
            c.Infra.PytestExecutionMode.FULL
            if complete
            else c.Infra.PytestExecutionMode.INCREMENTAL
        )
        slow_marker = config.Infra.tooling.tools.pytest.slow_marker
        if self.slow_phase and slow_marker in self.ci_excluded_markers(
            execution_mode=execution_mode,
        ):
            # The CI context deselects the slow marker by declaration, so its
            # phase is typed NOT EXECUTED here, never a selection of nothing.
            sys.stderr.write(
                f"pytest slow phase NOT EXECUTED: ci-excluded-markers declares "
                f"{slow_marker!r}\n",
            )
            return r.ok(0)
        u.Cli.ensure_dir(self.testmon_db.parent).unwrap()
        # Selection, execution, and integrity inspection share one database.
        # Serialize competing worktrees within this invocation's typed deadline.
        deadline = self._process_deadline()
        wait_seconds = max(
            0.0,
            deadline.expires_at_monotonic
            - deadline.termination_grace_seconds
            - time.monotonic(),
        )
        with u.Infra.codegen_transaction_lease(
            self.testmon_db,
            wait_seconds=wait_seconds,
        ):
            return self._execute_testmon_leased(
                complete=complete,
                execution_mode=execution_mode,
            )

    def _execute_testmon_leased(
        self,
        *,
        complete: bool,
        execution_mode: c.Infra.PytestExecutionMode,
    ) -> p.Result[int]:
        """Run one testmon phase while holding the database lease.

        Returns:
            The resulting ``p.Result[int]``.

        Raises:
            RuntimeError: If empty incremental selection requires an integrity-checked
                cache; or if testmon cache is unusable; or if testmon preflight rejected
                cache.

        """
        report_dir = self._report_directory()
        self._write_run_context(
            report_dir,
            m.Infra.PytestRunContext(
                execution_mode=execution_mode,
                testmon_db=self.testmon_db,
                deadline_monotonic=self._process_deadline().expires_at_monotonic,
                report_directory=report_dir,
            ),
        )
        pre_digest = FlextInfraTestmonDbInspector.digest_file(self.testmon_db)
        cache_restored = False
        if pre_digest is not None:
            pre_state = self._inspect_cache(digest=pre_digest).unwrap()
            self._record_cache_state(report_dir, "cache-before", pre_state)
            cache_restored = pre_state.restored_accepted
            if not cache_restored:
                msg = f"testmon preflight rejected cache: {pre_state.reason}"
                raise RuntimeError(msg)
        selection_plan = self._resolve_selection(
            report_dir,
            complete=complete,
            # The slow phase and a declared file always prove their inventory,
            # so a scope with no matching item reaches the zero-test receipt
            # even on a cold cache.
            verify_inventory=(
                pre_digest is not None
                or self.slow_phase
                or self.target_file is not None
            ),
            execution_mode=execution_mode,
        )
        u.Cli.atomic_write_text_file(
            report_dir / "selection-plan.json",
            selection_plan.model_dump_json(indent=2) + "\n",
        ).unwrap()
        selection = selection_plan.node_ids
        # A declared file whose inventory was collected still runs: testmon may
        # select nothing for a file that has in-scope tests, and noselect
        # executes that file. An empty scope is owns_no_tests and is not this
        # guard. A suite with no proved inventory stays a failure.
        if (
            not selection
            and not cache_restored
            and not selection_plan.owns_no_tests
            and not (
                self.target_file is not None and selection_plan.inventory_collected
            )
        ):
            msg = "empty incremental selection requires an integrity-checked cache"
            raise RuntimeError(msg)
        # Workers execute one centrally ordered selection. The collection plugin
        # enforces that manifest for both cold and warm caches while testmon
        # continues to collect dependencies through its xdist integration.
        command = self.build_command(
            report_dir,
            selection_plan,
            execution_mode=execution_mode,
        )
        outcome = self._run_suite(command, report_dir, execution_mode=execution_mode)
        # A declared file always executes under noselect, so an empty testmon
        # selection over a restored cache is never a cache hit for it.
        cache_hit = (
            self.target_file is None
            and not complete
            and outcome.raw_return_code
            in {pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED}
            and not outcome.timed_out
            and outcome.forwarded_signal is None
            and not selection
            and cache_restored
        )
        # A zero-test project (empty suite by declared design) completes its
        # lifecycle with pytest's NO_TESTS_COLLECTED: the run must reach the
        # finalizer so the typed receipt is published instead of a bare rc=5.
        completed_zero_tests = (
            selection_plan.owns_no_tests
            and outcome.raw_return_code
            in {pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED}
            and not outcome.timed_out
            and outcome.forwarded_signal is None
        )
        if (
            not u.Cli.process_succeeded(outcome)
            and not cache_hit
            and not completed_zero_tests
            and not self._completed_failure(outcome)
        ):
            return r.ok(outcome.raw_return_code)
        state = self._inspect_cache(digest=pre_digest).unwrap()
        self._record_cache_state(report_dir, "cache-after", state)
        policy = config.Infra.codegen.make.testmon_cache_policy
        if not policy.save_enabled:
            self._record_cache_state(report_dir, "cache-policy", state)
        if not state.restored_accepted and not state.saveable:
            msg = f"testmon cache is unusable: {state.reason}"
            raise RuntimeError(msg)
        return self._finalize(
            report_dir,
            cache_restored=cache_restored,
            raw_return_code=outcome.raw_return_code,
            cache_hit=cache_hit,
        )

    def execute_coverage(self) -> p.Result[int]:
        """Execute the whole suite under the coverage plugin (never testmon).

        testmon 2.x refuses branch coverage through the cov plugin, so the
        coverage pass is its own process: no selection pass, no cache traffic.
        The coverage artifact is validated here; coverage is reported, never gated.
        A completed failing suite writes no coverage artifact but still
        publishes its accounting and diagnostics with the original exit code.

        Returns:
            The resulting ``p.Result[int]``.

        """
        report_dir = self._report_directory()
        self._write_run_context(
            report_dir,
            m.Infra.PytestRunContext(
                execution_mode=c.Infra.PytestExecutionMode.COVERAGE,
                testmon_db=None,
                deadline_monotonic=self._process_deadline().expires_at_monotonic,
                report_directory=report_dir,
            ),
        )
        # The inventory pass enforces the same collection policy before coverage.
        self._resolve_selection(
            report_dir,
            complete=True,
            execution_mode=c.Infra.PytestExecutionMode.COVERAGE,
            verify_inventory=False,
        )
        command = self.build_coverage_command(report_dir)
        outcome = self._run_suite(
            command,
            report_dir,
            execution_mode=c.Infra.PytestExecutionMode.COVERAGE,
        )
        if self._completed_failure(outcome):
            return self._finalize(report_dir, raw_return_code=outcome.raw_return_code)
        if not u.Cli.process_succeeded(outcome):
            return r.ok(outcome.raw_return_code)
        self._validate_coverage(report_dir).unwrap()
        return self._finalize(report_dir)


__all__: list[str] = ["FlextInfraPytestRunnerExecution"]
