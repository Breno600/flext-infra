"""Behavior tests for bounded Mypy process execution.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import pstats
import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m, u
from tests import u as test_u


class TestsFlextInfraUtilitiesResourceLimits:
    """Behavior tests for the canonical Mypy resource-limit command."""

    @staticmethod
    def test_mypy_command_checks_source_with_memory_and_time_limits(
        tmp_path: Path,
    ) -> None:
        """Check a real typed source through both validated resource ceilings."""
        limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
            timeout_seconds=config.Infra.tooling.tools.mypy.timeout_seconds,
        )
        command = u.Infra.mypy_limited_command(
            test_u.Tests.mypy_workload(tmp_path),
            limit,
        )
        result = u.Cli.run_raw(command, timeout=u.Infra.mypy_runner_timeout(limit))

        tm.ok(result)
        tm.that(u.Cli.process_succeeded(result.value.outcome), eq=True)

    @staticmethod
    def test_mypy_profile_records_the_real_checker(tmp_path: Path) -> None:
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
            bool(pstats.Stats(str(profile)).get_stats_profile().func_profiles),
            eq=True,
        )

    @staticmethod
    def test_mypy_budget_resolves_the_project_tooling_overlay(
        tmp_path: Path,
    ) -> None:
        """A project tooling.yaml budget drives the runner timeout."""
        budget = config.Infra.tooling.tools.mypy.timeout_seconds // 2
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "tooling.yaml").write_text(
            f"Infra:\n  tooling:\n    tools:\n      mypy:\n        timeout_seconds: {budget}\n",
            encoding="utf-8",
        )
        expected_limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=u.Infra.mypy_resource_limit().memory_limit_mb,
            timeout_seconds=budget,
        )

        tm.that(
            u.Infra.mypy_runner_timeout_for_project(tmp_path),
            eq=u.Infra.mypy_runner_timeout(expected_limit),
        )

    @staticmethod
    def test_mypy_budget_overlay_above_the_fleet_bound_fails_loud(
        tmp_path: Path,
    ) -> None:
        """A project budget can only lower the fleet tooling bound."""
        above = config.Infra.tooling.tools.mypy.timeout_seconds + 1
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "tooling.yaml").write_text(
            f"Infra:\n  tooling:\n    tools:\n      mypy:\n        timeout_seconds: {above}\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="exceeds the fleet bound"):
            u.Infra.mypy_runner_timeout_for_project(tmp_path)

    @staticmethod
    def test_mypy_budget_without_overlay_uses_the_fleet_default(
        tmp_path: Path,
    ) -> None:
        """No project overlay falls back to the fleet tooling SSOT."""
        tm.that(
            u.Infra.mypy_runner_timeout_for_project(tmp_path),
            eq=u.Infra.mypy_runner_timeout(),
        )

    @staticmethod
    def test_workspace_checker_requires_its_own_environment(
        tmp_path: Path,
    ) -> None:
        """An unprovisioned target never borrows the orchestrator's interpreter."""
        test_u.Tests.initialize_git_repo(tmp_path)
        project = test_u.Tests.mypy_workload(tmp_path)
        invocation = m.Infra.MypyInvocation(
            targets=project.targets,
            config_file=project.config_file,
            workspace=tmp_path,
        )
        with pytest.raises(FileNotFoundError, match="managed workspace interpreter"):
            u.Infra.mypy_command(invocation)
        tm.ok(test_u.Tests.create_python_environment(tmp_path))
        with pytest.raises(FileNotFoundError, match="managed workspace checker"):
            u.Infra.mypy_command(invocation)

    @staticmethod
    def test_supervisor_rejects_executable_selection_before_launch(
        tmp_path: Path,
    ) -> None:
        """A hostile request cannot turn the supervisor into an arbitrary executor."""
        project = test_u.Tests.mypy_workload(tmp_path)
        command = u.Infra.mypy_limited_command(project, host_system="Darwin")
        injected = project.model_dump_json()[:-1] + ',"command":["/bin/sh"]}'
        result = u.Cli.run_raw(
            (*command[:-1], injected),
            timeout=u.Infra.mypy_runner_timeout(),
        )
        tm.ok(result)
        tm.that(result.value.outcome.raw_return_code, eq=1)
        tm.that(result.value.stderr, has="Extra inputs are not permitted")

    @staticmethod
    @pytest.mark.parametrize(
        ("scenario", "expected"),
        [
            ("exit", 7),
            # Real interpreter startup and controlled group cleanup use the
            # existing integration-harness budget, not the default case budget.
            pytest.param("deadline", 124, marks=pytest.mark.slow),
            # The checker may use different nonzero exit codes while reporting
            # the same bounded allocation failure through its public output.
            ("memory", None),
        ],
    )
    def test_resource_limit_enforces_exit_deadline_and_memory(
        tmp_path: Path,
        scenario: str,
        expected: int | None,
    ) -> None:
        """Exercise a real exit, deadline and resident allocation through the owner."""
        limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=max(1, c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT // 2)
            if scenario == "memory"
            else c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
            timeout_seconds=test_u.Tests.mypy_deadline_limit().timeout_seconds
            if scenario == "deadline"
            else config.Infra.tooling.tools.mypy.timeout_seconds,
        )
        source = "import sys,time; print('workload-ready', flush=True); "
        if scenario == "exit":
            source += "sys.exit(7)"
        else:
            if scenario == "memory":
                source += f"allocation = bytearray({limit.memory_limit_bytes * 2}); "
            source += f"time.sleep({limit.timeout_seconds + 1})"
        command = u.Infra.mypy_limited_command(
            test_u.Tests.mypy_workload(tmp_path, source),
            limit,
        )
        result = u.Cli.run_raw(command, timeout=u.Infra.mypy_runner_timeout(limit))
        tm.ok(result)
        tm.that(result.value.stdout, has="workload-ready")
        if scenario == "memory":
            tm.that(
                any(str(limit.memory_limit_bytes) in part for part in command[:-1]),
                eq=True,
            )
            tm.that(u.Cli.process_succeeded(result.value.outcome), eq=False)
            tm.that(result.value.outcome.timed_out, eq=False)
            # The configured bound itself must cause the stop: only a
            # resource-exhaustion outcome (memory marker or signal) yields the
            # public diagnostic, so an unrelated checker failure after the
            # workload start can no longer satisfy this scenario.
            diagnostic = tm.not_none(
                u.Infra.mypy_failure_diagnostic(result.value, limit),
            )
            tm.that(diagnostic, has=f"memory_limit={limit.memory_limit_mb} MiB")
            if sys.platform == "darwin":
                tm.that(result.value.stderr, has="RSS limit reached")
        else:
            tm.that(result.value.outcome.raw_return_code, eq=expected)

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize(
        ("leader_exits", "expected"),
        [(True, 7), (False, c.Infra.PROCESS_TIMEOUT_EXIT_CODE)],
    )
    def test_resource_limit_stops_resistant_descendant_group(
        tmp_path: Path,
        *,
        leader_exits: bool,
        expected: int,
        request: pytest.FixtureRequest,
    ) -> None:
        """Kill a TERM-resistant descendant after leader exit or deadline."""
        limit = test_u.Tests.mypy_deadline_limit()
        policy = config.Infra.tooling.tools.pytest
        pid_file = tmp_path / "descendant.pid"
        error_file = tmp_path / "descendant.stderr"
        request.addfinalizer(
            lambda: test_u.Tests.reap_mypy_descendant(
                pid_file,
                policy.termination_grace_seconds,
            ),
        )
        sleep = f"time.sleep({u.Infra.mypy_runner_timeout(limit) + policy.slow_timeout_seconds})"
        tail = f"sys.exit({expected})" if leader_exits else sleep
        descendant = (
            "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            f"print('ready', flush=True); {sleep}"
        )
        source = (
            "import subprocess,sys,time\nfrom pathlib import Path\n"
            f"errors = Path({str(error_file)!r})\n"
            "with errors.open('w', encoding='utf-8') as stderr:\n"
            f"    p = subprocess.Popen([sys.executable, '-c', {descendant!r}], "
            "stdout=subprocess.PIPE, stderr=stderr, text=True)\n"
            f"    Path({str(pid_file)!r}).write_text(str(p.pid), encoding='utf-8')\n"
            "    if p.stdout is None or p.stdout.readline() != 'ready\\n':\n"
            "        stderr.flush()\n"
            "        sys.stderr.write(errors.read_text(encoding='utf-8'))\n"
            "        raise RuntimeError('descendant readiness failed')\n"
            f"    print(p.pid, flush=True)\n    {tail}"
        )
        result = u.Cli.run_raw(
            u.Infra.mypy_limited_command(
                test_u.Tests.mypy_workload(tmp_path, source),
                limit,
            ),
            timeout=u.Infra.mypy_runner_timeout(limit),
        )
        tm.ok(result)
        tm.that(result.value.outcome.raw_return_code, eq=expected)
        tm.that(bool(result.value.stdout.splitlines()), eq=True)
        pid = int(result.value.stdout.splitlines()[0])
        tm.that(int(pid_file.read_text(encoding=c.Cli.ENCODING_DEFAULT)), eq=pid)
        tm.that(error_file.read_text(encoding=c.Cli.ENCODING_DEFAULT), empty=True)
        remaining = u.Cli.run_raw(
            ("/bin/ps", "-p", str(pid), "-o", "stat="),
            timeout=policy.termination_grace_seconds,
        )
        tm.ok(remaining)
        state = remaining.value.stdout.strip()
        if sys.platform == "darwin":
            tm.that(not state or state.startswith("Z"), eq=True)
        # GNU timeout reaps the resistant group when it stops the leader at
        # the deadline; on a clean leader exit the group outlives the
        # wrapper, so pytest teardown reaps its own descendant instead.
        elif not leader_exits:
            tm.that(not state, eq=True)

    @staticmethod
    def test_resource_limit_stops_workload_on_termination(tmp_path: Path) -> None:
        """Preserve external termination and reap the running workload."""
        limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
            timeout_seconds=config.Infra.tooling.tools.mypy.timeout_seconds,
        )
        started = u.Cli.process_start(
            u.Infra.mypy_limited_command(
                test_u.Tests.mypy_workload(
                    tmp_path,
                    "import time; print('ready', flush=True); "
                    f"time.sleep({limit.timeout_seconds + 1})",
                ),
                limit,
            ),
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

    @staticmethod
    def test_mypy_resource_contract_rejects_non_positive_limits() -> None:
        """Reject invalid external configuration before spawning a process."""
        with pytest.raises(ValueError, match="greater than 0"):
            m.Infra.MypyResourceLimit(memory_limit_mb=0, timeout_seconds=0)

    @staticmethod
    def test_mypy_resource_limit_parses_environment_at_boundary() -> None:
        """Convert valid process text once; the time bound stays the SSOT value."""
        memory_limit = c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT // 2
        with tm.scope(env={c.Infra.MYPY_MEMORY_LIMIT_MB_ENV: str(memory_limit)}):
            limit = u.Infra.mypy_resource_limit()

        tm.that(limit.memory_limit_mb, eq=memory_limit)
        tm.that(
            limit.timeout_seconds,
            eq=config.Infra.tooling.tools.mypy.timeout_seconds,
        )

    @staticmethod
    @pytest.mark.parametrize(
        "invalid_value",
        [
            # Each case spawns a real interpreter that imports the full
            # package tree before the boundary rejects the text, so they run
            # on the integration-harness budget like the deadline scenario
            # above, never on the default case budget.
            pytest.param("", marks=pytest.mark.slow),
            pytest.param("1024.0", marks=pytest.mark.slow),
            pytest.param("-1", marks=pytest.mark.slow),
            pytest.param(" 1024", marks=pytest.mark.slow),
        ],
    )
    def test_mypy_resource_limit_rejects_non_integer_environment(
        invalid_value: str,
    ) -> None:
        """Reject non-integer process text before constructing the strict model.

        A real child process receives the value verbatim, so nothing test-side
        can repair `` 1024`` into a valid limit (``tm.scope`` routes env values
        through a whitespace-stripping model) and the test process's own
        environment is never mutated. The contract under test is exactly that
        the parse boundary performs no such repair.
        """
        result = u.Cli.run_raw(
            [
                sys.executable,
                "-c",
                "from flext_infra import u; u.Infra.mypy_resource_limit()",
            ],
            env={c.Infra.MYPY_MEMORY_LIMIT_MB_ENV: invalid_value},
        )
        tm.ok(result)
        tm.that(u.Cli.process_succeeded(result.value.outcome), eq=False)
        tm.that(result.value.stderr, has=f"{c.Infra.MYPY_MEMORY_LIMIT_MB_ENV} must be")

    @staticmethod
    def test_mypy_resource_contract_rejects_memory_above_ceiling() -> None:
        """Reject a configured limit above the canonical hard ceiling."""
        with pytest.raises(
            ValueError,
            match=f"less than or equal to {c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT}",
        ):
            m.Infra.MypyResourceLimit(
                memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT + 1,
                timeout_seconds=config.Infra.tooling.tools.mypy.timeout_seconds,
            )

    @staticmethod
    def test_mypy_timeout_has_controlled_exit_and_signal_diagnostic() -> None:
        """Expose the configured ceilings and process status on timeout."""
        limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
            timeout_seconds=config.Infra.tooling.tools.mypy.timeout_seconds,
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

    @staticmethod
    def test_mypy_signal_diagnostic_preserves_both_output_streams() -> None:
        """Expose traceback output when Mypy also writes an error banner."""
        limit = m.Infra.MypyResourceLimit(
            memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
            timeout_seconds=config.Infra.tooling.tools.mypy.timeout_seconds,
        )
        diagnostic = u.Infra.mypy_failure_diagnostic(
            m.Cli.CommandOutput(
                stdout="Traceback: checker frame",
                stderr="INTERNAL ERROR",
                outcome=m.Cli.ProcessOutcome(
                    raw_return_code=-11,
                    timed_out=False,
                    forwarded_signal=None,
                ),
            ),
            limit,
        )

        tm.that(diagnostic, has=["Traceback: checker frame", "INTERNAL ERROR"])

    @staticmethod
    def test_mypy_cache_directory_is_project_keyed_and_survives_relocks(
        tmp_path: Path,
    ) -> None:
        """One shared Mypy cache per project, reused by every checkout and relock."""
        spec = config.Infra.codegen.make.mypy_cache

        def checkout(name: str, project: str) -> Path:
            root = tmp_path / name
            root.mkdir()
            (root / c.PYPROJECT_FILENAME).write_text(
                f"[project]\nname = '{project}'\nversion = '0.0.0'\n",
                encoding="utf-8",
            )
            return root

        lane = checkout("lane", "fixture-alpha")
        primary = checkout("primary", "fixture-alpha")
        other = checkout("other", "fixture-beta")
        shared = u.Infra.mypy_cache_directory(lane)
        # Every checkout of one project reuses one analysis.
        tm.that(u.Infra.mypy_cache_directory(primary), eq=shared)
        tm.that(shared.parent.name, eq=Path(spec.external_storage_directory).name)
        # A relock keeps the directory: Mypy revalidates changed modules itself.
        (lane / c.Infra.UV_LOCK_FILENAME).write_text("rotated\n", encoding="utf-8")
        tm.that(u.Infra.mypy_cache_directory(lane), eq=shared)
        # Distinct projects never share one tests package namespace.
        tm.that(u.Infra.mypy_cache_directory(other) != shared, eq=True)
