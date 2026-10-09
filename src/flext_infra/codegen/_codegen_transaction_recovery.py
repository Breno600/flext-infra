"""Journal persistence and recovery owner for the generation transaction.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, r, t, u
from flext_infra.codegen import (
    FlextInfraMiseArtifactsFiles,
    FlextInfraMiseArtifactsJournal,
    FlextInfraMiseArtifactsState,
    FlextInfraMiseRecovery,
    FlextInfraMiseWorkspacePlanner,
)
from flext_infra.codegen.codegen_preconditions import FlextInfraCodegenPreconditions
from flext_infra.codegen.file_leases import FlextInfraCodegenFileLeases

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenTransactionRecovery(FlextInfraCodegenFileLeases):
    """Persist owned journal receipts and recover exactly what they authorize."""

    def __init__(
        self,
        owner: p.Infra.MiseArtifactsOwner,
        *,
        participant_policy: m.Infra.CodegenParticipantPolicy | None = None,
    ) -> None:
        """Initialize journal planning and recovery for one Mise artifact owner."""
        super().__init__(participant_policy)
        self._planner = FlextInfraMiseWorkspacePlanner(owner)
        self._recovery = FlextInfraMiseRecovery()
        self._journal_receipts: MutableMapping[Path, m.Cli.AtomicFileState] = {}

    def participant_policy(self) -> p.Result[m.Infra.CodegenParticipantPolicy]:
        """Snapshot the canonical physical topology without creating state.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenParticipantPolicy]``.
        """
        result_type = r[m.Infra.CodegenParticipantPolicy]
        layout = self._planner.layout()
        if layout.failure:
            return result_type.from_failure(layout)
        roots: list[m.Cli.AtomicDirectoryChainPlan] = []
        for project in layout.value.projects:
            observed = u.Cli.atomic_plan_directory_chain(project.root)
            if observed.failure:
                return result_type.from_failure(observed)
            roots.append(observed.value)
        return result_type.ok(
            m.Infra.CodegenParticipantPolicy(
                scope_root=layout.value.scope_root,
                roots=tuple(roots),
            ),
        )

    def inspect_journal(self) -> p.Result[m.Infra.CodegenFootprint]:
        """Read the actual typed journal without locks, recovery, or directory writes.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenFootprint]``.
        """
        identity = self._planner.scope_identity()
        if identity.failure:
            return r[m.Infra.CodegenFootprint].from_failure(identity)
        return self._inspect_journal(identity.value)

    def validate_footprint(
        self,
        footprint: m.Infra.CodegenFootprint,
    ) -> p.Result[bool]:
        """Authorize one observed journal without acquiring or recovering it.

        Returns:
            The resulting ``p.Result[bool]``.
        """
        if self._participant_policy is None:
            return r[bool].fail("footprint validation requires request authorization")
        identity = self._planner.scope_identity()
        if identity.failure:
            return r[bool].from_failure(identity)
        if identity.value.repo_root != self._participant_policy.scope_root:
            return r[bool].fail("generation authorization coordination root differs")
        layout = self._planner.journal_layout(identity.value)
        if layout.failure:
            return r[bool].from_failure(layout)
        if layout.value.journal_path != footprint.journal_path:
            return r[bool].fail("generation footprint journal anchor changed")
        observed = self._inspect_journal(identity.value)
        if observed.failure:
            return r[bool].from_failure(observed)
        if observed.value.snapshot != footprint.snapshot:
            u.Cli.info(
                "generation journal changed during footprint inspection; "
                f"journal-snapshot-before={footprint.model_dump_json()}",
            )
            u.Cli.info(f"journal-snapshot-after={observed.value.model_dump_json()}")
            fields_equal = observed.value.snapshot.model_dump(
                exclude={"content"},
            ) == footprint.snapshot.model_dump(exclude={"content"})
            bytes_equal = observed.value.snapshot.content == footprint.snapshot.content
            return r[bool].fail(
                "generation journal changed during footprint inspection; "
                f"bytes_equal={bytes_equal}; normalized_fields_equal={fields_equal}",
            )
        if footprint.journal is not None:
            return self._authorize_journal(layout.value, footprint.journal)
        return self._authorize_roots((identity.value.repo_root,))

    def _inspect_journal(
        self,
        identity: m.Infra.GitIdentityReport,
    ) -> p.Result[m.Infra.CodegenFootprint]:
        result_type = r[m.Infra.CodegenFootprint]
        layout = self._planner.journal_layout(identity)
        if layout.failure:
            return result_type.from_failure(layout)
        observed = FlextInfraMiseArtifactsState.journal_state(layout.value)
        if observed.failure:
            return result_type.from_failure(observed)
        snapshot = FlextInfraMiseArtifactsState.journal_snapshot(observed.value)
        if snapshot is None:
            return result_type.fail("generation journal has no physical parent")
        journal: m.Infra.CodegenTransactionJournal | None = None
        if snapshot.content is not None:
            loaded = FlextInfraMiseArtifactsJournal.read(layout.value)
            if loaded.failure:
                return result_type.from_failure(loaded)
            journal, snapshot = loaded.value
        return result_type.ok(
            m.Infra.CodegenFootprint(
                scope_root=identity.repo_root,
                journal_path=layout.value.journal_path,
                snapshot_identity=snapshot.model_dump_json(exclude={"content"}),
                snapshot_sha256=(
                    u.Cli.sha256_bytes(snapshot.content)
                    if snapshot.content is not None
                    else None
                ),
                journal_version=journal.version if journal is not None else None,
                transaction_id=journal.transaction_id if journal is not None else None,
                normalized_journal_sha256=(
                    u.Cli.sha256_bytes(
                        journal.model_dump_json().encode(c.Cli.ENCODING_DEFAULT),
                    )
                    if journal is not None
                    else None
                ),
                journal_state=journal.state if journal is not None else "absent",
                pending_roots=(
                    (
                        *(
                            identity.repo_root / project.selector
                            for project in journal.projects
                        ),
                        *(
                            participant.root
                            for participant in journal.file_participants
                        ),
                    )
                    if journal is not None
                    else ()
                ),
                pending_destinations=(
                    tuple(entry.path for entry in journal.entries)
                    if journal is not None
                    else ()
                ),
                pending_directories=(
                    tuple(directory.path for directory in journal.directories)
                    if journal is not None
                    else ()
                ),
                pending_staging=(
                    (
                        *(
                            participant.transaction_root
                            for participant in journal.file_participants
                        ),
                        *(intent.before.path for intent in journal.staging_intents),
                    )
                    if journal is not None
                    else ()
                ),
                journal=journal,
                snapshot=snapshot,
            ),
        )

    def _authorize_journal(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[bool]:
        """Validate every recorded effect before leases, restore, or cleanup.

        Returns:
            The resulting ``p.Result[bool]``.
        """
        roots = (
            *(layout.scope_root / project.selector for project in journal.projects),
            *(participant.root for participant in journal.file_participants),
        )
        authorized = self._authorize_roots(roots)
        if authorized.failure or self._participant_policy is None:
            return authorized
        if layout.scope_root != self._participant_policy.scope_root:
            return r[bool].fail("generation authorization coordination root differs")
        recorded_layout = layout.model_copy(
            update={"file_participants": journal.file_participants},
        )
        paths: list[Path] = [
            participant.transaction_root for participant in journal.file_participants
        ]
        paths.extend(intent.before.path for intent in journal.staging_intents)
        paths.extend(
            directory.before.path
            for directory in journal.directories
            if directory.before is not None
        )
        paths.extend(
            directory.created.path
            for directory in journal.directories
            if directory.created is not None
        )
        for selector in (
            *(entry.path for entry in journal.entries),
            *(directory.path for directory in journal.directories),
            *(
                selector
                for entry in journal.entries
                for selector in (
                    entry.desired_staging,
                    entry.original_backup,
                    entry.rollback_staging,
                )
                if selector is not None
            ),
        ):
            resolved = FlextInfraMiseArtifactsFiles.resolve_transaction(
                recorded_layout,
                selector,
                purpose="authorized generation effect",
            )
            if resolved.failure:
                return r[bool].from_failure(resolved)
            paths.append(resolved.value)
        return self._authorize_roots(roots, tuple(paths))

    def _preflight_journal(
        self,
        identity: m.Infra.GitIdentityReport,
    ) -> p.Result[bool]:
        """Refuse foreign pending authority before opening even the scope lease.

        Returns:
            The resulting ``p.Result[bool]``.
        """
        if self._participant_policy is None:
            return r[bool].ok(value=True)
        if identity.repo_root != self._participant_policy.scope_root:
            return r[bool].fail("generation authorization coordination root differs")
        authorized = self._authorize_roots((identity.repo_root,))
        if authorized.failure:
            return authorized
        observed = self._inspect_journal(identity)
        if observed.failure:
            return r[bool].from_failure(observed)
        return self.validate_footprint(observed.value)

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
        authorized = self._authorize_journal(layout, journal)
        if authorized.failure:
            return result_type.from_failure(authorized)
        current_journal = journal
        current_state = journal_state
        for intent in current_journal.directories:
            if intent.created is not None:
                continue
            materialized = self._create_and_record_directory(
                layout,
                current_journal,
                current_state,
                intent,
            )
            if materialized.failure:
                return result_type.from_failure(materialized)
            current_journal, current_state = materialized.value
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

    def _create_and_record_directory(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        journal_state: m.Cli.AtomicFileState,
        intent: m.Infra.CodegenJournalDirectory,
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Create one journaled directory, then record and persist its receipt.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        result_type = r[tuple[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]
        created = FlextInfraMiseArtifactsState.create_journaled_directory(
            layout,
            journal.directories,
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
            for entry in journal.directories
        )
        recorded = FlextInfraMiseArtifactsJournal.record_directories(
            journal,
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
            expected=journal_state,
        )
        if persisted.failure:
            failed = self._compensate_directory_persistence(
                layout,
                created.value,
                persisted.error or f"cannot persist directory {intent.path}",
                journal_write=True,
            )
            return result_type.from_failure(failed)
        return result_type.ok((recorded.value, persisted.value))

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
        authorized = self._authorize_journal(layout, journal)
        if authorized.failure:
            return r[m.Cli.AtomicFileState].from_failure(authorized)
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
        authorized = self._authorize_journal(layout, journal)
        if authorized.failure:
            return authorized
        if journal.file_participants:
            return self._recover_file_participants(layout, journal, journal_state)
        return self._recover_project_selectors(layout, journal, journal_state)

    def _recover_file_participants(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        journal_state: m.Cli.AtomicFileState,
    ) -> p.Result[bool]:
        """Recover a file-only journal under its participants' leases.

        Returns:
            The resulting ``p.Result[bool]``.

        """
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
        return self._settle_recovery(layout, recovered)

    def _recover_project_selectors(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        journal_state: m.Cli.AtomicFileState,
    ) -> p.Result[bool]:
        """Recover a Mise journal through its recorded project selectors.

        Returns:
            The resulting ``p.Result[bool]``.

        """
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
        return self._settle_recovery(layout, recovered)

    def _settle_recovery(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        recovered: p.Result[bool],
    ) -> p.Result[bool]:
        """Drop the owned receipt once a recovery fully succeeded.

        Returns:
            The recovery outcome.

        """
        if recovered.success:
            self._journal_receipts.pop(layout.journal_path, None)
        return recovered
