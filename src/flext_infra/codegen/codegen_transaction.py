"""Single extensible transaction coordinator for complete project generation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import m, r, t, u
from flext_infra.codegen._codegen_transaction_generation import (
    FlextInfraCodegenTransactionGeneration,
)
from flext_infra.codegen._codegen_transaction_phases import (
    FlextInfraCodegenTransactionPhases,
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


class FlextInfraCodegenTransaction(
    FlextInfraCodegenTransactionGeneration,
    FlextInfraCodegenTransactionPhases,
):
    """Keep every generation phase recoverable until one final fixed point."""

    def run_files_locked[T](
        self,
        roots: t.MappingKV[str, Path],
        operation: Callable[[Path], p.Result[T]],
        *,
        prepare: bool = True,
    ) -> p.Result[T]:
        """Hold Git and shared destination leases before planning or recovery.

        Returns:
            The resulting ``p.Result[T]``.

        """
        identity = self._planner.scope_identity()
        if identity.failure:
            return r[T].from_failure(identity)
        authorized = self._authorize_roots(tuple(roots.values()))
        if authorized.failure:
            return r[T].from_failure(authorized)
        preflight = self._preflight_journal(identity.value)
        if preflight.failure:
            return r[T].from_failure(preflight)
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
            participants = self._file_recovery_participants(
                proposed.value,
                prepare=prepare,
            )
            if participants.failure:
                return r[T].from_failure(participants)
            with self._lease_file_participants(
                participants.value,
                held_roots=frozenset({identity.value.repo_root.resolve()}),
            ):
                if not prepare:
                    residue = state.transaction_residue(proposed.value)
                    if residue:
                        return r[T].fail(
                            "unregistered generation staging blocks readiness: "
                            f"{residue[0]}",
                        )
                    u.Cli.info(
                        "stage=file-transaction-readiness "
                        "journal=absent residue=0 leased=true",
                    )
                return self._run_locked_operation(
                    identity.value,
                    prepare=prepare,
                    operation=operation,
                )

    def _file_recovery_participants(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        *,
        prepare: bool,
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenFileParticipant]]:
        """Authenticate current and recorded participants under the journal lease.

        Returns:
            The ordered participants whose destination leases must be acquired.

        """
        result_type = r[t.VariadicTuple[m.Infra.CodegenFileParticipant]]
        participants = {item.root: item for item in layout.file_participants}
        observed = state.journal_state(layout)
        if observed.failure:
            return result_type.from_failure(observed)
        snapshot = state.journal_snapshot(observed.value)
        if snapshot is not None and snapshot.content is not None:
            if not prepare:
                return result_type.fail(
                    "pending file generation journal blocks read-only readiness; "
                    "authenticated apply recovery is required",
                )
            loaded = journal_io.read(layout)
            if loaded.failure:
                return result_type.from_failure(loaded)
            authorized = self._authorize_journal(layout, loaded.value[0])
            if authorized.failure:
                return result_type.from_failure(authorized)
            for participant in loaded.value[0].file_participants:
                current = participants.get(participant.root)
                if current is not None and (current.device, current.inode) != (
                    participant.device,
                    participant.inode,
                ):
                    return result_type.fail(
                        "file capability identity changed before recovery",
                    )
                participants[participant.root] = participant
        return result_type.ok(tuple(participants.values()))

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

    def publish_file_phase_locked(
        self,
        scope_root: Path,
        roots: t.MappingKV[str, Path],
        analysis: m.Infra.CodegenPhaseAnalysis,
        policy: m.Infra.CodegenPhasePublicationPolicy,
        *,
        staged_validator: Callable[
            [
                m.Infra.CodegenTransactionSession,
                t.VariadicTuple[m.Infra.CodegenStagedFile],
            ],
            p.Result[m.Infra.CodegenTransactionSession],
        ]
        | None = None,
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Compose file publication through the same durable phase lifecycle.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        """
        result_type = r[t.VariadicTuple[Path]]
        started = self.begin_files_locked(scope_root, roots, analysis.inputs)
        if started.failure:
            return result_type.from_failure(started)
        prepared = self.append_directories_locked(
            started.value,
            analysis.phase,
            policy.directories,
        )
        if prepared.failure:
            return result_type.from_failure(prepared)
        published = self.append_phase_locked(
            prepared.value,
            analysis.phase,
            analysis.files,
            staged_validator=staged_validator,
        )
        if published.failure:
            return result_type.from_failure(published)
        return self.commit_locked(published.value, policy.validator)

    def validate(
        self,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan] = (),
    ) -> p.Result[bool]:
        """Validate a coherent committed Mise snapshot under the generation lock.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return self.run_locked(
            prepare=False,
            operation=lambda scope_root: self.validate_locked(scope_root, config_plans),
        )

    def validate_locked(
        self,
        scope_root: Path,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan] = (),
    ) -> p.Result[bool]:
        """Reject pending recovery/residue, then exercise real Mise consumers.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        selected = self._selected_validate_layout(scope_root, config_plans)
        if selected.failure:
            return r[bool].from_failure(selected)
        layout = selected.value
        journal = state.journal_state(layout)
        if journal.failure:
            return r[bool].from_failure(journal)
        journal_snapshot = state.journal_snapshot(journal.value)
        if journal_snapshot is not None and journal_snapshot.content is not None:
            return r[bool].fail(
                "pending generation transaction requires apply-mode recovery",
            )
        residue = state.transaction_residue(layout)
        if residue:
            return r[bool].fail(
                f"generation staging has no journal authority: {residue[0]}",
            )
        plan = self._planner.snapshot(layout, config_plans)
        if plan.failure:
            return r[bool].from_failure(plan)
        return verify.live(self._owner, plan.value)

    def _selected_validate_layout(
        self,
        scope_root: Path,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
    ) -> p.Result[m.Infra.MiseToolchainWorkspaceLayout]:
        """Derive the exact topology for a validation pass and select its scope.

        Returns:
            The resulting ``p.Result[m.Infra.MiseToolchainWorkspaceLayout]``.

        """
        layout_result = (
            self._planner.layout_for_config_plans(scope_root, config_plans)
            if config_plans
            else self._planner.layout(scope_root)
        )
        if layout_result.failure:
            return r[m.Infra.MiseToolchainWorkspaceLayout].from_failure(layout_result)
        return self._planner.select_layout(layout_result.value, config_plans)

    @staticmethod
    def validate_phase_analysis_locked(
        analysis: m.Infra.CodegenPhaseAnalysis,
    ) -> p.Result[bool]:
        """Validate a published phase from its immutable planning receipt.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return verify.phase_analysis_live(analysis)

    def run_locked[T](
        self,
        *,
        prepare: bool,
        operation: Callable[[Path], p.Result[T]],
    ) -> p.Result[T]:
        """Own the shared journal before recovery through final publication cleanup.

        Returns:
            The resulting ``p.Result[T]``.

        """
        identity = self._planner.scope_identity()
        if identity.failure:
            return r[T].from_failure(identity)
        preflight = self._preflight_journal(identity.value)
        if preflight.failure:
            return r[T].from_failure(preflight)
        with u.Infra.codegen_transaction_lease(
            self._planner.journal_path(identity.value),
        ):
            return self._run_locked_operation(
                identity.value,
                prepare=prepare,
                operation=operation,
            )

    def _run_locked_operation[T](
        self,
        identity: m.Infra.GitIdentityReport,
        *,
        prepare: bool,
        operation: Callable[[Path], p.Result[T]],
    ) -> p.Result[T]:
        """Reauthenticate and reconcile after the descriptor lock is held.

        Returns:
            The resulting ``p.Result[T]``.

        """
        preflight = self._preflight_journal(identity)
        if preflight.failure:
            return r[T].from_failure(preflight)
        if prepare:
            reconciled = self._reconcile(identity)
            if reconciled.failure:
                return r[T].from_failure(reconciled)
        return operation(identity.repo_root)

    def abort_locked(
        self,
        session: m.Infra.CodegenTransactionSession,
        failure: str,
    ) -> p.Result[bool]:
        """Recover the complete prepared transaction and preserve the cause.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return self._recover_failure(session.plan.layout, failure)

    def publish_prepared_locked[T](
        self,
        session: m.Infra.CodegenTransactionSession,
        operation: Callable[[m.Infra.CodegenTransactionSession], p.Result[T]],
    ) -> p.Result[T]:
        """Run every phase after ``begin_locked`` without stranding its journal.

        A phase that fails or raises after the journal was prepared recovers
        that journal here, while the lease is still held, and keeps the cause:
        a failure is returned unchanged and an exception escapes unchanged.
        A failure whose owner already attempted or refused recovery (it carries
        ``recovery_error``) is returned as-is, never recovered twice.

        Returns:
            The resulting ``p.Result[T]``.

        """
        layout = session.plan.layout
        try:
            outcome = operation(session)
        except Exception as exc:
            recovered = self._recover_prepared(layout)
            if recovered.failure:
                exc.add_note(f"generation recovery failed: {recovered.error}")
            raise
        if outcome.success or (
            outcome.error_data is not None and "recovery_error" in outcome.error_data
        ):
            return outcome
        recovered = self._recover_prepared(layout)
        if recovered.failure:
            return r[T].fail(
                outcome.error or "generation phase failed",
                error_data={
                    **(outcome.error_data or {}),
                    "recovery_error": recovered.error,
                },
            )
        return outcome


__all__: list[str] = ["FlextInfraCodegenTransaction"]
