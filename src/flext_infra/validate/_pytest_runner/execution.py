"""Strict process lifecycle for the canonical pytest runner."""

from __future__ import annotations

import shlex
import sys
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, override

import pytest

from flext_core import r
from flext_infra import c, config, m, t, u
from flext_infra.validate.testmon_db import FlextInfraTestmonDbInspector

from .command import FlextInfraPytestRunnerCommand
from .reports import FlextInfraPytestRunnerReports

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraPytestRunnerExecution(
    FlextInfraPytestRunnerCommand, FlextInfraPytestRunnerReports
):
    """Execute pytest once and reject incomplete evidence."""

    def _inspect_cache(
        self, *, digest: str | None
    ) -> p.Result[m.Infra.TestmonCacheState]:
        """Run the SQLite integrity owner for the external database."""
        return FlextInfraTestmonDbInspector(
            repository_root=self.root, db_path=self.testmon_db, pre_run_digest=digest
        ).execute()

    def _selection_env(self, manifest: Path | None = None) -> MutableMapping[str, str]:
        """Return the child environment shared by every runner invocation."""
        overrides = {
            c.Infra.ORCHESTRATOR_ENV_PYTHONPATH: str(
                self.root / c.Infra.DEFAULT_SRC_DIR
            ),
            c.Infra.PYTEST_ENV_TESTMON_DATAFILE: str(self.testmon_db),
        }
        if manifest is not None:
            overrides[c.Infra.PYTEST_ENV_COLLECTION_MANIFEST] = str(manifest)
        remove_keys = tuple(
            key
            for key in c.Infra.PYTEST_INHERITED_ENV_REMOVE_KEYS
            if manifest is None or key != c.Infra.PYTEST_ENV_COLLECTION_MANIFEST
        )
        return u.Cli.process_env(remove_keys=remove_keys, overrides=overrides)

    def _resolve_selection(
        self,
        report_dir: Path,
        *,
        execution_mode: c.Infra.PytestExecutionMode,
        complete: bool = False,
    ) -> t.StrSequence:
        """Return the node ids testmon selects, resolved in one process."""
        artifact = "testmon-inventory" if complete else "testmon-selection"
        selection_log = report_dir / f"{artifact}.log"
        manifest_path = report_dir / f"{artifact}.json"
        report_log = report_dir / f"{artifact}.events.jsonl"
        command = self.build_selection_command(
            report_log=report_log, complete=complete, execution_mode=execution_mode
        )
        outcome = u.Cli.run_to_file(
            command,
            selection_log,
            cwd=self.root,
            env=self._selection_env(manifest_path),
            deadline=self._process_deadline(),
        ).unwrap()
        self._record_process_outcome(
            report_dir, "inventory" if complete else "selection", outcome
        )
        log_text = selection_log.read_text(encoding="utf-8")
        # Exit code 5 is pytest's "no tests ran": testmon selected nothing.
        if (
            outcome.raw_return_code
            not in (
                {pytest.ExitCode.OK}
                if complete
                else {pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED}
            )
            or outcome.timed_out
            or outcome.forwarded_signal is not None
        ):
            detail = log_text.strip()
            msg = f"testmon selection failed ({outcome.raw_return_code}): {detail}"
            raise RuntimeError(msg)
        self._collection_diagnostics(report_log)
        manifest = m.Infra.PytestCollectionManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
        node_ids = manifest.node_ids
        if outcome.raw_return_code == pytest.ExitCode.NO_TESTS_COLLECTED and node_ids:
            msg = "pytest reported no collection with a nonempty manifest"
            raise RuntimeError(msg)
        if complete and not node_ids:
            msg = "complete pytest inventory must contain at least one test"
            raise RuntimeError(msg)
        u.Cli.atomic_write_text_file(
            report_dir / f"{artifact}.txt", "\n".join(node_ids) + "\n"
        ).unwrap()
        if not complete:
            inventory = self._resolve_selection(
                report_dir, complete=True, execution_mode=execution_mode
            )
            if not set(node_ids).issubset(inventory):
                msg = "testmon selected node IDs outside the complete collection inventory"
                raise RuntimeError(msg)
        return node_ids

    def _process_deadline(self) -> p.Cli.ProcessDeadline:
        """Use the entrypoint clock for selection, execution, and cleanup."""
        pytest_settings = config.Infra.tooling.tools.pytest
        return m.Cli.ProcessDeadline(
            expires_at_monotonic=self.started_at_monotonic
            + pytest_settings.run_timeout_seconds,
            termination_grace_seconds=pytest_settings.termination_grace_seconds,
        )

    def _run_suite(
        self, command: t.VariadicTuple[str], report_dir: Path
    ) -> p.Cli.ProcessOutcome:
        """Execute one suite argv under the shared deadline and environment."""
        u.Cli.atomic_write_text_file(
            report_dir / "command.txt", f"{shlex.join(command)}\n"
        ).unwrap()
        outcome = u.Cli.run_to_file(
            command,
            report_dir / "pytest.log",
            cwd=self.root,
            env=self._selection_env(),
            live=True,
            deadline=self._process_deadline(),
        ).unwrap()
        self._record_process_outcome(report_dir, "suite", outcome)
        return outcome

    @staticmethod
    def _record_process_outcome(
        report_dir: Path, phase: str, outcome: p.Cli.ProcessOutcome
    ) -> None:
        """Preserve the process owner's causal fields even when JUnit is absent."""
        recorded = m.Cli.ProcessOutcome.model_validate(outcome, from_attributes=True)
        receipt = report_dir / f"{phase}-outcome.json"
        u.Cli.atomic_write_text_file(
            receipt, recorded.model_dump_json(indent=2) + "\n"
        ).unwrap()
        if not u.Cli.process_succeeded(outcome):
            sys.stderr.write(
                f"pytest {phase}: raw_return_code={outcome.raw_return_code} "
                f"timed_out={outcome.timed_out} "
                f"forwarded_signal={outcome.forwarded_signal}; receipt={receipt}\n"
            )
        if outcome.raw_return_code == 0 and not u.Cli.process_succeeded(outcome):
            msg = f"pytest {phase} reported zero after an interrupted lifecycle: {receipt}"
            raise RuntimeError(msg)

    def _finalize(
        self,
        report_dir: Path,
        *,
        cache_restored: bool = False,
        raw_return_code: int = 0,
        cache_hit: bool = False,
    ) -> p.Result[int]:
        """Reject incomplete evidence and publish one bounded summary."""
        diagnostics = self._diagnostics(report_dir).unwrap()
        accounting = self._accounting(
            report_dir / "junit.xml",
            report_dir / "pytest.log",
            cache_restored=cache_restored,
            reported_count=len(diagnostics.reported_node_ids),
        ).unwrap()
        context = m.Infra.PytestRunContext.model_validate_json(
            (report_dir / "run-context.json").read_text(encoding="utf-8")
        )
        if not accounting.executed_count and not (
            cache_hit
            and context.execution_mode == c.Infra.PytestExecutionMode.INCREMENTAL
            and raw_return_code
            in {pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED}
        ):
            msg = "zero execution is accepted only for a verified incremental cache hit"
            raise RuntimeError(msg)
        if cache_hit and accounting.executed_count:
            msg = "a testmon cache hit cannot contain executed tests"
            raise RuntimeError(msg)
        phases = self._phase_diagnostics(report_dir, context=context, suite=diagnostics)
        self._write_diagnostics(report_dir, diagnostics, phases=phases)
        warnings = sum(item.warning_count for _, item in phases)
        blocking_warnings = sum(item.blocking_warning_count for _, item in phases)
        suspended_warnings = sum(item.suspended_warning_count for _, item in phases)
        accounting_complete = (
            accounting.executed_count == accounting.reported_count
            and (
                accounting.inventory_count is None
                or accounting.executed_count + accounting.deselected_count
                == accounting.inventory_count
            )
        )
        rejected = any((
            diagnostics.failed_count,
            diagnostics.error_count,
            blocking_warnings,
            diagnostics.skipped_count,
            diagnostics.collection_failed_count,
            diagnostics.collection_skipped_count,
            not accounting_complete,
        ))
        accepted_cache_hit = cache_hit and not rejected
        final_exit = 0 if accepted_cache_hit else raw_return_code or int(rejected)
        if final_exit:
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
            f"{phase}_warnings={item.warning_count}\n"
            f"{phase}_blocking_warnings={item.blocking_warning_count}\n"
            f"{phase}_suspended_warnings={item.suspended_warning_count}\n"
            for phase, item in phases
        )
        summary = (
            f"outcome={result}\n"
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
            f"blocking_warnings={blocking_warnings}\n"
            f"suspended_warnings={suspended_warnings}\n"
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
        """Execute the incremental testmon operation."""
        return self._execute_testmon(complete=False)

    def execute_full(self) -> p.Result[int]:
        """Run incremental then full under one deadline and persistent database."""
        incremental_exit = self.execute().unwrap()
        if incremental_exit:
            return r.ok(incremental_exit)
        return self._execute_testmon(complete=True)

    def _execute_testmon(self, *, complete: bool) -> p.Result[int]:
        """Execute one selected testmon phase without resetting shared state."""
        report_dir = self._report_directory()
        execution_mode = (
            c.Infra.PytestExecutionMode.FULL
            if complete
            else c.Infra.PytestExecutionMode.INCREMENTAL
        )
        self._write_run_context(
            report_dir,
            m.Infra.PytestRunContext(
                execution_mode=execution_mode,
                testmon_db=self.testmon_db,
                deadline_monotonic=self._process_deadline().expires_at_monotonic,
            ),
        )
        u.Cli.ensure_dir(self.testmon_db.parent).unwrap()
        pre_digest = FlextInfraTestmonDbInspector.digest_file(self.testmon_db)
        cache_restored = False
        if pre_digest is not None:
            pre_state = self._inspect_cache(digest=pre_digest).unwrap()
            cache_restored = pre_state.restored_accepted
            if not cache_restored:
                msg = f"testmon preflight rejected cache: {pre_state.reason}"
                raise RuntimeError(msg)
        selection = self._resolve_selection(
            report_dir, complete=complete, execution_mode=execution_mode
        )
        if not selection and not cache_restored:
            msg = "empty incremental selection requires an integrity-checked cache"
            raise RuntimeError(msg)
        # Workers execute one centrally ordered selection. The collection plugin
        # enforces that manifest for both cold and warm caches while testmon
        # continues to collect dependencies through its xdist integration.
        command = self.build_command(
            report_dir, selection, execution_mode=execution_mode
        )
        outcome = self._run_suite(command, report_dir)
        cache_hit = (
            not complete
            and outcome.raw_return_code
            in {pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED}
            and not outcome.timed_out
            and outcome.forwarded_signal is None
            and not selection
            and cache_restored
        )
        completed_failure = (
            outcome.raw_return_code == pytest.ExitCode.TESTS_FAILED
            and not outcome.timed_out
            and outcome.forwarded_signal is None
        )
        if (
            not u.Cli.process_succeeded(outcome)
            and not cache_hit
            and not completed_failure
        ):
            return r.ok(outcome.raw_return_code)
        state = self._inspect_cache(digest=pre_digest).unwrap()
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
        """
        report_dir = self._report_directory()
        self._write_run_context(
            report_dir,
            m.Infra.PytestRunContext(
                execution_mode=c.Infra.PytestExecutionMode.COVERAGE,
                testmon_db=None,
                deadline_monotonic=self._process_deadline().expires_at_monotonic,
            ),
        )
        command = self.build_coverage_command(report_dir)
        outcome = self._run_suite(command, report_dir)
        if not u.Cli.process_succeeded(outcome):
            return r.ok(outcome.raw_return_code)
        self._validate_coverage(report_dir).unwrap()
        return self._finalize(report_dir)


__all__: list[str] = ["FlextInfraPytestRunnerExecution"]
