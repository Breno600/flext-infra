"""Behavior tests for bounded Mypy process execution."""

from __future__ import annotations

import os
import pstats
import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, m, u
from tests import u as test_u


class TestsFlextInfraUtilitiesResourceLimits:
    """Behavior tests for the canonical Mypy resource-limit command."""

    def test_mypy_command_checks_source_with_memory_and_time_limits(
        self, tmp_path: Path
    ) -> None:
        """Check a real typed source through both validated resource ceilings."""
        limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
            timeout_seconds=c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT,
        )
        command = u.Infra.mypy_limited_command(
            test_u.Tests.mypy_workload(tmp_path), limit
        )
        result = u.Cli.run_raw(command, timeout=u.Infra.mypy_runner_timeout(limit))

        tm.ok(result)
        tm.that(u.Cli.process_succeeded(result.value.outcome), eq=True)
        tm.that(result.value.outcome.raw_return_code, eq=0)

    def test_mypy_profile_records_the_real_checker(self, tmp_path: Path) -> None:
        """Keep the public profiling contract while removing executable selection."""
        project = test_u.Tests.mypy_workload(tmp_path)
        profile = tmp_path / "checker.pstats"
        invocation = m.Infra.MypyInvocation(
            targets=project.targets,
            config_file=project.config_file,
            profile_output=profile,
        )
        result = u.Cli.run_raw(
            u.Infra.mypy_limited_command(invocation),
            timeout=u.Infra.mypy_runner_timeout(),
        )
        tm.ok(result)
        tm.that(u.Cli.process_succeeded(result.value.outcome), eq=True)
        tm.that(
            bool(pstats.Stats(str(profile)).get_stats_profile().func_profiles), eq=True
        )

    def test_workspace_checker_requires_its_own_environment(
        self, tmp_path: Path
    ) -> None:
        """An unprovisioned target never borrows the orchestrator's interpreter."""
        test_u.Tests.initialize_git_repo(tmp_path)
        project = test_u.Tests.mypy_workload(tmp_path)
        invocation = m.Infra.MypyInvocation(
            targets=project.targets, config_file=project.config_file, workspace=tmp_path
        )
        with pytest.raises(FileNotFoundError, match="managed workspace interpreter"):
            u.Infra.mypy_command(invocation)
        tm.ok(test_u.Tests.create_python_environment(tmp_path))
        with pytest.raises(FileNotFoundError, match="managed workspace checker"):
            u.Infra.mypy_command(invocation)

    def test_supervisor_rejects_executable_selection_before_launch(
        self, tmp_path: Path
    ) -> None:
        """A hostile request cannot turn the supervisor into an arbitrary executor."""
        project = test_u.Tests.mypy_workload(tmp_path)
        command = u.Infra.mypy_limited_command(project, host_system="Darwin")
        injected = project.model_dump_json()[:-1] + ',"command":["/bin/sh"]}'
        result = u.Cli.run_raw(
            (*command[:-1], injected), timeout=u.Infra.mypy_runner_timeout()
        )
        tm.ok(result)
        tm.that(result.value.outcome.raw_return_code, eq=1)
        tm.that(result.value.stderr, has="Extra inputs are not permitted")

    @pytest.mark.parametrize(
        ("scenario", "expected"),
        [
            ("exit", 7),
            ("deadline", 124),
            # Darwin's supervisor samples group RSS and stops it (137); Linux
            # prlimit makes the allocation fail inside the process (exit 1).
            ("memory", (137 if sys.platform == "darwin" else 1)),
        ],
    )
    def test_resource_limit_enforces_exit_deadline_and_memory(
        self, tmp_path: Path, scenario: str, expected: int
    ) -> None:
        """Exercise a real exit, deadline and resident allocation through the owner."""
        limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=max(1, c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT // 8)
            if scenario == "memory"
            else c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
            timeout_seconds=max(1, c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT // 10)
            if scenario == "deadline"
            else c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT,
        )
        source = "import sys,time; print('workload-ready', flush=True); "
        if scenario == "exit":
            source += "sys.exit(7)"
        else:
            if scenario == "memory":
                source += f"allocation = bytearray({limit.memory_limit_bytes * 2}); "
            source += f"time.sleep({limit.timeout_seconds + 1})"
        result = u.Cli.run_raw(
            u.Infra.mypy_limited_command(
                test_u.Tests.mypy_workload(tmp_path, source), limit
            ),
            timeout=u.Infra.mypy_runner_timeout(limit),
        )
        tm.ok(result)
        tm.that(result.value.stdout, has="workload-ready")
        tm.that(result.value.outcome.raw_return_code, eq=expected)
        if scenario == "memory":
            tm.that(
                result.value.stderr,
                has="RSS limit reached" if sys.platform == "darwin" else "MemoryError",
            )

    @pytest.mark.parametrize("expected", [7, 124])
    def test_resource_limit_stops_resistant_descendant_group(
        self, tmp_path: Path, expected: int
    ) -> None:
        """Kill a TERM-resistant descendant after leader exit or deadline."""
        limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
            timeout_seconds=max(1, c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT // 10),
        )
        sleep = f"time.sleep({limit.timeout_seconds + c.Infra.TIMEOUT_KILL_AFTER_SECONDS + 1})"
        tail = "sys.exit(7)" if expected == 7 else sleep
        source = (
            "import subprocess,sys,time; "
            "p=subprocess.Popen([sys.executable, '-c', "
            '"import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); '
            f"print('ready', flush=True); {sleep}\"], "
            "stdout=subprocess.PIPE, text=True); "
            f"p.stdout.readline(); print(p.pid, flush=True); {tail}"
        )
        result = u.Cli.run_raw(
            u.Infra.mypy_limited_command(
                test_u.Tests.mypy_workload(tmp_path, source), limit
            ),
            timeout=u.Infra.mypy_runner_timeout(limit),
        )
        tm.ok(result)
        tm.that(result.value.outcome.raw_return_code, eq=expected)
        tm.that(bool(result.value.stdout.splitlines()), eq=True)
        pid = int(result.value.stdout.splitlines()[0])
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

    def test_resource_limit_stops_workload_on_termination(self, tmp_path: Path) -> None:
        """Preserve external termination and reap the running workload."""
        limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
            timeout_seconds=c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT,
        )
        started = u.Cli.process_start(
            u.Infra.mypy_limited_command(
                test_u.Tests.mypy_workload(
                    tmp_path,
                    "import time; print('ready', flush=True); "
                    f"time.sleep({limit.timeout_seconds + 1})",
                ),
                limit,
            )
        )
        tm.ok(started)
        child = started.value
        try:
            tm.ok(child.stdout_read_until(b"ready", timeout=limit.timeout_seconds))
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
        memory_limit = c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT // 2
        timeout_limit = c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT // 2
        with tm.scope(
            env={
                c.Infra.MYPY_MEMORY_LIMIT_MB_ENV: str(memory_limit),
                c.Infra.MYPY_TIMEOUT_SECONDS_ENV: str(timeout_limit),
            }
        ):
            limit = u.Infra.mypy_resource_limit()

        tm.that(limit.memory_limit_mb, eq=memory_limit)
        tm.that(limit.timeout_seconds, eq=timeout_limit)

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
                timeout_seconds=c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT,
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
            memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
            timeout_seconds=c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT,
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
            memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
            timeout_seconds=c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT,
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
