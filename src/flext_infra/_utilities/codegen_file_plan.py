"""Generated-file plan decisions exposed through ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import difflib
import errno
import fcntl
import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from itertools import islice
from typing import TYPE_CHECKING, Literal

from flext_cli import m as cli_m, u

from flext_core import r
from flext_infra import c, m, p, t

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraUtilitiesCodegenFilePlan:
    """Derive generated-file effects from immutable planning data."""

    class JournalLeaseTimeoutError(TimeoutError):
        """Another process held the journal lease past the acquisition deadline."""

        def __init__(self, lock_file: Path) -> None:
            self.lock_file = str(lock_file)
            super().__init__(f"journal lease is held elsewhere: {self.lock_file}")

    @staticmethod
    @contextmanager
    def codegen_transaction_lease(journal_path: Path) -> Generator[None]:
        """Hold native ownership without unlinking the journal's lock identity.

        The lease is an exclusive ``flock`` on a ``0o600`` lock file that
        outlives the lease: closing the descriptor releases the kernel lock
        while the file keeps its identity (stable device/inode), and close-time
        errors propagate instead of being swallowed.

        Acquisition waits politely for a held lease up to
        ``c.Infra.JOURNAL_LEASE_WAIT_SECONDS`` (flext-c2kp3): a legitimate fleet
        ``make gen`` holds the lease for minutes, so an immediate non-blocking
        refusal manufactured spurious ``JournalLeaseTimeoutError`` failures
        under ordinary multi-agent traffic. The wait stays bounded, so a truly
        wedged holder still fails loud rather than hanging forever.
        Only native contention (EACCES, EAGAIN or EWOULDBLOCK) enters this wait;
        every other acquisition error escapes unchanged.
        """
        lock_path = journal_path.with_name(f"{journal_path.name}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            deadline = time.monotonic() + c.Infra.JOURNAL_LEASE_WAIT_SECONDS
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as error:
                    if error.errno not in {
                        errno.EACCES,
                        errno.EAGAIN,
                        errno.EWOULDBLOCK,
                    }:
                        raise
                    if time.monotonic() >= deadline:
                        raise FlextInfraUtilitiesCodegenFilePlan.JournalLeaseTimeoutError(
                            lock_path
                        ) from error
                    time.sleep(c.Infra.JOURNAL_LEASE_POLL_SECONDS)
                    continue
                break
            yield
        finally:
            os.close(descriptor)

    @staticmethod
    def planned_file(
        project: Path,
        target: Path,
        *,
        required: bool,
        desired_content: bytes | None,
        desired_mode: int | None,
        source_states: t.SequenceOf[cli_m.Cli.AtomicFileState] = (),
        owner: str = "",
        policy: Literal["full", "merge"] | None = None,
    ) -> p.Result[m.Infra.CodegenFilePlan]:
        """Capture one destination's before state and bind it to its desired state.

        ``required`` says whether the destination must already exist: a removal
        plan reads an existing file, a publication plan tolerates its absence.
        """
        before = u.Cli.atomic_read_binary_file_state(target, required=required)
        if before.failure:
            return r[m.Infra.CodegenFilePlan].from_failure(before)
        return r[m.Infra.CodegenFilePlan].ok(
            m.Infra.CodegenFilePlan(
                project=project,
                path=target,
                before=before.value,
                desired_content=desired_content,
                desired_mode=desired_mode,
                source_states=tuple(source_states),
                owner=owner,
                policy=policy,
            )
        )

    @staticmethod
    def required_file_states(
        paths: t.IterableOf[Path],
    ) -> p.Result[t.VariadicTuple[cli_m.Cli.AtomicFileState]]:
        """Snapshot descriptor-authenticated states for an inventoried path set.

        Every path must exist: an absent input is a planning defect, not an empty
        snapshot.
        """
        states: list[cli_m.Cli.AtomicFileState] = []
        for path in sorted(set(paths)):
            state = u.Cli.atomic_read_binary_file_state(path, required=True)
            if state.failure:
                return r[tuple[cli_m.Cli.AtomicFileState, ...]].from_failure(state)
            states.append(state.value)
        return r[tuple[cli_m.Cli.AtomicFileState, ...]].ok(tuple(states))

    @staticmethod
    def codegen_file_before_state(
        plan: m.Infra.CodegenFilePlan,
    ) -> p.Result[cli_m.Cli.AtomicFileState]:
        """Return a publishable state only after its parent physically exists."""
        if isinstance(plan.before, cli_m.Cli.AtomicDirectoryChainPlan):
            return r[cli_m.Cli.AtomicFileState].fail(
                f"codegen destination parent is absent: {plan.path.parent}"
            )
        return r[cli_m.Cli.AtomicFileState].ok(plan.before)

    @staticmethod
    def atomic_file_state_differs(
        before: cli_m.Cli.AtomicFileState,
        *,
        desired_content: bytes | None,
        desired_mode: int | None,
    ) -> bool:
        """Compare the owner's exact bytes, absence marker, and permission bits.

        Both content fields are binary contracts. Decoding with replacement
        would hide distinct invalid UTF-8 bytes; treating None as empty bytes
        would erase the distinction between an absent and an empty file.
        """
        return before.content != desired_content or before.mode != desired_mode

    @staticmethod
    def codegen_file_requires_effect(plan: m.Infra.CodegenFilePlan) -> bool:
        """Whether publication must change a generated-file destination."""
        if isinstance(plan.before, cli_m.Cli.AtomicDirectoryChainPlan):
            return plan.desired_content is not None
        return FlextInfraUtilitiesCodegenFilePlan.atomic_file_state_differs(
            plan.before,
            desired_content=plan.desired_content,
            desired_mode=plan.desired_mode,
        )

    @staticmethod
    def codegen_file_drift_report(
        plans: t.SequenceOf[m.Infra.CodegenFilePlan], *, limit: int = 40
    ) -> str:
        """Report a bounded byte-exact diff, including line endings and presence.

        Escaped byte lines preserve CRLF, missing final newlines, and non-UTF-8
        content. Only equal bytes with different modes are mode-only drift.
        """
        if limit <= 0:
            msg = "codegen drift report limit must be positive"
            raise ValueError(msg)
        parts: list[str] = []
        for plan in plans:
            if isinstance(plan.before, cli_m.Cli.AtomicDirectoryChainPlan):
                parts.append(f"{plan.path}: absent parent chain gains content")
                continue
            raw_before = plan.before.content
            old_lines = tuple(
                repr(line) for line in (raw_before or b"").splitlines(keepends=True)
            )
            new_lines = tuple(
                repr(line)
                for line in (plan.desired_content or b"").splitlines(keepends=True)
            )
            committed_mode = (
                oct(plan.before.mode) if plan.before.mode is not None else "absent"
            )
            rendered_mode = (
                oct(plan.desired_mode) if plan.desired_mode is not None else "absent"
            )
            header = (
                f"--- {plan.path} (committed mode={committed_mode})"
                f"\n+++ {plan.path} (rendered mode={rendered_mode})"
            )
            diff = tuple(
                islice(difflib.unified_diff(old_lines, new_lines, lineterm=""), limit)
            )
            if diff:
                parts.append("\n".join((header, *diff)))
                continue
            old_bytes = (
                raw_before.encode("utf-8")
                if isinstance(raw_before, str)
                else (raw_before or b"")
            )
            new_bytes = plan.desired_content or b""
            if old_bytes == new_bytes:
                parts.append(
                    f"{header}\n(content equal: mode-only drift "
                    f"observed={committed_mode} desired={rendered_mode})"
                )
                continue
            # Lines are equal but bytes are not: name the exact tail difference
            # (line endings / trailing newline) instead of a false mode claim.
            parts.append(
                f"{header}\n(lines equal, bytes differ: committed {len(old_bytes)}B "
                f"tail={old_bytes[-24:]!r}; rendered {len(new_bytes)}B "
                f"tail={new_bytes[-24:]!r})"
            )
        return "\n----\n".join(parts)


__all__: list[str] = ["FlextInfraUtilitiesCodegenFilePlan"]
