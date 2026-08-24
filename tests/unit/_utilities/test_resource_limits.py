"""Behavior tests for bounded Mypy process execution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from flext_infra import c, m, u
from flext_tests import tm


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

        tm.that(Path(command[0]).name, eq=c.Infra.TIMEOUT_COMMAND)
        tm.that(command[3], eq=f"{limit.timeout_seconds}s")
        tm.that(Path(command[4]).name, eq=c.Infra.PRLIMIT_COMMAND)
        tm.that(
            command[5], eq=f"--as={limit.memory_limit_bytes}:{limit.memory_limit_bytes}"
        )
        tm.ok(result)
        tm.that(result.value.exit_code, eq=0)
        tm.that(result.value.stdout, has="bounded-process")

    def test_mypy_resource_contract_rejects_non_positive_limits(self) -> None:
        """Reject invalid external configuration before spawning a process."""
        with pytest.raises(ValueError, match="greater than 0"):
            m.Infra.MypyResourceLimit(memory_limit_mb=0, timeout_seconds=0)

    def test_mypy_resource_limit_parses_environment_at_boundary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Convert valid process text once before strict model validation."""
        monkeypatch.setenv(c.Infra.MYPY_MEMORY_LIMIT_MB_ENV, "1024")
        monkeypatch.setenv(c.Infra.MYPY_TIMEOUT_SECONDS_ENV, "120")

        limit = u.Infra.mypy_resource_limit()

        tm.that(limit.memory_limit_mb, eq=1024)
        tm.that(limit.timeout_seconds, eq=120)

    @pytest.mark.parametrize("invalid_value", ["", "1024.0", "-1", " 1024"])
    def test_mypy_resource_limit_rejects_non_integer_environment(
        self, monkeypatch: pytest.MonkeyPatch, invalid_value: str
    ) -> None:
        """Reject non-integer process text before constructing the strict model."""
        monkeypatch.setenv(c.Infra.MYPY_MEMORY_LIMIT_MB_ENV, invalid_value)
        monkeypatch.setenv(c.Infra.MYPY_TIMEOUT_SECONDS_ENV, "120")

        with pytest.raises(
            ValueError, match=f"{c.Infra.MYPY_MEMORY_LIMIT_MB_ENV} must be"
        ):
            u.Infra.mypy_resource_limit()

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
                stdout="", stderr="", exit_code=c.Infra.PROCESS_TIMEOUT_EXIT_CODE
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
                exit_code=-11,
            ),
            limit,
        )

        tm.that(diagnostic, has=["Traceback: checker frame", "INTERNAL ERROR"])
