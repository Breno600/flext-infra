"""Darwin Mypy supervisor: sampled process-group RSS and wall-clock deadline.

This supervisor validates the owned checker request before launching Mypy.
Darwin's initial VM mappings
can already exceed the configured memory budget; RLIMIT_AS cannot represent a
usable allocation ceiling there. RSS is sampled every
``c.Infra.MYPY_SUPERVISOR_POLL_SECONDS`` instead. It is a
termination threshold, not a kernel allocation barrier: transient overshoot is
possible. Linux retains its kernel-enforced address-space limit.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import signal
import sys
import time
from types import FrameType
from typing import TYPE_CHECKING

from flext_cli import u

from flext_infra import c, m, t
from flext_infra._utilities import FlextInfraUtilitiesResourceLimits

if TYPE_CHECKING:
    from flext_cli import s


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

        Raises:
            PermissionError: If ``cls._usage(pid)[1]``.
            ProcessGroupAbsentError: If a ``ProcessLookupError`` is caught; or if a
                ``PermissionError`` is caught.

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

        snapshot = u.Cli.run(
            ("/bin/ps", "-axo", "pgid=,rss=,stat="),
            timeout=c.Infra.MYPY_SUPERVISOR_PS_TIMEOUT,
        ).unwrap()
        total_kib = 0
        alive = False
        for row in snapshot.stdout.splitlines():
            group, rss, state = row.split()
            if int(group) == pid and not state.startswith("Z"):
                total_kib += int(rss)
                alive = True
        return total_kib * c.Infra.BYTES_PER_KIB, alive

    @staticmethod
    def _ask_group_exit(
        child: s.ManagedProcess,
        received_signal: int,
        kill_after: int,
    ) -> None:
        """Ask the live group to exit and wait through the kill-after grace."""
        if FlextInfraMypyDarwinSupervisor._usage(child.pid)[1]:
            FlextInfraMypyDarwinSupervisor._signal_group(
                child.pid,
                received_signal or signal.SIGTERM,
            )
        end = time.monotonic() + kill_after
        while time.monotonic() < end:
            child.poll()
            if not FlextInfraMypyDarwinSupervisor._usage(child.pid)[1]:
                break
            time.sleep(c.Infra.MYPY_SUPERVISOR_SHUTDOWN_POLL_SECONDS)

    @classmethod
    def _kill_group(cls, child: s.ManagedProcess) -> None:
        """Hard-kill a still-live group and reap the leader."""
        if cls._usage(child.pid)[1]:
            cls._signal_group(child.pid, signal.SIGKILL)
        child.wait().unwrap()

    @classmethod
    def _supervised_exit_code(
        cls,
        child: s.ManagedProcess,
        deadline: float,
        memory_bytes: int,
        kill_after: int,
    ) -> int:
        """Relay signals, enforce limits, and clean the group before returning.

        Returns:
            The resulting ``int``.

        """
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
                time.sleep(c.Infra.MYPY_SUPERVISOR_POLL_SECONDS)
            return exit_code if exit_code >= 0 else 128 - exit_code
        finally:
            # Always clean descendants, even when their leader already exited.
            # Why ask-first: signaling only a natively-proven-live group keeps
            # absence out of the cleanup path entirely — no suppression, no
            # sentinel; a race between proof and signal propagates visibly.
            try:
                cls._ask_group_exit(child, received_signal, kill_after)
            finally:
                try:
                    cls._kill_group(child)
                finally:
                    for signum, handler in previous.items():
                        signal.signal(signum, handler)

    @classmethod
    def run(
        cls,
        invocation: m.Infra.MypyInvocation,
        memory_bytes: int,
        timeout: int,
        kill_after: int,
    ) -> int:
        """Run the owned checker with inherited streams and bounded group lifetime.

        Returns:
            The resulting ``int``.

        Raises:
            ValueError: If positive memory, timeout and kill-after are required.

        """
        if min(memory_bytes, timeout, kill_after) <= 0:
            msg = "positive memory, timeout and kill-after are required"
            raise ValueError(msg)
        # Probe the native accounting boundary before launching any workload.
        cls._usage(os.getpgrp())
        deadline = time.monotonic() + timeout
        child = u.Cli.process_start(
            FlextInfraUtilitiesResourceLimits.mypy_command(invocation),
            capture=False,
            start_new_session=True,
        ).unwrap()
        return cls._supervised_exit_code(child, deadline, memory_bytes, kill_after)


if __name__ == "__main__":
    memory, timeout, kill_after, request = sys.argv[1:]
    raise SystemExit(
        FlextInfraMypyDarwinSupervisor.run(
            m.Infra.MypyInvocation.model_validate_json(request),
            int(memory),
            int(timeout),
            int(kill_after),
        ),
    )
