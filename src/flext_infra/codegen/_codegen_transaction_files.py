"""File-only transaction lane: leases, guards, and the durable file cursor.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import m, t, u
from flext_infra.codegen._codegen_transaction_recovery import (
    FlextInfraCodegenTransactionRecovery,
)
from flext_infra.codegen._mise_artifacts_journal import (
    FlextInfraMiseArtifactsJournal as journal_io,
)
from flext_infra.codegen._mise_artifacts_state import (
    FlextInfraMiseArtifactsState as state,
)
from flext_infra.codegen._mise_artifacts_verification import (
    FlextInfraMiseArtifactsVerification as verify,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenTransactionFiles(FlextInfraCodegenTransactionRecovery):
    """File-transaction lane of the generation transaction coordinator."""

    def run_files_locked[T](
        self,
        roots: t.MappingKV[str, Path],
        operation: Callable[[Path], p.Result[T]],
    ) -> p.Result[T]:
        """Hold Git and shared destination leases before planning or recovery.

        Returns:
            The resulting ``p.Result[T]``.

        """
        identity = self._planner.scope_identity()
        if identity.failure:
            return r[T].from_failure(identity)
        proposed = self._planner.file_layout(
            identity.value.repo_root,
            roots,
            transaction_id=secrets.token_hex(16),
        )
        if proposed.failure:
            return r[T].from_failure(proposed)
        with u.Infra.codegen_transaction_lease(
            self._planner.journal_path(identity.value),
        ):
            participants = {
                item.root: item for item in proposed.value.file_participants
            }
            observed = state.journal_state(proposed.value)
            if observed.failure:
                return r[T].from_failure(observed)
            snapshot = state.journal_snapshot(observed.value)
            if snapshot is not None and snapshot.content is not None:
                loaded = journal_io.read(proposed.value)
                if loaded.failure:
                    return r[T].from_failure(loaded)
                for participant in loaded.value[0].file_participants:
                    current = participants.get(participant.root)
                    if current is not None and (current.device, current.inode) != (
                        participant.device,
                        participant.inode,
                    ):
                        return r[T].fail(
                            "file capability identity changed before recovery",
                        )
                    participants[participant.root] = participant
            with self._lease_file_participants(
                tuple(participants.values()),
                held_roots=frozenset({identity.value.repo_root.resolve()}),
            ):
                return self._run_locked_operation(
                    identity.value,
                    prepare=True,
                    operation=operation,
                )

    def begin_files_locked(
        self,
        scope_root: Path,
        roots: t.MappingKV[str, Path],
        inputs: t.VariadicTuple[m.Cli.AtomicFileState],
    ) -> p.Result[m.Infra.CodegenTransactionSession]:
        """Create a durable file-only cursor using the existing journal lifecycle.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionSession]``.

        """
        result_type = r[m.Infra.CodegenTransactionSession]
        if set(roots.values()) - self._file_leases.keys():
            return result_type.fail("file session requires every destination lease")
        transaction_id = secrets.token_hex(16)
        prepared = self._planner.file_layout(
            scope_root,
            roots,
            transaction_id=transaction_id,
        )
        if prepared.failure:
            return result_type.from_failure(prepared)
        layout = prepared.value
        mismatch = self._file_lease_mismatch(layout)
        if mismatch is not None:
            return result_type.fail(mismatch)
        plan = m.Infra.CodegenFileSessionPlan(layout=layout)
        opened = self._open_file_transaction_journal(
            layout,
            plan,
            inputs,
            transaction_id,
        )
        if opened.failure:
            return result_type.from_failure(opened)
        journal, journal_state = opened.value
        return result_type.ok(
            m.Infra.CodegenTransactionSession(
                plan=plan,
                journal=journal,
                journal_state=journal_state,
            ),
        )

    def _file_lease_mismatch(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
    ) -> str | None:
        """Describe the first file participant whose identity left its lease.

        Returns:
            The mismatch message, or None when every participant still matches.

        """
        for participant in layout.file_participants:
            leased = self._file_leases[participant.root]
            if (participant.device, participant.inode) != (leased.device, leased.inode):
                return "file capability root changed after lease acquisition"
        return None

    @staticmethod
    def _file_transaction_guard(
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        inputs: t.VariadicTuple[m.Cli.AtomicFileState],
    ) -> p.Result[
        t.Pair[t.VariadicTuple[m.Infra.CodegenJournalDirectory], m.Cli.AtomicFileState]
    ]:
        """Require a recovered-absent journal, no residue, and stable inputs.

        Returns:
            The resulting ``p.Result[t.Pair[t.VariadicTuple[
                m.Infra.CodegenJournalDirectory], m.Cli.AtomicFileState]]`` with
            the planned transaction directories and the absent-journal baseline.

        """
        result_type = r[
            t.Pair[
                t.VariadicTuple[m.Infra.CodegenJournalDirectory],
                m.Cli.AtomicFileState,
            ]
        ]
        observed = state.journal_state(layout)
        if observed.failure:
            return result_type.from_failure(observed)
        before = state.journal_snapshot(observed.value)
        if before is None or before.content is not None:
            return result_type.fail(
                "file transaction journal is not absent after recovery",
            )
        if state.transaction_residue(layout):
            return result_type.fail("file transaction has unowned staging residue")
        stable = verify.states_current(inputs)
        if stable.failure:
            return result_type.from_failure(stable)
        directories = state.plan_transaction_directories(layout)
        if directories.failure:
            return result_type.from_failure(directories)
        return result_type.ok((directories.value, before))

    def _open_file_transaction_journal(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        plan: m.Infra.CodegenFileSessionPlan,
        inputs: t.VariadicTuple[m.Cli.AtomicFileState],
        transaction_id: str,
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Open, persist, materialize, and durably prepare the file journal.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]
        ]
        guarded = self._file_transaction_guard(layout, inputs)
        if guarded.failure:
            return result_type.from_failure(guarded)
        directories, before = guarded.value
        journal = journal_io.begin(
            plan,
            transaction_id=transaction_id,
            sources=tuple(("docs", source) for source in inputs),
            directories=directories,
        )
        if journal.failure:
            return result_type.from_failure(journal)
        opened = self._materialize_journal(layout, journal.value, expected=before)
        if opened.failure:
            return result_type.from_failure(opened)
        recorded, recorded_state = opened.value
        prepared_journal = journal_io.append_prepared(plan, recorded, ())
        if prepared_journal.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    prepared_journal.error or "file preparation failed",
                ),
            )
        ready = self._write_journal(
            layout,
            prepared_journal.value,
            expected=recorded_state,
        )
        if ready.failure:
            return result_type.from_failure(
                self._handle_journal_write_failure(
                    layout,
                    ready.error or "file cursor persistence failed",
                ),
            )
        return result_type.ok((prepared_journal.value, ready.value))

    def _materialize_journal(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        *,
        expected: m.Cli.AtomicFileState,
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Persist one journal revision, then materialize its planned directories.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]
        ]
        persisted = self._write_journal(layout, journal, expected=expected)
        if persisted.failure:
            return result_type.from_failure(persisted)
        materialized = self._materialize_directories(layout, journal, persisted.value)
        if materialized.failure:
            return result_type.from_failure(materialized)
        recorded, recorded_state = materialized.value
        return result_type.ok((recorded, recorded_state))
