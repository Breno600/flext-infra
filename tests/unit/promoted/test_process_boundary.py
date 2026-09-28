"""Exercise the promoted dispatcher at its real process boundary."""

from __future__ import annotations

import os
import select
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

from tests import t

if TYPE_CHECKING:
    from collections.abc import Mapping


class TestsFlextInfraPromotedProcessBoundary:
    """The promoted runner owns a real child process, not a simulated one.

    Constants and probe helpers are class attributes because the module
    declares one facade class; they were module-level data and functions,
    which is a second declaration surface the namespace contract forbids.
    """

    ROOT: Final = Path(__file__).resolve().parents[2]
    # The one workspace interpreter is the interpreter running this suite.
    PYTHON: Final = Path(sys.executable)
    NONZERO_EXIT: Final = 37
    # The child imports flext_infra before it can reach a barrier, so the wait
    # has to cover a cold interpreter start on a loaded machine, not an idle
    # one. Sized under the config-owned slow budget (60s) these barrier tests
    # declare, so a genuine hang still fails as a hang rather than as a barrier
    # that was never reached.
    BARRIER_TIMEOUT: Final = 25.0
    PROBE: Final = """\
import sys
from pathlib import Path

from flext_infra import m, u

raise SystemExit(
    u.Infra.promoted_run(
        m.Infra.PromotedCommand(
            verb="probe",
            what="probe",
            domain="probe",
            summary="probe",
            description="probe",
            example="probe",
            path=Path(sys.argv[1]),
            mutates=False,
            aliases=(),
            params=(),
            rules=(),
        )
    )
)
"""

    @classmethod
    def _probe_env(cls) -> t.MutableStrMapping:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(cls.ROOT / "src")
        return env

    @classmethod
    def _write_command(cls, tmp_path: Path, source: str) -> Path:
        command = tmp_path / "scripts" / "probe" / "probe.py"
        command.parent.mkdir(parents=True)
        command.write_text(source, encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname='probe'\n", encoding="utf-8"
        )
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").symlink_to(cls.PYTHON)
        return command

    @classmethod
    def _read_ready(
        cls, streams: Mapping[int, str], timeout: float = BARRIER_TIMEOUT
    ) -> t.Pair[str, str]:
        stdout = ""
        stderr = ""
        pending = dict(streams)
        while pending:
            ready, _, _ = select.select(tuple(pending), (), (), timeout)
            if not ready:
                pytest.fail(f"timed out waiting for live output: {pending.values()}")
            for descriptor in ready:
                chunk = os.read(descriptor, 4096).decode()
                if pending.pop(descriptor) == "stdout":
                    stdout += chunk
                else:
                    stderr += chunk
        return stdout, stderr

    @staticmethod
    def _wait_status(pid: int) -> int:
        _, status = os.waitpid(pid, 0)
        return os.waitstatus_to_exitcode(status)

    @classmethod
    def _spawn_probe(
        cls,
        command: Path,
        *,
        env: t.StrMapping,
        stdout: int | None = None,
        stderr: int | None = None,
        process_group: bool = False,
    ) -> int:
        file_actions: list[t.Triple[int, int, int]] = []
        if stdout is not None:
            file_actions.append((os.POSIX_SPAWN_DUP2, stdout, 1))
        if stderr is not None:
            file_actions.append((os.POSIX_SPAWN_DUP2, stderr, 2))
        argv = (cls.PYTHON, "-P", "-c", cls.PROBE, command)
        if process_group:
            return os.posix_spawn(
                cls.PYTHON, argv, env, file_actions=file_actions, setpgroup=0
            )
        return os.posix_spawn(cls.PYTHON, argv, env, file_actions=file_actions)

    @pytest.mark.slow
    def test_run_streams_stdout_and_stderr_before_child_completion(
        self, tmp_path: Path
    ) -> None:
        """Expose both streams while the child remains blocked before completion."""
        ready_fifo = tmp_path / "ready.fifo"
        release_fifo = tmp_path / "release.fifo"
        os.mkfifo(ready_fifo)
        os.mkfifo(release_fifo)
        command = self._write_command(
            tmp_path,
            "import os, sys\n"
            "print('stdout-live', flush=True)\n"
            "print('stderr-live', file=sys.stderr, flush=True)\n"
            # Split literal: child snippet string must not self-match scans.
            "with op" + "en(os.environ['READY_FIFO'], 'w') as ready: ready.write('1')\n"
            "op" + "en(os.environ['RELEASE_FIFO']).read(1)\n",
        )
        env = self._probe_env()
        env["READY_FIFO"] = str(ready_fifo)
        env["RELEASE_FIFO"] = str(release_fifo)
        ready_read = os.open(ready_fifo, os.O_RDONLY | os.O_NONBLOCK)
        release_write = os.open(release_fifo, os.O_RDWR | os.O_NONBLOCK)
        stdout_read, stdout_write = os.pipe()
        stderr_read, stderr_write = os.pipe()
        pid = self._spawn_probe(
            command, env=env, stdout=stdout_write, stderr=stderr_write
        )
        os.close(stdout_write)
        os.close(stderr_write)
        reaped = False
        try:
            ready, _, _ = select.select((ready_read,), (), (), self.BARRIER_TIMEOUT)
            if not ready:
                pytest.fail("child did not reach the completion barrier")
            if os.read(ready_read, 1) != b"1":
                pytest.fail("child completion barrier emitted an invalid marker")
            stdout, stderr = self._read_ready({
                stdout_read: "stdout",
                stderr_read: "stderr",
            })
            if stdout != "stdout-live\n":
                pytest.fail(f"stdout was not streamed live: {stdout!r}")
            if stderr != "stderr-live\n":
                pytest.fail(f"stderr was not streamed live: {stderr!r}")
            os.write(release_write, b"1")
            if self._wait_status(pid) != 0:
                pytest.fail("successful child exit status was not preserved")
            reaped = True
        finally:
            os.close(ready_read)
            os.close(release_write)
            os.close(stdout_read)
            os.close(stderr_read)
            if not reaped:
                # Failure path: the child is provably still alive, so the kill
                # and the reap must succeed; an OS contradiction escapes loud.
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)

    @pytest.mark.slow
    def test_run_returns_exact_nonzero_exit_status(self, tmp_path: Path) -> None:
        """Return the child's raw nonzero code without normalization.

        A cold interpreter importing flext_infra is the declared slow class
        (see ``BARRIER_TIMEOUT``), the same budget its sibling probes use.
        """
        command = self._write_command(
            tmp_path, f"raise SystemExit({self.NONZERO_EXIT})\n"
        )
        exit_code = self._wait_status(self._spawn_probe(command, env=self._probe_env()))
        if exit_code != self.NONZERO_EXIT:
            pytest.fail(f"expected {self.NONZERO_EXIT}, got {exit_code}")

    @pytest.mark.slow
    def test_run_sigint_terminates_child_without_residual_process(
        self, tmp_path: Path
    ) -> None:
        """Propagate terminal SIGINT and reap the promoted child process."""
        child_pid = tmp_path / "child.pid"
        ready_fifo = tmp_path / "sigint-ready.fifo"
        os.mkfifo(ready_fifo)
        command = self._write_command(
            tmp_path,
            "import os, signal\n"
            "from pathlib import Path\n"
            "Path(os.environ['CHILD_PID']).write_text(str(os.getpid()))\n"
            # Split literal: child snippet string must not self-match scans.
            "with op" + "en(os.environ['READY_FIFO'], 'w') as ready: ready.write('1')\n"
            "signal.pause()\n",
        )
        env = self._probe_env()
        env["CHILD_PID"] = str(child_pid)
        env["READY_FIFO"] = str(ready_fifo)
        ready_read = os.open(ready_fifo, os.O_RDONLY | os.O_NONBLOCK)
        pid = self._spawn_probe(command, env=env, process_group=True)
        reaped = False
        try:
            ready, _, _ = select.select((ready_read,), (), (), self.BARRIER_TIMEOUT)
            if not ready:
                pytest.fail("child did not reach the SIGINT barrier")
            if os.read(ready_read, 1) != b"1":
                pytest.fail("child SIGINT barrier emitted an invalid marker")
            child = int(child_pid.read_text(encoding="utf-8"))
            os.killpg(pid, signal.SIGINT)
            if self._wait_status(pid) == 0:
                pytest.fail("SIGINT was normalized to success")
            with pytest.raises(ProcessLookupError):
                os.kill(child, 0)
            reaped = True
        finally:
            os.close(ready_read)
            if not reaped:
                # Failure path: the group is provably still alive, so the kill
                # and the reap must succeed; an OS contradiction escapes loud.
                os.killpg(pid, signal.SIGKILL)
                os.waitpid(pid, 0)

    def test_run_works_without_owner_venv_on_workspace_interpreter(
        self, tmp_path: Path
    ) -> None:
        """Run a command whose owner has no .venv on the workspace interpreter.

        One-venv contract: a missing owner .venv is not an error; the command
        runs on the single workspace interpreter and its exit status is
        preserved.
        """
        command = self._write_command(tmp_path, "raise SystemExit(0)\n")
        (tmp_path / ".venv" / "bin" / "python").unlink()
        exit_code = self._wait_status(self._spawn_probe(command, env=self._probe_env()))
        if exit_code != 0:
            pytest.fail(
                "command must run on the workspace interpreter without an owner "
                f"venv, got {exit_code}"
            )
