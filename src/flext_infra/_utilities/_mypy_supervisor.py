"""Darwin Mypy supervisor: sampled process-group RSS and wall-clock deadline.

This executable module uses only the standard library, so supervising starts
before importing the checker or its dependencies. Darwin's initial VM mappings
can already exceed the configured memory budget; RLIMIT_AS cannot represent a
usable allocation ceiling there. RSS is sampled every 100 ms instead. It is a
termination threshold, not a kernel allocation barrier: transient overshoot is
possible. Linux retains its kernel-enforced address-space limit.
"""

from __future__ import annotations

import os
import signal
import subprocess  # nosec B404 - std-lib-only bootstrap supervisor; must run before fleet imports
import sys
import time
from types import FrameType

from flext_infra import t


class FlextInfraMypyDarwinSupervisor:
    """Own the checker process group and stop it on resource-control failure."""

    class ProcessGroupAbsentError(Exception):
        """The target process group has no live member; nothing to signal."""

    @classmethod
    def _signal_group(cls, pid: int, signum: int) -> None:
        """Signal one process group, surfacing absence as a typed domain outcome.

        Raises ProcessGroupAbsent when a native accounting proof shows no live
        member (Darwin may retain an unsignalable zombie-only group): the
        absence is raised, never returned as a silent sentinel.
        """
        try:
            os.killpg(pid, signum)
        except ProcessLookupError as err:
            raise FlextInfraMypyDarwinSupervisor.ProcessGroupAbsentError from err
        except PermissionError:
            # Darwin may retain an unsignalable zombie-only process group.
            # Only a native accounting proof of no live member closes it.
            if cls._usage(pid)[1]:
                raise
            raise FlextInfraMypyDarwinSupervisor.ProcessGroupAbsentError from None

    @staticmethod
    def _usage(pid: int) -> t.Pair[int, bool]:
        snapshot = subprocess.run(  # nosec B603 - constant argv (/bin/ps), no shell, no untrusted input
            ("/bin/ps", "-axo", "pgid=,rss=,stat="),
            capture_output=True,
            text=True,
            check=True,
            timeout=1,
        )
        total_kib = 0
        alive = False
        for row in snapshot.stdout.splitlines():
            group, rss, state = row.split()
            if int(group) == pid and not state.startswith("Z"):
                total_kib += int(rss)
                alive = True
        return total_kib * 1024, alive

    @classmethod
    def run(
        cls,
        command: t.SequenceOf[str],
        memory_bytes: int,
        timeout: int,
        kill_after: int,
    ) -> int:
        """Run one command with inherited streams and bounded group lifetime."""
        if not command or min(memory_bytes, timeout, kill_after) <= 0:
            msg = "command and positive memory, timeout and kill-after are required"
            raise ValueError(msg)
        # Probe the native accounting boundary before launching any workload.
        cls._usage(os.getpgrp())
        deadline = time.monotonic() + timeout
        child = subprocess.Popen(  # nosec B603 - fleet-constructed command; group ownership is the module's purpose
            command, start_new_session=True
        )
        received_signal: int = 0

        def receive_signal(signum: int, _frame: FrameType | None) -> None:
            nonlocal received_signal
            received_signal = signum

        previous = {
            signum: signal.signal(signum, receive_signal)
            for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
        }
        try:
            while (exit_code := child.poll()) is None:
                if received_signal:
                    return 128 + received_signal
                if time.monotonic() >= deadline:
                    sys.stderr.write("Mypy wall-time limit reached\n")
                    return 124
                if cls._usage(child.pid)[0] > memory_bytes:
                    sys.stderr.write("Mypy out of memory: RSS limit reached\n")
                    return 137
                time.sleep(0.1)
            return exit_code if exit_code >= 0 else 128 - exit_code
        finally:
            # Always clean descendants, even when their leader already exited.
            # Why ask-first: signaling only a natively-proven-live group keeps
            # absence out of the cleanup path entirely — no suppression, no
            # sentinel; a race between proof and signal propagates visibly.
            try:
                if cls._usage(child.pid)[1]:
                    cls._signal_group(child.pid, received_signal or signal.SIGTERM)
                end = time.monotonic() + kill_after
                while time.monotonic() < end:
                    child.poll()
                    if not cls._usage(child.pid)[1]:
                        break
                    time.sleep(0.05)
            finally:
                try:
                    if cls._usage(child.pid)[1]:
                        cls._signal_group(child.pid, signal.SIGKILL)
                    child.wait()
                finally:
                    for signum, handler in previous.items():
                        signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(
        FlextInfraMypyDarwinSupervisor.run(
            sys.argv[4:], int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
        )
    )
