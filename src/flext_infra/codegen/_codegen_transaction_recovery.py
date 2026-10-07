"""Journal persistence and recovery owner for the generation transaction.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra.codegen._mise_artifacts_journal import FlextInfraMiseArtifactsJournal
from flext_infra.codegen._mise_artifacts_recovery import FlextInfraMiseRecovery
from flext_infra.codegen._mise_artifacts_state import FlextInfraMiseArtifactsState
from flext_infra.codegen.codegen_preconditions import FlextInfraCodegenPreconditions
from flext_infra.codegen.file_leases import FlextInfraCodegenFileLeases
from flext_infra.codegen.mise_artifacts_workspace import FlextInfraMiseWorkspacePlanner
from flext_infra.models import m
from flext_infra.typings import t

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenTransactionRecovery(FlextInfraCodegenFileLeases):
    """Persist owned journal receipts and recover exactly what they authorize."""

    def __init__(self, owner: p.Infra.MiseArtifactsOwner) -> None:
        """Initialize journal planning and recovery for one Mise artifact owner."""
        super().__init__()
        self._planner = FlextInfraMiseWorkspacePlanner(owner)
        self._recovery = FlextInfraMiseRecovery()
        self._journal_receipts: MutableMapping[Path, m.Cli.AtomicFileState] = {}

    def _materialize_directories(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        journal_state: m.Cli.AtomicFileState,
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Create and durably bind one directory identity at a time.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        result_type = r[tuple[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]
        current_journal = journal
        current_state = journal_state
        for intent in current_journal.directories:
            if intent.created is not None:
                continue
            created = FlextInfraMiseArtifactsState.create_journaled_directory(
                layout,
                current_journal.directories,
                intent,
            )
            if created.failure:
                return result_type.from_failure(
                    self._recover_failure(
                        layout,
                        created.error or f"cannot create directory {intent.path}",
                    ),
                )
            directories = tuple(
                created.value if entry.path == intent.path else entry
                for entry in current_journal.directories
            )
            recorded = FlextInfraMiseArtifactsJournal.record_directories(
                current_journal,
                directories,
            )
            if recorded.failure:
                failed = self._compensate_directory_persistence(
                    layout,
                    created.value,
                    recorded.error or f"cannot record directory {intent.path}",
                    journal_write=False,
                )
                return result_type.from_failure(failed)
            persisted = self._write_journal(
                layout,
                recorded.value,
                expected=current_state,
            )
            if persisted.failure:
                failed = self._compensate_directory_persistence(
                    layout,
                    created.value,
                    persisted.error or f"cannot persist directory {intent.path}",
                    journal_write=True,
                )
                return result_type.from_failure(failed)
            current_journal = recorded.value
            current_state = persisted.value
        manifested = FlextInfraMiseArtifactsJournal.record_transaction_manifests(
            layout,
            current_journal,
        )
        if manifested.failure:
            return result_type.from_failure(manifested)
        for previous, recorded in zip(
            current_journal.directories,
            manifested.value.directories,
            strict=True,
        ):
            if (
                previous.manifest is None
                and recorded.manifest is not None
                and recorded.manifest.entries
            ):
                return result_type.fail(
                    f"new transaction tree contains unregistered entries: "
                    f"{recorded.path}",
                )
        persisted = self._write_journal(
            layout,
            manifested.value,
            expected=current_state,
        )
        if persisted.failure:
            return result_type.from_failure(persisted)
        return result_type.ok((manifested.value, persisted.value))

    def _compensate_directory_persistence(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        created: m.Infra.CodegenJournalDirectory,
        failure: str,
        *,
        journal_write: bool,
    ) -> p.Result[bool]:
        """Compensate only this invocation's exact empty-directory effect.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        compensated = FlextInfraMiseArtifactsState.compensate_created_directory(created)
        if compensated.failure:
            return r[bool].fail(
                f"{failure}; created-directory compensation failed: "
                f"{compensated.error}",
            )
        if journal_write:
            return self._handle_journal_write_failure(layout, failure)
        return self._recover_failure(layout, failure)

    def _recover_prepared(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
    ) -> p.Result[bool]:
        """Recover only the latest journal receipt written by this transaction.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        expected = self._journal_receipts.get(layout.journal_path)
        if expected is None:
            observed = FlextInfraMiseArtifactsState.journal_state(layout)
            if observed.failure:
                return r[bool].from_failure(observed)
            snapshot = FlextInfraMiseArtifactsState.journal_snapshot(observed.value)
            if snapshot is not None and snapshot.content is None:
                return r[bool].ok(value=False)
            return r[bool].fail("generation recovery has no invocation journal receipt")
        return self._recover(layout, expected=expected)

    def _reconcile(self, identity: m.Infra.GitIdentityReport) -> p.Result[bool]:
        layout = self._planner.journal_layout(identity)
        if layout.failure:
            return r[bool].from_failure(layout)
        journal = FlextInfraMiseArtifactsState.journal_state(layout.value)
        if journal.failure:
            return r[bool].from_failure(journal)
        journal_snapshot = FlextInfraMiseArtifactsState.journal_snapshot(journal.value)
        if journal_snapshot is not None and journal_snapshot.content is not None:
            return self._recover(layout.value)
        residue = FlextInfraMiseArtifactsState.transaction_residue(layout.value)
        if residue:
            return r[bool].fail(
                f"generation staging has no journal authority: {residue[0]}",
            )
        return r[bool].ok(value=True)

    def _handle_journal_write_failure(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        failure: str,
    ) -> p.Result[bool]:
        observed = FlextInfraMiseArtifactsState.journal_state(layout)
        if observed.failure:
            return r[bool].fail(
                f"{failure}; journal inspection failed: {observed.error}",
            )
        observed_snapshot = FlextInfraMiseArtifactsState.journal_snapshot(
            observed.value,
        )
        if observed_snapshot is None or observed_snapshot.content is None:
            return r[bool].fail(f"{failure}; durable journal disappeared")
        return self._recover_failure(layout, failure)

    def _verified_prepublication_barriers(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        plan: m.Infra.MiseToolchainWorkspacePlan,
        all_sources: t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]],
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[bool]:
        """Re-verify every pre-publication barrier, recovering on the first breach.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        barriers = FlextInfraCodegenPreconditions.prepublication_barriers(
            plan,
            tuple(source for _phase, source in all_sources),
            tuple(item.before for item in publications),
        )
        if barriers.failure:
            return r[bool].from_failure(
                self._recover_failure(
                    layout,
                    barriers.error or "generation barrier failed",
                ),
            )
        return r[bool].ok(value=True)

    def _recover_failure(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        failure: str,
    ) -> p.Result[bool]:
        recovered = self._recover_prepared(layout)
        if recovered.failure:
            # Recovery must never replace the failure that initiated it.
            return r[bool].fail(failure, error_data={"recovery_error": recovered.error})
        return r[bool].fail(failure)

    def _write_journal(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        *,
        expected: m.Cli.AtomicFileState,
    ) -> p.Result[m.Cli.AtomicFileState]:
        """Retain the exact owned receipt for in-session failure recovery.

        Returns:
            The resulting ``p.Result[m.Cli.AtomicFileState]``.

        """
        written = FlextInfraMiseArtifactsJournal.write(
            layout,
            journal,
            expected=expected,
        )
        if written.success:
            self._journal_receipts[layout.journal_path] = written.value
        return written

    def _recover(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        *,
        expected: m.Cli.AtomicFileState | None = None,
    ) -> p.Result[bool]:
        loaded = FlextInfraMiseArtifactsJournal.read(layout)
        if loaded.failure:
            return r[bool].from_failure(loaded)
        journal, journal_state = loaded.value
        if expected is not None and journal_state != expected:
            return r[bool].fail(
                "generation recovery journal changed from owned receipt",
            )
        if journal.file_participants:
            if journal.projects:
                return r[bool].fail(
                    "mixed Mise and file-only recovery requires explicit composition",
                )
            recovery_layout = self._planner.file_layout(
                layout.scope_root,
                {item.selector: item.root for item in journal.file_participants},
                transaction_id=journal.transaction_id,
            )
            if recovery_layout.failure:
                return r[bool].from_failure(recovery_layout)
            if recovery_layout.value.journal_path != layout.journal_path:
                return r[bool].fail("file journal identity changed during recovery")
            with self._lease_file_participants(journal.file_participants):
                recovered = self._recovery.execute(
                    recovery_layout.value,
                    journal,
                    journal_state,
                )
            if recovered.success:
                self._journal_receipts.pop(layout.journal_path, None)
            return recovered
        selectors = tuple(project.selector for project in journal.projects)
        recovery_layout = self._planner.layout_from_selectors(
            layout.scope_root,
            selectors,
            transaction_id=journal.transaction_id,
        )
        if recovery_layout.failure:
            return r[bool].from_failure(recovery_layout)
        if recovery_layout.value.journal_path != layout.journal_path:
            return r[bool].fail("generation journal identity changed during recovery")
        recovered = self._recovery.execute(
            recovery_layout.value,
            journal,
            journal_state,
        )
        if recovered.success:
            self._journal_receipts.pop(layout.journal_path, None)
        return recovered
