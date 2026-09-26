"""Behavior tests for bounded Mypy process execution."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, m, u
from tests import u as test_u


class TestsFlextInfraUtilitiesResourceLimits:
    """Behavior tests for the canonical Mypy resource-limit command."""

    def test_mypy_command_runs_harmless_process_with_memory_and_time_limits(
        self,
    ) -> None:
        """Run a harmless process through both validated resource ceilings."""
        limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT, timeout_seconds=60
        )
        command = u.Infra.mypy_limited_command(
            (
                sys.executable,
                "-c",
                "import sys; sys.stdout.write('bounded-process\\n')",
            ),
            limit,
        )
        result = u.Cli.run_raw(command, timeout=u.Infra.mypy_runner_timeout(limit))

        if sys.platform == "darwin":
            tm.that(command[0], eq=sys.executable)
            tm.that(Path(command[1]).name, eq="_mypy_supervisor.py")
            tm.that(command[2], eq=str(limit.memory_limit_bytes))
            tm.that(command[3], eq=str(limit.timeout_seconds))
        else:
            tm.that(Path(command[0]).name, eq=c.Infra.TIMEOUT_COMMAND)
            tm.that(command[3], eq=f"{limit.timeout_seconds}s")
            tm.that(Path(command[4]).name, eq=c.Infra.PRLIMIT_COMMAND)
            tm.that(
                command[5],
                eq=f"--as={limit.memory_limit_bytes}:{limit.memory_limit_bytes}",
            )
        tm.ok(result)
        tm.that(u.Cli.process_succeeded(result.value.outcome), eq=True)
        tm.that(result.value.stdout, has="bounded-process")

    @pytest.mark.parametrize(
        ("source", "memory_mb", "seconds", "expected"),
        [
            ("import sys; sys.exit(7)", 512, 10, 7),
            ("import time; time.sleep(30)", 512, 1, 124),
            # Darwin's supervisor samples group RSS and stops it (137); Linux
            # prlimit makes the allocation fail inside the process (exit 1).
            (
                "import time; a = bytearray(128 * 1024**2); time.sleep(30)",
                64,
                10,
                (137 if sys.platform == "darwin" else 1),
            ),
        ],
    )
    def test_resource_limit_enforces_exit_deadline_and_memory(
        self, source: str, memory_mb: int, seconds: int, expected: int
    ) -> None:
        """Exercise a real exit, deadline and resident allocation through the owner."""
        limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=memory_mb, timeout_seconds=seconds
        )
        result = u.Cli.run_raw(
            u.Infra.mypy_limited_command((sys.executable, "-c", source), limit),
            timeout=u.Infra.mypy_runner_timeout(limit),
        )
        tm.ok(result)
        tm.that(result.value.outcome.raw_return_code, eq=expected)

    @pytest.mark.parametrize(
        ("tail", "expected"), [("sys.exit(7)", 7), ("time.sleep(30)", 124)]
    )
    def test_resource_limit_stops_resistant_descendant_group(
        self, tail: str, expected: int
    ) -> None:
        """Kill a TERM-resistant descendant after leader exit or deadline."""
        source = (
            "import subprocess,sys,time; "
            "p=subprocess.Popen([sys.executable, '-c', "
            '"import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); '
            "print('ready', flush=True); time.sleep(30)\"], "
            "stdout=subprocess.PIPE, text=True); "
            f"p.stdout.readline(); print(p.pid, flush=True); {tail}"
        )
        limit = m.Infra.MypyResourceLimit(memory_limit_mb=512, timeout_seconds=2)
        result = u.Cli.run_raw(
            u.Infra.mypy_limited_command((sys.executable, "-c", source), limit),
            timeout=u.Infra.mypy_runner_timeout(limit),
        )
        tm.ok(result)
        tm.that(result.value.outcome.raw_return_code, eq=expected)
        pid = int(result.value.stdout.strip())
        remaining = u.Cli.run_raw(("/bin/ps", "-p", str(pid), "-o", "stat="), timeout=2)
        tm.ok(remaining)
        state = remaining.value.stdout.strip()
        if sys.platform == "darwin":
            tm.that(not state or state.startswith("Z"), eq=True)
        # GNU timeout reaps the resistant group when it stops the leader at
        # the deadline; on a clean leader exit the group outlives the
        # wrapper, so the probe reaps its own descendant instead.
        elif expected == 124:
            tm.that(not state, eq=True)
        else:
            u.Cli.run_raw(("/bin/kill", "-9", str(pid)), timeout=2)

    def test_resource_limit_stops_workload_on_termination(self) -> None:
        """Preserve external termination and reap the running workload."""
        limit = m.Infra.MypyResourceLimit(memory_limit_mb=512, timeout_seconds=20)
        started = u.Cli.process_start(
            u.Infra.mypy_limited_command(
                (
                    sys.executable,
                    "-c",
                    "import time; print('ready', flush=True); time.sleep(30)",
                ),
                limit,
            )
        )
        tm.ok(started)
        child = started.value
        try:
            tm.ok(child.stdout_read_until(b"ready", timeout=5))
            tm.ok(child.terminate())
            exited = child.wait(timeout=10)
            tm.ok(exited)
            expected_exit = 143 if sys.platform == "darwin" else -15
            tm.that(exited.value, eq=expected_exit)
        finally:
            if child.poll() is None:
                tm.ok(child.kill())
                tm.ok(child.wait(timeout=5))

    def test_mypy_resource_contract_rejects_non_positive_limits(self) -> None:
        """Reject invalid external configuration before spawning a process."""
        with pytest.raises(ValueError, match="greater than 0"):
            m.Infra.MypyResourceLimit(memory_limit_mb=0, timeout_seconds=0)

    def test_mypy_resource_limit_parses_environment_at_boundary(self) -> None:
        """Convert valid process text once before strict model validation."""
        with tm.scope(
            env={
                c.Infra.MYPY_MEMORY_LIMIT_MB_ENV: "1024",
                c.Infra.MYPY_TIMEOUT_SECONDS_ENV: "120",
            }
        ):
            limit = u.Infra.mypy_resource_limit()

        tm.that(limit.memory_limit_mb, eq=1024)
        tm.that(limit.timeout_seconds, eq=120)

    @pytest.mark.parametrize("invalid_value", ["", "1024.0", "-1", " 1024"])
    def test_mypy_resource_limit_rejects_non_integer_environment(
        self, invalid_value: str
    ) -> None:
        """Reject non-integer process text before constructing the strict model.

        The value reaches the process environment verbatim: ``tm.scope`` routes
        it through a model whose base config strips whitespace, which would
        repair `` 1024`` into a valid limit and make the padded case untestable.
        The contract under test is exactly that no such repair happens.
        """
        original_memory = os.environ.get(c.Infra.MYPY_MEMORY_LIMIT_MB_ENV)
        original_timeout = os.environ.get(c.Infra.MYPY_TIMEOUT_SECONDS_ENV)
        os.environ[c.Infra.MYPY_MEMORY_LIMIT_MB_ENV] = invalid_value
        os.environ[c.Infra.MYPY_TIMEOUT_SECONDS_ENV] = "120"
        try:
            with pytest.raises(
                ValueError, match=f"{c.Infra.MYPY_MEMORY_LIMIT_MB_ENV} must be"
            ):
                u.Infra.mypy_resource_limit()
        finally:
            test_u.Tests.restore_env(c.Infra.MYPY_MEMORY_LIMIT_MB_ENV, original_memory)
            test_u.Tests.restore_env(c.Infra.MYPY_TIMEOUT_SECONDS_ENV, original_timeout)

    def test_mypy_resource_contract_rejects_memory_above_ceiling(self) -> None:
        """Reject a configured limit above the canonical hard ceiling."""
        with pytest.raises(
            ValueError,
            match=f"less than or equal to {c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT}",
        ):
            m.Infra.MypyResourceLimit(
                memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT + 1,
                timeout_seconds=60,
            )

    def test_mypy_resource_contract_rejects_timeout_above_ceiling(self) -> None:
        """Reject a wall-time configuration above the canonical ceiling."""
        with pytest.raises(
            ValueError,
            match=f"less than or equal to {c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT}",
        ):
            m.Infra.MypyResourceLimit(
                memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
                timeout_seconds=c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT + 1,
            )

    def test_mypy_timeout_has_controlled_exit_and_signal_diagnostic(self) -> None:
        """Expose the configured ceilings and process status on timeout."""
        limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT, timeout_seconds=60
        )
        diagnostic = u.Infra.mypy_failure_diagnostic(
            m.Cli.CommandOutput(
                stdout="",
                stderr="",
                outcome=m.Cli.ProcessOutcome(
                    raw_return_code=c.Infra.PROCESS_TIMEOUT_EXIT_CODE,
                    timed_out=True,
                    forwarded_signal=None,
                ),
            ),
            limit,
        )

        tm.that(
            diagnostic,
            has=[
                f"memory_limit={limit.memory_limit_mb} MiB",
                f"timeout={limit.timeout_seconds}s",
                f"exit={c.Infra.PROCESS_TIMEOUT_EXIT_CODE}",
                "signal=none",
            ],
        )

    def test_mypy_signal_diagnostic_preserves_both_output_streams(self) -> None:
        """Expose traceback output when Mypy also writes an error banner."""
        limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT, timeout_seconds=60
        )
        diagnostic = u.Infra.mypy_failure_diagnostic(
            m.Cli.CommandOutput(
                stdout="Traceback: checker frame",
                stderr="INTERNAL ERROR",
                outcome=m.Cli.ProcessOutcome(
                    raw_return_code=-11, timed_out=False, forwarded_signal=None
                ),
            ),
            limit,
        )

        tm.that(diagnostic, has=["Traceback: checker frame", "INTERNAL ERROR"])
