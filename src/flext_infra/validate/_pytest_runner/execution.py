"""Strict process lifecycle for the canonical pytest runner."""

from __future__ import annotations

import shlex
import sys
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal, override

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

    def _selection_env(self) -> MutableMapping[str, str]:
        """Return the child environment shared by every runner invocation."""
        return u.Cli.process_env(
            remove_keys=c.Infra.PYTEST_INHERITED_ENV_REMOVE_KEYS,
            overrides={
                c.Infra.ORCHESTRATOR_ENV_PYTHONPATH: str(
                    self.root / c.Infra.DEFAULT_SRC_DIR
                ),
                c.Infra.PYTEST_ENV_TESTMON_DATAFILE: str(self.testmon_db),
            },
        )

    def _resolve_selection(
        self, report_dir: Path, *, complete: bool = False, coverage: bool = False
    ) -> t.StrSequence:
        """Return the node ids testmon selects, resolved in one process."""
        pytest_settings = config.Infra.tooling.tools.pytest
        command = self.build_selection_command(
            complete=complete, coverage=coverage, report_dir=report_dir
        )
        artifact = "testmon-inventory" if complete else "testmon-selection"
        log = report_dir / f"{artifact}.log"
        outcome = u.Cli.run_to_file(
            command,
            log,
            cwd=self.root,
            deadline=m.Cli.ProcessDeadline(
                expires_at_monotonic=self.started_at_monotonic
                + pytest_settings.run_timeout_seconds,
                termination_grace_seconds=pytest_settings.termination_grace_seconds,
            ),
            env=self._selection_env(),
        ).unwrap()
        self._record_process_outcome(
            report_dir, "inventory" if complete else "selection", outcome
        )
        # Exit code 5 is pytest's "no tests ran": testmon selected nothing.
        if (
            outcome.raw_return_code not in {0, 5}
            or outcome.timed_out
            or outcome.forwarded_signal is not None
        ):
            detail = log.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            msg = f"testmon selection failed ({outcome.raw_return_code}): {detail}"
            raise RuntimeError(msg)
        node_ids = tuple(
            line.strip()
            for line in log.read_text(encoding=c.Cli.ENCODING_DEFAULT).splitlines()
            if "::" in line and not line.startswith(" ")
        )
        u.Cli.atomic_write_text_file(
            report_dir / f"{artifact}.txt", "\n".join(node_ids) + "\n"
        ).unwrap()
        if len(node_ids) != len(set(node_ids)) or (complete and not node_ids):
            details = "\n".join(self._collection_skip_lines(report_dir))
            msg_0 = f"invalid pytest inventory: {log}\n{details}"
            raise ValueError(msg_0)
        return node_ids

    def _run_suite(
        self, command: t.VariadicTuple[str], report_dir: Path
    ) -> p.Cli.ProcessOutcome:
        """Execute one suite argv under the shared deadline and environment."""
        pytest_settings = config.Infra.tooling.tools.pytest
        u.Cli.atomic_write_text_file(
            report_dir / "command.txt", f"{shlex.join(command)}\n"
        ).unwrap()
        deadline = m.Cli.ProcessDeadline(
            expires_at_monotonic=self.started_at_monotonic
            + pytest_settings.run_timeout_seconds,
            termination_grace_seconds=pytest_settings.termination_grace_seconds,
        )
        outcome = u.Cli.run_to_file(
            command,
            report_dir / "pytest.log",
            cwd=self.root,
            env=self._selection_env(),
            live=True,
            deadline=deadline,
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
        mode: Literal["incremental", "full", "coverage"],
        inventory: t.StrSequence,
        selected: t.StrSequence,
        cache_restored: bool = False,
        raw_return_code: int = 0,
    ) -> p.Result[int]:
        """Reject incomplete evidence and publish one bounded summary."""
        cache_hit = mode == "incremental" and not selected
        accounting = (
            m.Infra.TestmonRunAccounting(
                mode=mode,
                cache_hit=True,
                inventory=tuple(inventory),
                deselected=tuple(inventory),
                database=str(self.testmon_db),
                executed_count=0,
                deselected_count=len(inventory),
                cache_restored=cache_restored,
            )
            if cache_hit
            else self._accounting(
                report_dir / "junit.xml",
                report_dir / "pytest.log",
                cache_restored=cache_restored,
                mode=mode,
                inventory=inventory,
                selected=selected,
            ).unwrap()
        )
        warnings = self._warning_events(report_dir)
        diagnostics = (
            self._complete_diagnostics(
                report_dir,
                m.Infra.PytestDiagnostics(
                    failed_count=0, error_count=0, skipped_count=0, warning_count=0
                ),
            )
            if cache_hit
            else self._diagnostics(report_dir).unwrap()
        )
        suspended_warnings = sum(self._warning_suspended(event) for event in warnings)
        u.Cli.atomic_write_text_file(
            report_dir / "accounting.json", accounting.model_dump_json(indent=2) + "\n"
        ).unwrap()
        self._write_diagnostics(report_dir, diagnostics)
        rejected = any((
            diagnostics.failed_count,
            diagnostics.error_count,
            diagnostics.warning_count - suspended_warnings,
            diagnostics.skipped_count,
        ))
        final_exit = raw_return_code or int(rejected)
        external_gates = ",".join(
            config.Infra.tooling.tools.pytest.external_gate_markers
        )
        summary = (
            f"mode={mode}\nresult={'cache_hit' if cache_hit else 'executed'}\n"
            f"executed={accounting.executed_count}\n"
            f"deselected={accounting.deselected_count}\n"
            f"not_executed_external_gates={external_gates}\n"
            f"not_executed_ci_markers={','.join(self.ci_excluded_markers())}\n"
            f"cache_restored={cache_restored}\n"
            f"failed={diagnostics.failed_count}\nerrors={diagnostics.error_count}\n"
            f"warnings={diagnostics.warning_count}\nskipped={diagnostics.skipped_count}\n"
            f"collection_skipped={len(self._collection_skip_lines(report_dir))}\n"
            f"suspended_policy_warnings={suspended_warnings}\n"
            f"policy_suspension_reason={config.Infra.codegen.make.policy_check_suspension_reason}\n"
            f"exit={final_exit}\n"
        )
        u.Cli.atomic_write_text_file(report_dir / "summary.txt", summary).unwrap()
        u.Cli.atomic_write_text_file(
            self.root / self.reports / "latest.txt", f"{report_dir.name}\n"
        ).unwrap()
        sys.stderr.write(f"Reports: {report_dir}\n")
        return r.ok(final_exit)

    @override
    def execute(self) -> p.Result[int]:
        """Execute the incremental selection with exact inventory accounting."""
        return self._execute_mode("incremental")

    def execute_full(self) -> p.Result[int]:
        """Execute the entire eligible inventory while collecting testmon data."""
        return self._execute_mode("full")

    def execute_coverage(self) -> p.Result[int]:
        """Execute the complete inventory with coverage, without testmon traffic."""
        return self._execute_mode("coverage")

    def _execute_mode(
        self, mode: Literal["incremental", "full", "coverage"]
    ) -> p.Result[int]:
        """Share inventory, deadline, process and receipt ownership for all modes."""
        report_dir = self._report_directory()
        coverage = mode == "coverage"
        if not coverage:
            u.Cli.ensure_dir(self.testmon_db.parent).unwrap()
        pre_digest = (
            None
            if coverage
            else FlextInfraTestmonDbInspector.digest_file(self.testmon_db)
        )
        cold_cache = pre_digest is None
        cache_restored = False
        if pre_digest is not None:
            pre_state = self._inspect_cache(digest=pre_digest).unwrap()
            u.Cli.atomic_write_text_file(
                report_dir / "cache-before.json",
                pre_state.model_dump_json(indent=2) + "\n",
            ).unwrap()
            cache_restored = pre_state.restored_accepted
            if not cache_restored:
                msg = f"testmon preflight rejected cache: {pre_state.reason}"
                raise RuntimeError(msg)
        inventory = self._resolve_selection(
            report_dir, complete=True, coverage=coverage
        )
        selection = (
            self._resolve_selection(report_dir) if mode == "incremental" else inventory
        )
        if not set(selection).issubset(inventory):
            msg_0 = "testmon selected nodes outside the complete inventory"
            raise ValueError(msg_0)
        if mode != "incremental":
            u.Cli.atomic_write_text_file(
                report_dir / "testmon-selection.txt", "\n".join(selection) + "\n"
            ).unwrap()
        if not selection:
            state = self._inspect_cache(digest=pre_digest).unwrap()
            u.Cli.atomic_write_text_file(
                report_dir / "cache-after.json", state.model_dump_json(indent=2) + "\n"
            ).unwrap()
            if not cache_restored or not state.restored_accepted:
                msg_0 = f"empty selection without an integrity-checked cache: {state.reason}"
                raise RuntimeError(msg_0)
            return self._finalize(
                report_dir,
                mode=mode,
                inventory=inventory,
                selected=selection,
                cache_restored=True,
            )
        # A cold cache seeds deterministically only when one process writes it:
        # parallel workers each resolve testmon against an evolving database and
        # xdist aborts with "Different tests were collected". Serialize the
        # seeding run; parallel distribution is a warm-cache path.
        command = (
            self.build_coverage_command(report_dir, selected_node_ids=selection)
            if coverage
            else self.build_command(report_dir, selection, serialize=cold_cache)
        )
        outcome = self._run_suite(command, report_dir)
        completed_failure = (
            outcome.raw_return_code == pytest.ExitCode.TESTS_FAILED
            and not outcome.timed_out
            and outcome.forwarded_signal is None
        )
        if not u.Cli.process_succeeded(outcome) and not completed_failure:
            return r.ok(outcome.raw_return_code)
        if coverage:
            if not completed_failure:
                self._validate_coverage(report_dir).unwrap()
        else:
            state = self._inspect_cache(digest=pre_digest).unwrap()
            u.Cli.atomic_write_text_file(
                report_dir / "cache-after.json", state.model_dump_json(indent=2) + "\n"
            ).unwrap()
            if not state.restored_accepted and not state.saveable:
                msg = f"testmon cache is unusable: {state.reason}"
                raise RuntimeError(msg)
        return self._finalize(
            report_dir,
            mode=mode,
            inventory=inventory,
            selected=selection,
            cache_restored=cache_restored,
            raw_return_code=outcome.raw_return_code if completed_failure else 0,
        )


__all__: list[str] = ["FlextInfraPytestRunnerExecution"]
