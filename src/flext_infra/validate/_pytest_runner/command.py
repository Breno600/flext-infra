"""Canonical pytest argv for persistent testmon execution.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import hashlib
import sys
from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from flext_infra import c, config, m, t, u
from flext_infra._pytest_collection import FlextInfraPytestCollection
from flext_infra.validate._pytest_runner.base import FlextInfraPytestRunnerBase


class FlextInfraPytestRunnerCommand(FlextInfraPytestRunnerBase):
    """Build the single supported pytest command family.

    One suite builder owns every flag; the testmon and coverage verbs are two
    selections over it (testmon 2.x refuses branch coverage through the cov
    plugin, so the two never share a process).
    """

    _NO_COVERAGE: ClassVar[t.VariadicTuple[str]] = ("--no-cov",)

    @staticmethod
    @lru_cache(maxsize=1)
    def _toolchain_testmon_environment() -> str:
        """Fingerprint the interpreter and installed distribution provenance.

        Git branch dependencies can change commits while retaining the same
        package version, so their PEP 610 receipts participate in cache identity.
        Registry distributions legitimately have no direct-URL receipt. An
        editable install names a checkout path, not a toolchain: testmon already
        tracks that source by file checksum, so every checkout of one project
        on the same lock shares one environment record.

        Returns:
            The resulting ``str``.

        """
        provenance: t.MutableSequenceOf[str] = []
        for distribution in u.installed_distributions():
            receipt = distribution.read_text("direct_url.json")
            dir_info = (
                None
                if receipt is None
                else m.Infra.DirectUrlReceipt.model_validate_json(receipt).dir_info
            )
            identity = (
                "editable" if dir_info is not None and dir_info.editable else receipt
            )
            provenance.append(
                f"{distribution.name}={distribution.version}:{identity!r}",
            )
        fingerprint = "\n".join((sys.version, *sorted(provenance)))
        digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:12]
        return f"toolchain-{digest}"

    def carries_slow_items(self, execution_mode: c.Infra.PytestExecutionMode) -> bool:
        """Whether this invocation may run slow-marked items.

        The budgeted phase deselects the slow marker and the slow phase
        selects it, for the incremental and the full operation alike: each
        phase is its own process on its own clock (gate-budget law), so the
        full operation runs the whole suite as two complete phases. Coverage
        runs the whole suite in one process. One predicate drives both the
        marker expression and the stop reserve, so an in-flight slow item
        always has its slow drain.

        Returns:
            The resulting ``bool``.

        """
        return self.slow_phase or execution_mode == c.Infra.PytestExecutionMode.COVERAGE

    def suite_stop_monotonic(
        self,
        *,
        serial: bool = False,
        execution_mode: c.Infra.PytestExecutionMode = (
            c.Infra.PytestExecutionMode.INCREMENTAL
        ),
    ) -> float:
        """Derive the graceful suite stop instant from the entrypoint deadline.

        Selection and inventory consume the same clock, so the instant leaves
        exactly the typed stop reserve before the process deadline: pytest
        ends its own session there and testmon persists what ran, instead of
        the deadline SIGTERM discarding every unflushed result. Serial runs
        keep at most one item in flight, so their reserve is smaller; a run
        that carries slow items reserves the slow per-item bound.

        Returns:
            The resulting ``float``.

        """
        pytest = config.Infra.tooling.tools.pytest
        if self.carries_slow_items(execution_mode):
            reserve = (
                pytest.slow_serial_suite_stop_reserve_seconds
                if serial
                else pytest.slow_suite_stop_reserve_seconds
            )
        else:
            reserve = (
                pytest.serial_suite_stop_reserve_seconds
                if serial
                else pytest.suite_stop_reserve_seconds
            )
        return self.started_at_monotonic + self.run_timeout_seconds(pytest) - reserve

    def ci_excluded_markers(
        self,
        *,
        execution_mode: c.Infra.PytestExecutionMode = (
            c.Infra.PytestExecutionMode.INCREMENTAL
        ),
    ) -> t.StrTuple:
        """Use the same CI token as generated workflows and pre-commit hooks.

        Returns:
            The resulting ``t.StrTuple``.

        """
        if self.ci_context and execution_mode != c.Infra.PytestExecutionMode.FULL:
            return config.Infra.tooling.tools.pytest.ci_excluded_markers
        return ()

    def testmon_environment(self, execution_mode: c.Infra.PytestExecutionMode) -> str:
        """Name the testmon environment of one marker scope on this toolchain.

        Under xdist, testmon syncs its records from the ids the workers
        collected and deletes every changed test outside them. Phases that
        deselect each other's markers inside one environment therefore erase
        each other's executions — a failed slow test vanished after the next
        budgeted run, its file then read as stable, and the slow phase passed
        without running it. testmon's environment is its declared separation
        between run configurations, so each marker scope owns one.

        Returns:
            The resulting ``str``.

        """
        scope = hashlib.sha256(
            self._marker_expression(execution_mode).encode(),
        ).hexdigest()[:8]
        return (
            f"{self._toolchain_testmon_environment()}-"
            f"{self._config_testmon_digest()}-{scope}"
        )

    def _config_testmon_digest(self) -> str:
        """Fingerprint the project's current ``config/*.yaml`` behavior inputs.

        testmon tracks Python sources only, while a FLEXT project's behavior
        is declared in its config: an edited YAML must select a fresh
        environment in the same external database instead of a cache hit.
        Read on every command construction, never memoized.

        Returns:
            The digest of every config source path and content.

        Raises:
            ValueError: If a required config source disappears mid-read.

        """
        digest = hashlib.sha256()
        for state in u.Infra.snapshot_config_sources(self.root).unwrap():
            if state.content is None:
                msg = f"required test configuration disappeared: {state.path}"
                raise ValueError(msg)
            digest.update(state.path.relative_to(self.root).as_posix().encode())
            digest.update(b"\0")
            digest.update(hashlib.sha256(state.content).digest())
        return digest.hexdigest()[:8]

    def _marker_expression(self, execution_mode: c.Infra.PytestExecutionMode) -> str:
        """Return the native pytest marker expression of one execution scope.

        The phase split is a marker expression: the budgeted phase deselects
        the slow marker, the slow phase selects only it.

        Returns:
            The native pytest marker expression of one execution scope.

        """
        pytest = config.Infra.tooling.tools.pytest
        excluded = tuple(
            dict.fromkeys((
                *(
                    (
                        *pytest.external_gate_markers,
                        *self.ci_excluded_markers(execution_mode=execution_mode),
                    )
                    if execution_mode != c.Infra.PytestExecutionMode.FULL
                    else ()
                ),
                *(
                    ()
                    if self.carries_slow_items(execution_mode)
                    else (pytest.slow_marker,)
                ),
            )),
        )
        if self.slow_phase:
            return (
                f"{pytest.slow_marker} and not ({' or '.join(excluded)})"
                if excluded
                else pytest.slow_marker
            )
        return f"not ({' or '.join(excluded)})" if excluded else ""

    def _plugin_policy_args(
        self,
        *,
        execution_mode: c.Infra.PytestExecutionMode,
    ) -> t.VariadicTuple[str]:
        """Apply the same configured plugin contract to collection and execution.

        Returns:
            The resulting ``t.VariadicTuple[str]``.

        """
        pytest = config.Infra.tooling.tools.pytest
        expression = self._marker_expression(execution_mode)
        return (
            "-p",
            pytest.enforcement_plugin,
            "-p",
            "no:metadata",
            "-o",
            f"{c.Infra.ASYNCIO_DEFAULT_FIXTURE_LOOP_SCOPE}={pytest.asyncio_default_fixture_loop_scope}",
            *(("-m", expression) if expression else ()),
        )

    def _node_targets(self) -> t.StrTuple:
        """Return the pytest node targets of this invocation.

        A declared single-file target replaces the suite directory as the
        only node target; the default remains the configured test root.

        Returns:
            The resulting ``t.StrTuple``.

        """
        return (
            (str(self.target_file),)
            if self.target_file is not None
            else (str(self.target),)
        )

    def build_selection_command(
        self,
        *,
        report_log: Path,
        manifest_path: Path,
        complete: bool = False,
        execution_mode: c.Infra.PytestExecutionMode = (
            c.Infra.PytestExecutionMode.INCREMENTAL
        ),
    ) -> t.VariadicTuple[str]:
        """Build the read-only argv that resolves the testmon selection once.

        Every xdist worker otherwise resolves the selection itself, and two
        workers reading the database while a third writes it collect different
        sets, which xdist aborts with "Different tests were collected". This
        pass runs no test and records its collection and warning evidence.
        The coverage inventory owns no testmon plugin, so it never reads or
        writes the persistent database.

        Returns:
            The resulting ``t.VariadicTuple[str]``.

        """
        testmon = (
            ()
            if execution_mode == c.Infra.PytestExecutionMode.COVERAGE
            else (
                "--testmon",
                "--testmon-nocollect",
                # Why: the external-gate deselection is a ``-m`` expression, and
                # testmon deactivates its selection whenever ``-m`` is present;
                # ``--testmon-forceselect`` is testmon's declared override for
                # exactly that case (never combined with ``--testmon-noselect``).
                *(("--testmon-noselect",) if complete else ("--testmon-forceselect",)),
                "--testmon-env",
                f"'{self.testmon_environment(execution_mode)}'",
            )
        )
        pytest_arguments = (
            *self._node_targets(),
            *testmon,
            "--collect-only",
            f"{c.Infra.PYTEST_COLLECTION_MANIFEST_OPTION}={manifest_path}",
            f"--report-log={report_log}",
            "-q",
            *self._plugin_policy_args(execution_mode=execution_mode),
            "--benchmark-disable",
            "--strict-markers",
            f"--timeout={config.Infra.tooling.tools.pytest.case_timeout_seconds}",
            "-o",
            "filterwarnings=",
            "-p",
            "no:randomly",
            "-n",
            "0",
            "--no-cov",
        )
        if self.collection_command_prefix:
            return (
                *self.collection_command_prefix,
                str(manifest_path.with_suffix(".pstats")),
                *pytest_arguments,
            )
        return (sys.executable, "-m", "pytest", *pytest_arguments)

    def build_command(
        self,
        report_dir: Path,
        selection_plan: m.Infra.PytestSelectionPlan | None = None,
        *,
        serialize: bool = False,
        execution_mode: c.Infra.PytestExecutionMode = (
            c.Infra.PytestExecutionMode.INCREMENTAL
        ),
    ) -> t.VariadicTuple[str]:
        """Build the testmon suite argv (never the cov plugin).

        A resolved plan carries the selected IDs and their manifest together.

        Returns:
            The resulting ``t.VariadicTuple[str]``.

        """
        pytest = config.Infra.tooling.tools.pytest
        selected_node_ids = selection_plan.node_ids if selection_plan else None
        selection = selected_node_ids or None
        # An empty selection needs no workers, and a selection smaller than the
        # worker budget never needs more workers than items: every extra worker
        # only pays startup cost for an empty queue. Explicit serial execution
        # remains available to callers; cold and warm cache runs share the same
        # manifest.
        budget = self.parallel_worker_budget(pytest)
        if serialize or selected_node_ids == ():
            workers = "0"
        elif selection:
            workers = str(min(budget, len(selection)))
        else:
            workers = str(budget)
        # A serial dispatch keeps one item in flight, so its drain reserve is
        # the single-item budget instead of the xdist two-deep worst case.
        serial = workers in {"0", "1"}
        if serial:
            workers = "0"
        return self._suite_argv(
            report_dir,
            serial=serial,
            execution_mode=execution_mode,
            targets=(
                self._node_targets()
                if (
                    selection_plan is None
                    or selection_plan.whole_target
                    or selection is None
                )
                else tuple(selection)
            ),
            workers=workers,
            trailing=(
                *self._plugin_policy_args(execution_mode=execution_mode),
                *(
                    (
                        "-p",
                        FlextInfraPytestCollection.__module__,
                        f"{c.Infra.PYTEST_SELECTED_COLLECTION_OPTION}={selection_plan.manifest_path}",
                    )
                    if selection_plan is not None and selection
                    else ()
                ),
                "--testmon",
                # Why: a declared single-file target is the operator's chosen
                # scope; the cache must never deselect it (a file never run
                # before has no traces, so testmon selection resolves empty
                # and the phase would pass with zero tests). The execution
                # still feeds the persistent database for future runs.
                *(
                    ("--testmon-noselect",)
                    if (selection or self.target_file is not None)
                    else ("--testmon-forceselect",)
                ),
                "--testmon-env",
                f"'{self.testmon_environment(execution_mode)}'",
                *self._NO_COVERAGE,
            ),
        )

    def build_coverage_command(
        self,
        report_dir: Path,
        *,
        serialize: bool = False,
    ) -> t.VariadicTuple[str]:
        """Build the whole-suite coverage argv (never the testmon plugin).

        The measurement source is the declared package source directory — the
        same boundary every fleet coverage config declares — so imported
        third-party/Cython modules can never emit parse warnings.

        Returns:
            The resulting ``t.VariadicTuple[str]``.

        """
        pytest = config.Infra.tooling.tools.pytest
        workers = "0" if serialize else str(self.parallel_worker_budget(pytest))
        return self._suite_argv(
            report_dir,
            serial=workers == "0",
            execution_mode=c.Infra.PytestExecutionMode.COVERAGE,
            targets=self._node_targets(),
            workers=workers,
            trailing=(
                *self._plugin_policy_args(
                    execution_mode=c.Infra.PytestExecutionMode.COVERAGE,
                ),
                f"--cov={self.root / c.Infra.DEFAULT_SRC_DIR}",
                f"--cov-report=xml:{report_dir / 'coverage.xml'}",
                "--no-cov-on-fail",
            ),
        )

    def _suite_argv(
        self,
        report_dir: Path,
        *,
        serial: bool,
        execution_mode: c.Infra.PytestExecutionMode,
        targets: t.StrSequence,
        workers: str,
        trailing: t.StrSequence,
    ) -> t.VariadicTuple[str]:
        """Assemble one suite invocation; ``trailing`` owns the plugin split.

        Returns:
            The resulting ``t.VariadicTuple[str]``.

        """
        pytest = config.Infra.tooling.tools.pytest
        suite_stop = self.suite_stop_monotonic(
            serial=serial,
            execution_mode=execution_mode,
        )
        return (
            sys.executable,
            *(
                (
                    "-c",
                    c.Infra.PYTEST_PROFILE_LAUNCHER,
                    str(report_dir / pytest.profile_suite_filename),
                )
                if self.profile_enabled
                else ("-m", "pytest")
            ),
            *targets,
            *pytest.progress_args,
            *pytest.report_args,
            f"--timeout={pytest.case_timeout_seconds}",
            f"{c.Infra.PYTEST_SUITE_STOP_OPTION}={suite_stop!r}",
            f"--maxfail={pytest.max_failures}",
            f"--junitxml={report_dir / 'junit.xml'}",
            f"--report-log={report_dir / 'events.jsonl'}",
            *trailing,
            "-n",
            workers,
            "--dist",
            pytest.parallel_distribution,
            # Why: xdist queues the shutdown marker behind each worker's
            # pre-dispatched chunk, so the declared max-failures stop only took
            # effect after every worker drained its assigned items at fleet
            # scale. A one-item dispatch step makes that stop immediate.
            "--maxschedchunk",
            str(pytest.parallel_schedule_chunk),
            "--benchmark-disable",
        )


__all__: list[str] = ["FlextInfraPytestRunnerCommand"]
