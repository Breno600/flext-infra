"""Public proof that gate hook defaults survive as class data.

A gate that leaves the five check hooks alone still drops the color signal,
inherits the rest of the environment, leaves undeclared reports in place, and
accepts output with no declared evidence. A gate that replaces the class data
or overrides a reader keeps that replacement.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, ClassVar, override

import pytest
from flext_tests import tm

from flext_infra import c, m
from flext_infra.gates.base_gate import FlextInfraGate
from flext_infra.gates.pyrefly import FlextInfraPyreflyGate
from flext_infra.gates.pyright import FlextInfraPyrightGate

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class TestsFlextInfraGateHookDefaults:
    """Check-hook defaults and their overrides, observed through ``check``."""

    _KEPT = "FLEXT_GATE_PROBE_KEPT"
    _KEPT_VALUE = "kept"
    _MARKER = "FLEXT_GATE_PROBE_MARKER"
    _MARKER_VALUE = "from-override"
    _REPORT_NAME = "probe.json"

    class _Probe(FlextInfraGate):
        """Run one environment probe without replacing the five hook defaults."""

        gate_id: ClassVar[str] = "probe"
        gate_name: ClassVar[str] = "Probe"

        @override
        def _build_check_command(
            self,
            project_dir: Path,
            ctx: m.Infra.GateContext,
            check_dirs: t.StrSequence,
        ) -> t.StrSequence:
            """Print the environment keys the hook defaults control.

            Returns:
                The resulting ``t.StrSequence``.

            """
            _ = project_dir, ctx, check_dirs
            return TestsFlextInfraGateHookDefaults._probe_command()

        @override
        def _parse_check_output(
            self,
            result: p.Cli.CommandOutput,
            project_dir: Path,
            ctx: m.Infra.GateContext,
        ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
            """Accept the probe output. The environment is the assertion.

            Returns:
                The resulting ``t.Pair[bool, t.SequenceOf[m.Infra.Issue]]``.

            """
            _ = result, project_dir, ctx
            return True, ()

    class _ClassDataOverride(_Probe):
        """Replace report, removal, and timeout data without new readers."""

        check_report_filename: ClassVar[str] = "probe.json"
        check_timeout: ClassVar[int] = 1
        check_remove_env_keys: ClassVar[t.StrSequence] = (
            *FlextInfraGate.check_remove_env_keys,
            "FLEXT_GATE_PROBE_KEPT",
        )

    class _EnvOverride(_Probe):
        """Overlay one marker while the other hook defaults stay inherited."""

        @override
        def _check_env(
            self,
            project_dir: Path,
            ctx: m.Infra.GateContext,
        ) -> t.StrMapping | None:
            """Overlay one marker on the inherited environment.

            Returns:
                The resulting ``t.StrMapping | None``.

            """
            _ = project_dir, ctx
            return {
                TestsFlextInfraGateHookDefaults._MARKER: (
                    TestsFlextInfraGateHookDefaults._MARKER_VALUE
                ),
            }

    class _ValidateOverride(_Probe):
        """Reject the probe output that the inherited validator accepts."""

        @override
        def _validate_check_report(
            self,
            result: p.Cli.CommandOutput,
            project_dir: Path,
            ctx: m.Infra.GateContext,
            targets: t.StrSequence,
        ) -> None:
            """Reject the probe's native stderr marker.

            Raises:
                ValueError: If the probe wrote its native marker.

            """
            _ = project_dir, ctx, targets
            if "NATIVE" in result.stderr:
                msg = "native report rejected"
                raise ValueError(msg)

    class _SlowInherited(_Probe):
        """Spend two seconds so a tiny inherited timeout would kill the probe."""

        @override
        def _build_check_command(
            self,
            project_dir: Path,
            ctx: m.Infra.GateContext,
            check_dirs: t.StrSequence,
        ) -> t.StrSequence:
            """Sleep inside the inherited deadline, then finish.

            Returns:
                The resulting ``t.StrSequence``.

            """
            _ = project_dir, ctx, check_dirs
            return (
                sys.executable,
                "-c",
                "import time; time.sleep(2); print('FINISHED')",
            )

    class _ShortTimeout(_Probe):
        """Cut a long sleep off with the replaced timeout."""

        check_timeout: ClassVar[int] = 1

        @override
        def _build_check_command(
            self,
            project_dir: Path,
            ctx: m.Infra.GateContext,
            check_dirs: t.StrSequence,
        ) -> t.StrSequence:
            """Sleep far past the replaced one-second deadline.

            Returns:
                The resulting ``t.StrSequence``.

            """
            _ = project_dir, ctx, check_dirs
            return (
                sys.executable,
                "-c",
                "import time; time.sleep(30); print('FINISHED')",
            )

    @staticmethod
    def _probe_command() -> t.StrSequence:
        """Return the interpreter command that prints the probed environment.

        Returns:
            The resulting ``t.StrSequence``.

        """
        force = repr(c.Infra.ENV_VAR_FORCE_COLOR)
        kept = repr(TestsFlextInfraGateHookDefaults._KEPT)
        marker = repr(TestsFlextInfraGateHookDefaults._MARKER)
        script = (
            "import os, sys\n"
            "sys.stderr.write('NATIVE\\n')\n"
            "print('PROBE\\t{0}\\t{1}\\t{2}'.format(\n"
            f"    os.environ.get({force}, ''),\n"
            f"    os.environ.get({kept}, ''),\n"
            f"    os.environ.get({marker}, ''),\n"
            "))\n"
        )
        return (sys.executable, "-c", script)

    @staticmethod
    def _project(tmp_path: Path) -> tuple[Path, Path]:
        """Create one project with a Python target and a reports directory.

        Returns:
            The project directory and its reports directory.

        """
        project = tmp_path / "demo"
        source = project / "src"
        source.mkdir(parents=True)
        (source / "sample.py").write_text("value = 1\n", encoding="utf-8")
        reports = project / "reports"
        reports.mkdir()
        return project, reports

    @staticmethod
    def _context(project: Path, reports: Path) -> m.Infra.GateContext:
        """Build the check context whose reports directory the gate may replace.

        Returns:
            The resulting ``m.Infra.GateContext``.

        """
        return m.Infra.GateContext(repository_root=project, reports_dir=reports)

    def test_inherited_defaults_still_apply(self, tmp_path: Path) -> None:
        """A gate that does not override the five hooks keeps the old defaults."""
        project, reports = self._project(tmp_path)
        replaced = reports / f"{project.name}-{self._REPORT_NAME}"
        kept_file = reports / f"{project.name}-kept.json"
        replaced.write_text("stale\n", encoding="utf-8")
        kept_file.write_text("stay\n", encoding="utf-8")
        with tm.scope(
            env={
                c.Infra.ENV_VAR_FORCE_COLOR: "forced",
                self._KEPT: self._KEPT_VALUE,
            },
        ):
            execution = self._Probe(project).check(
                project,
                self._context(project, reports),
            )
        tm.that(execution.result.passed, eq=True)
        tm.that(execution.raw_output, has="NATIVE")
        tm.that(execution.raw_output, has=f"PROBE\t\t{self._KEPT_VALUE}\t")
        tm.that(execution.raw_output, lacks="forced")
        tm.that(replaced.read_text(encoding="utf-8"), eq="stale\n")
        tm.that(kept_file.read_text(encoding="utf-8"), eq="stay\n")

    def test_class_data_override_replaces_report_and_env(
        self,
        tmp_path: Path,
    ) -> None:
        """Replaced class data unlinks the named report and drops the extra key."""
        project, reports = self._project(tmp_path)
        replaced = reports / f"{project.name}-{self._REPORT_NAME}"
        kept_file = reports / f"{project.name}-kept.json"
        replaced.write_text("stale\n", encoding="utf-8")
        kept_file.write_text("stay\n", encoding="utf-8")
        with tm.scope(
            env={
                c.Infra.ENV_VAR_FORCE_COLOR: "forced",
                self._KEPT: self._KEPT_VALUE,
            },
        ):
            execution = self._ClassDataOverride(project).check(
                project,
                self._context(project, reports),
            )
        tm.that(execution.result.passed, eq=True)
        tm.that(execution.raw_output, has="PROBE\t\t\t")
        tm.that(execution.raw_output, lacks=self._KEPT_VALUE)
        tm.that(execution.raw_output, lacks="forced")
        tm.that(replaced.exists(), eq=False)
        tm.that(kept_file.read_text(encoding="utf-8"), eq="stay\n")

    def test_method_override_keeps_env_and_validation(self, tmp_path: Path) -> None:
        """A reader override still overlays the environment and rejects the report."""
        project, reports = self._project(tmp_path)
        context = self._context(project, reports)
        with tm.scope(
            env={
                c.Infra.ENV_VAR_FORCE_COLOR: "forced",
                self._KEPT: self._KEPT_VALUE,
            },
        ):
            execution = self._EnvOverride(project).check(project, context)
            tm.that(execution.result.passed, eq=True)
            tm.that(
                execution.raw_output,
                has=f"PROBE\t\t{self._KEPT_VALUE}\t{self._MARKER_VALUE}",
            )
            tm.that(execution.raw_output, lacks="forced")
            with pytest.raises(ValueError, match="native report rejected"):
                self._ValidateOverride(project).check(project, context)

    def test_inherited_timeout_allows_a_short_command(self, tmp_path: Path) -> None:
        """A two-second probe finishes under the inherited deadline."""
        project, reports = self._project(tmp_path)
        execution = self._SlowInherited(project).check(
            project,
            self._context(project, reports),
        )
        tm.that(execution.raw_output, has="FINISHED")

    def test_replaced_timeout_stops_a_long_command(self, tmp_path: Path) -> None:
        """A gate that replaces ``check_timeout`` is cut off at that deadline."""
        project, reports = self._project(tmp_path)
        execution = self._ShortTimeout(project).check(
            project,
            self._context(project, reports),
        )
        tm.that(execution.raw_output, lacks="FINISHED")
        tm.that(execution.result.duration, lt=10)

    @staticmethod
    def test_production_gates_keep_their_declared_defaults() -> None:
        """Pyright and Pyrefly keep the deadlines and removals they declared."""
        tm.that(FlextInfraPyrightGate.check_timeout, eq=c.Infra.TIMEOUT_LONG)
        tm.that(
            tuple(FlextInfraPyreflyGate.check_remove_env_keys),
            eq=(
                *tuple(FlextInfraGate.check_remove_env_keys),
                c.Infra.ORCHESTRATOR_ENV_PYTHONPATH,
            ),
        )
        tm.that(
            FlextInfraPyreflyGate.check_report_filename,
            eq="pyrefly.json",
        )
