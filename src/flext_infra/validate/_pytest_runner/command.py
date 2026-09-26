"""Canonical pytest argv for persistent testmon execution."""

from __future__ import annotations

import hashlib
import sys
from functools import lru_cache
from importlib.metadata import distributions
from pathlib import Path
from typing import ClassVar

from flext_infra import c, config, t

from ..._pytest_collection import FlextInfraPytestCollection
from .base import FlextInfraPytestRunnerBase


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
        Registry distributions legitimately have no direct-URL receipt.
        """
        fingerprint = "\n".join((
            sys.version,
            *sorted(
                f"{distribution.name}={distribution.version}:"
                f"{distribution.read_text('direct_url.json')!r}"
                for distribution in distributions()
            ),
        ))
        digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:12]
        return f"toolchain-{digest}"

    def ci_excluded_markers(
        self,
        *,
        execution_mode: c.Infra.PytestExecutionMode = c.Infra.PytestExecutionMode.INCREMENTAL,
    ) -> t.StrTuple:
        """Use the same CI token as generated workflows and pre-commit hooks."""
        if self.ci_context and execution_mode != c.Infra.PytestExecutionMode.FULL:
            return config.Infra.tooling.tools.pytest.ci_excluded_markers
        return ()

    def _plugin_policy_args(
        self, *, execution_mode: c.Infra.PytestExecutionMode
    ) -> t.VariadicTuple[str]:
        """Apply the same configured plugin contract to collection and execution."""
        pytest = config.Infra.tooling.tools.pytest
        excluded = (
            (
                *pytest.external_gate_markers,
                *self.ci_excluded_markers(execution_mode=execution_mode),
            )
            if execution_mode != c.Infra.PytestExecutionMode.FULL
            else ()
        )
        return (
            "-p",
            pytest.enforcement_plugin,
            "-p",
            "no:metadata",
            "-o",
            f"{c.Infra.ASYNCIO_DEFAULT_FIXTURE_LOOP_SCOPE}={pytest.asyncio_default_fixture_loop_scope}",
            *(("-m", f"not ({' or '.join(excluded)})") if excluded else ()),
        )

    def build_selection_command(
        self,
        *,
        report_log: Path,
        complete: bool = False,
        execution_mode: c.Infra.PytestExecutionMode = c.Infra.PytestExecutionMode.INCREMENTAL,
    ) -> t.VariadicTuple[str]:
        """Build the read-only argv that resolves the testmon selection once.

        Every xdist worker otherwise resolves the selection itself, and two
        workers reading the database while a third writes it collect different
        sets, which xdist aborts with "Different tests were collected". This
        pass runs no test and records its collection and warning evidence.
        """
        return (
            sys.executable,
            "-m",
            "pytest",
            str(self.target),
            "--testmon",
            "--testmon-nocollect",
            # Why: the external-gate deselection is a ``-m`` expression, and
            # testmon deactivates its selection whenever ``-m`` is present;
            # ``--testmon-forceselect`` is testmon's declared override for
            # exactly that case (never combined with ``--testmon-noselect``).
            *(("--testmon-noselect",) if complete else ("--testmon-forceselect",)),
            "--testmon-env",
            f"'{self._toolchain_testmon_environment()}'",
            "--collect-only",
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

    def build_command(
        self,
        report_dir: Path,
        selected_node_ids: t.StrSequence | None = None,
        *,
        serialize: bool = False,
        execution_mode: c.Infra.PytestExecutionMode = c.Infra.PytestExecutionMode.INCREMENTAL,
    ) -> t.VariadicTuple[str]:
        """Build the testmon suite argv (never the cov plugin)."""
        pytest = config.Infra.tooling.tools.pytest
        selection = selected_node_ids or None
        # A single selected test has no distribution work.  Starting xdist for
        # it only adds two interpreter lifecycles and can consume the enclosing
        # test's complete slow-test budget after the two collection processes.
        # Cold and warm caches still share the same explicit manifest.
        workers = (
            "0"
            if serialize
            or (selected_node_ids is not None and len(selected_node_ids) <= 1)
            else str(self.parallel_worker_budget(pytest))
        )
        return self._suite_argv(
            report_dir,
            targets=(tuple(selection) if selection else (str(self.target),)),
            workers=workers,
            trailing=(
                *self._plugin_policy_args(execution_mode=execution_mode),
                *(
                    (
                        "-p",
                        FlextInfraPytestCollection.__module__,
                        c.Infra.PYTEST_SELECTED_COLLECTION_OPTION,
                    )
                    if selection
                    else ()
                ),
                "--testmon",
                *(("--testmon-noselect",) if selection else ("--testmon-forceselect",)),
                "--testmon-env",
                f"'{self._toolchain_testmon_environment()}'",
                *self._NO_COVERAGE,
            ),
        )

    def build_coverage_command(
        self, report_dir: Path, *, serialize: bool = False
    ) -> t.VariadicTuple[str]:
        """Build the whole-suite coverage argv (never the testmon plugin).

        The measurement source is the declared package source directory — the
        same boundary every fleet coverage config declares — so imported
        third-party/Cython modules can never emit parse warnings.
        """
        pytest = config.Infra.tooling.tools.pytest
        workers = "0" if serialize else str(self.parallel_worker_budget(pytest))
        return self._suite_argv(
            report_dir,
            targets=(str(self.target),),
            workers=workers,
            trailing=(
                *self._plugin_policy_args(
                    execution_mode=c.Infra.PytestExecutionMode.COVERAGE
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
        targets: t.StrSequence,
        workers: str,
        trailing: t.StrSequence,
    ) -> t.VariadicTuple[str]:
        """Assemble one suite invocation; ``trailing`` owns the plugin split."""
        pytest = config.Infra.tooling.tools.pytest
        return (
            sys.executable,
            "-m",
            "pytest",
            *targets,
            *pytest.progress_args,
            *pytest.report_args,
            f"--timeout={pytest.case_timeout_seconds}",
            f"--maxfail={pytest.max_failures}",
            f"--junitxml={report_dir / 'junit.xml'}",
            f"--report-log={report_dir / 'events.jsonl'}",
            *trailing,
            "-n",
            workers,
            "--dist",
            pytest.parallel_distribution,
            "--benchmark-disable",
        )


__all__: list[str] = ["FlextInfraPytestRunnerCommand"]
