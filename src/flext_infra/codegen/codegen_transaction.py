"""Single extensible transaction coordinator for complete project generation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import m, t, u
from flext_infra.codegen._codegen_transaction_generation import (
    FlextInfraCodegenTransactionGeneration,
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
from flext_infra.codegen.codegen_preconditions import FlextInfraCodegenPreconditions

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenTransaction(FlextInfraCodegenTransactionGeneration):
    """Keep every generation phase recoverable until one final fixed point."""

    def publish_file_phase_locked(
        self,
        scope_root: Path,
        roots: t.MappingKV[str, Path],
        analysis: m.Infra.CodegenPhaseAnalysis,
        directories: t.VariadicTuple[Path],
        validator: Callable[[], p.Result[bool]],
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
            directories,
        )
        if prepared.failure:
            return result_type.from_failure(prepared)
        published = self.append_phase_locked(
            prepared.value,
            analysis.phase,
            analysis.files,
        )
        if published.failure:
            return result_type.from_failure(published)
        return self.commit_locked(published.value, validator)

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
        if prepare:
            reconciled = self._reconcile(identity)
            if reconciled.failure:
                return r[T].from_failure(reconciled)
        return operation(identity.repo_root)

    def commit_locked(
        self,
        session: m.Infra.CodegenTransactionSession,
        validator: Callable[[], p.Result[bool]],
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Validate final reality while recoverable, then commit and clean up.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        """
        exact = verify.journal_destinations_live(session.plan.layout, session.journal)
        if exact.failure:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    session.plan.layout,
                    exact.error or "publication identity changed",
                ),
            )
        validated = validator()
        if validated.failure or not validated.value:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    session.plan.layout,
                    validated.error or "generation fixed-point validation failed",
                ),
            )
        committed = self._verified_commit(session)
        if committed.failure:
            return r[t.VariadicTuple[Path]].from_failure(committed)
        cleaned = journal_io.cleanup(
            session.plan.layout,
            committed.value[0],
            committed.value[1],
        )
        if cleaned.failure:
            return r[t.VariadicTuple[Path]].from_failure(cleaned)
        self._journal_receipts.pop(session.plan.layout.journal_path, None)
        return r[t.VariadicTuple[Path]].ok(session.written_files)

    def _verified_commit(
        self,
        session: m.Infra.CodegenTransactionSession,
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Re-prove the journal, commit it, and durably persist the commit.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]
        ]
        layout = session.plan.layout
        unchanged = FlextInfraCodegenPreconditions.unchanged_journal(
            session,
            "generation journal changed before commit",
        )
        if unchanged.failure:
            return result_type.from_failure(unchanged)
        session = unchanged.value
        exact = verify.journal_destinations_live(layout, session.journal)
        if exact.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    exact.error or "publication identity changed before commit",
                ),
            )
        committed = journal_io.commit(session.journal)
        if committed.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    committed.error or "cannot validate generation commit",
                ),
            )
        committed_state = self._write_journal(
            layout,
            committed.value,
            expected=session.journal_state,
        )
        if committed_state.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    committed_state.error or "cannot persist generation commit",
                ),
            )
        return result_type.ok((committed.value, committed_state.value))

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
