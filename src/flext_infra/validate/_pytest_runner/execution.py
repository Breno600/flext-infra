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

    def _collect_node_ids(
        self, report_dir: Path, *, inventory: bool = False
    ) -> t.StrSequence:
        """Persist collection evidence; inventory never changes the selected set."""
        pytest_settings = config.Infra.tooling.tools.pytest
        command = (
            self.build_inventory_command()
            if inventory
            else self.build_selection_command()
        )
        phase = "inventory" if inventory else "selection"
        outcome = u.Cli.run_raw(
            command,
            cwd=self.root,
            timeout=pytest_settings.run_timeout_seconds,
            env=self._selection_env(),
        ).unwrap()
        self._record_process_outcome(report_dir, phase, outcome.outcome)
        # Exit code 5 is pytest's "no tests ran": testmon selected nothing.
        if (
            outcome.outcome.raw_return_code not in {0, 5}
            or outcome.outcome.timed_out
            or outcome.outcome.forwarded_signal is not None
        ):
            detail = (outcome.stderr or outcome.stdout).strip()
            msg = (
                f"testmon {phase} failed ({outcome.outcome.raw_return_code}): {detail}"
            )
            raise RuntimeError(msg)
        node_ids = tuple(
            line.strip()
            for line in (outcome.stdout or "").splitlines()
            if "::" in line and not line.startswith(" ")
        )
        artifact = f"testmon-{phase}"
        u.Cli.atomic_write_text_file(
            report_dir / f"{artifact}.txt", "\n".join(node_ids) + "\n"
        ).unwrap()
        u.Cli.atomic_write_text_file(
            report_dir / f"{artifact}.log", outcome.stdout or ""
        ).unwrap()
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
        cache_restored: bool = False,
        raw_return_code: int = 0,
    ) -> p.Result[int]:
        """Reject incomplete evidence and publish one bounded summary."""
        accounting = self._accounting(
            report_dir / "junit.xml",
            report_dir / "pytest.log",
            cache_restored=cache_restored,
        ).unwrap()
        diagnostics = self._diagnostics(report_dir).unwrap()
        self._write_diagnostics(report_dir, diagnostics)
        rejected = any((
            diagnostics.failed_count,
            diagnostics.error_count,
            diagnostics.warning_count,
        ))
        final_exit = raw_return_code or int(rejected)
        external_gates = ",".join(
            config.Infra.tooling.tools.pytest.external_gate_markers
        )
        summary = (
            f"executed={accounting.executed_count}\n"
            f"deselected={accounting.deselected_count}\n"
            f"not_executed_external_gates={external_gates}\n"
            f"not_executed_ci_markers={','.join(self.ci_excluded_markers())}\n"
            f"cache_restored={cache_restored}\n"
            f"failed={diagnostics.failed_count}\nerrors={diagnostics.error_count}\n"
            f"warnings={diagnostics.warning_count}\nskipped={diagnostics.skipped_count}\n"
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
        """Execute one whole-suite cached or full testmon invocation."""
        report_dir = self._report_directory()
        u.Cli.ensure_dir(self.testmon_db.parent).unwrap()
        pre_digest = FlextInfraTestmonDbInspector.digest_file(self.testmon_db)
        cold_cache = pre_digest is None
        cache_restored = False
        if pre_digest is not None:
            pre_state = self._inspect_cache(digest=pre_digest).unwrap()
            cache_restored = pre_state.restored_accepted
            if not cache_restored:
                msg = f"testmon preflight rejected cache: {pre_state.reason}"
                raise RuntimeError(msg)
        selection = self._collect_node_ids(report_dir)
        if not selection:
            self._collect_node_ids(report_dir, inventory=True)
        # A cold cache seeds deterministically only when one process writes it:
        # parallel workers each resolve testmon against an evolving database and
        # xdist aborts with "Different tests were collected". Serialize the
        # seeding run; parallel distribution is a warm-cache path.
        command = self.build_command(report_dir, selection, serialize=cold_cache)
        outcome = self._run_suite(command, report_dir)
        cache_hit = (
            outcome.raw_return_code == pytest.ExitCode.NO_TESTS_COLLECTED
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
            raw_return_code=outcome.raw_return_code if completed_failure else 0,
        )

    def execute_coverage(self) -> p.Result[int]:
        """Execute the whole suite under the coverage plugin (never testmon).

        testmon 2.x refuses branch coverage through the cov plugin, so the
        coverage pass is its own process: no selection pass, no cache traffic.
        The coverage artifact and any threshold failure are validated here.
        """
        report_dir = self._report_directory()
        command = self.build_coverage_command(report_dir)
        outcome = self._run_suite(command, report_dir)
        if not u.Cli.process_succeeded(outcome):
            return r.ok(outcome.raw_return_code)
        self._validate_coverage(report_dir).unwrap()
        return self._finalize(report_dir)


__all__: list[str] = ["FlextInfraPytestRunnerExecution"]
