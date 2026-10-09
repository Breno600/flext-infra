"""Crash recovery for staging, prepared, recovering, or committed journals.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import stat
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from flext_infra import c, m, r, t
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)
from flext_infra.codegen._mise_artifacts_journal import (
    FlextInfraMiseArtifactsJournal as journal_io,
)
from flext_infra.codegen._mise_artifacts_process import (
    FlextInfraMiseArtifactsProcess as process,
)
from flext_infra.codegen._mise_artifacts_state import (
    FlextInfraMiseArtifactsState as state,
)
from flext_infra.codegen._mise_artifacts_verification import (
    FlextInfraMiseArtifactsVerification as verify,
)

if TYPE_CHECKING:
    from flext_infra import p

type _FileIdentity = tuple[
    int | None,
    int | None,
    str | None,
    int | None,
    int | None,
    int | None,
    int | None,
    int | None,
    int | None,
]

type _FileOwnershipIdentity = tuple[
    bool | None,
    int | None,
    int | None,
    str | None,
    int | None,
    int | None,
    int | None,
]


class FlextInfraMiseRecovery:
    """Restore only full states attributable to one durable journal."""

    def execute(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        journal_state: m.Cli.AtomicFileState,
    ) -> p.Result[bool]:
        """Recover an authenticated journal without consulting source topology.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        authority = self._verified_recovery_authority(layout, journal)
        if authority.failure:
            return authority
        terminal = self._terminal_state_cleanup(layout, journal, journal_state)
        if terminal.failure:
            return r[bool].from_failure(terminal)
        terminal_value, terminal_reached = terminal.value
        if terminal_reached:
            return r[bool].ok(terminal_value)
        classified = self._classify(layout, journal)
        advanced = self._advanced_recovery_journal(
            layout,
            journal,
            journal_state,
            classified,
        )
        if advanced.failure:
            return r[bool].from_failure(advanced)
        journal, journal_state, classified_value = advanced.value
        restored = self._restored_and_verified(layout, journal, classified_value)
        if restored.failure:
            return r[bool].from_failure(restored)
        return journal_io.cleanup(layout, journal, journal_state)

    @classmethod
    def _verified_recovery_authority(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[bool]:
        """Bind the journal topology and authenticate its transaction roots.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        topology = verify.journal_topology(layout, journal)
        if topology.failure:
            return topology
        return state.validate_transaction_roots(layout, journal)

    @classmethod
    def _terminal_state_cleanup(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        journal_state: m.Cli.AtomicFileState,
    ) -> p.Result[t.Pair[bool, bool]]:
        """Clean up directly when the journal is already staging or committed.

        Returns:
            The resulting ``p.Result[t.Pair[bool, bool]]`` where the payload
            is ``(terminal_status, terminal_reached)``; a journal that still
            needs a restore reports ``(False, False)``.

        """
        if journal.state in {"staging", "committed"}:
            cleaned = journal_io.cleanup(layout, journal, journal_state)
            if cleaned.failure:
                return r[t.Pair[bool, bool]].from_failure(cleaned)
            return r[t.Pair[bool, bool]].ok((cleaned.value, True))
        return r[t.Pair[bool, bool]].ok((False, False))

    @classmethod
    def _advanced_recovery_journal(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        journal_state: m.Cli.AtomicFileState,
        classified: p.Result[t.VariadicTuple[m.Infra.CodegenRecoveryAction]],
    ) -> p.Result[
        t.Triple[
            m.Infra.CodegenTransactionJournal,
            m.Cli.AtomicFileState,
            t.VariadicTuple[m.Infra.CodegenRecoveryAction],
        ]
    ]:
        """Advance a prepared journal into its recoverable registered state.

        Returns:
            The resulting ``p.Result[t.Triple[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState, t.VariadicTuple[
                m.Infra.CodegenRecoveryAction]]]``.

        """
        result_type = r[
            t.Triple[
                m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState,
                t.VariadicTuple[m.Infra.CodegenRecoveryAction],
            ]
        ]
        if classified.failure:
            return result_type.from_failure(classified)
        if journal.state != "prepared":
            return result_type.ok((journal, journal_state, classified.value))
        prepared = cls._prepare_restore_candidates(layout, classified.value)
        if prepared.failure:
            return result_type.from_failure(prepared)
        return cls._registered_prepared_journal(
            layout,
            journal,
            journal_state,
            prepared.value,
        )

    @classmethod
    def _registered_prepared_journal(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        journal_state: m.Cli.AtomicFileState,
        prepared: t.VariadicTuple[m.Infra.CodegenStagedFile | None],
    ) -> p.Result[
        t.Triple[
            m.Infra.CodegenTransactionJournal,
            m.Cli.AtomicFileState,
            t.VariadicTuple[m.Infra.CodegenRecoveryAction],
        ]
    ]:
        """Register, persist, and reclassify one prepared recovery journal.

        Returns:
            The resulting ``p.Result[t.Triple[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState, t.VariadicTuple[
                m.Infra.CodegenRecoveryAction]]]``.

        """
        result_type = r[
            t.Triple[
                m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState,
                t.VariadicTuple[m.Infra.CodegenRecoveryAction],
            ]
        ]
        recovering = journal_io.begin_recovery(journal, prepared)
        if recovering.failure:
            return result_type.from_failure(recovering)
        persisted = cls._registered_recovery_journal(
            layout,
            journal_state,
            recovering.value,
        )
        if persisted.failure:
            return result_type.from_failure(persisted)
        recorded_journal, recorded_state = persisted.value
        reclassified = cls._classify(layout, recorded_journal)
        if reclassified.failure:
            return result_type.from_failure(reclassified)
        return result_type.ok((recorded_journal, recorded_state, reclassified.value))

    @classmethod
    def _registered_recovery_journal(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal_state: m.Cli.AtomicFileState,
        recovering: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Register and durably persist the recovery journal revision.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]
        ]
        recorded = journal_io.record_transaction_manifests(layout, recovering)
        if recorded.failure:
            return result_type.from_failure(recorded)
        persisted = journal_io.write(layout, recorded.value, expected=journal_state)
        if persisted.failure:
            return result_type.from_failure(persisted)
        return result_type.ok((recorded.value, persisted.value))

    @staticmethod
    def _plain_resource_state(path: Path) -> m.Cli.AtomicFileState:
        """Read one package-owned resource without atomic-ownership semantics.

        uv hard-links installed package files to its cache, so their link
        count exceeds one by construction; the atomic-state reader rejects
        such leaves. Package resources are immutable data read as bytes, and
        their physical identities still come from lstat for the action log.

        Returns:
            The resulting ``m.Cli.AtomicFileState``.

        """
        content = path.read_bytes()
        leaf = path.lstat()
        parent = path.parent.lstat()
        return m.Cli.AtomicFileState(
            path=path,
            parent_device=parent.st_dev,
            parent_inode=parent.st_ino,
            content=content,
            mode=stat.S_IMODE(leaf.st_mode),
            device=leaf.st_dev,
            inode=leaf.st_ino,
            link_count=leaf.st_nlink,
            file_attributes=getattr(leaf, "st_file_attributes", None),
            reparse_tag=getattr(leaf, "st_reparse_tag", None),
        )

    @classmethod
    def _classify(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenRecoveryAction]]:
        """Classify every live target before preparing any recovery effect.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.CodegenRecoveryAction]]``.

        """
        result_type = r[tuple[m.Infra.CodegenRecoveryAction, ...]]
        actions: list[m.Infra.CodegenRecoveryAction] = []
        for entry in journal.entries:
            target = files.resolve_transaction(
                layout,
                entry.path,
                purpose="generated destination",
            )
            if target.failure:
                return result_type.from_failure(target)
            # Package-owned resources (uv hard-links installed templates into
            # site-packages) are never uniquely-owned workspace state: a stale
            # journal entry pointing inside the installed package classifies
            # as a noop instead of failing the whole recovery on the nlink
            # guard of the atomic-state reader.
            package_root = Path(__file__).resolve().parents[2]
            if target.value.is_relative_to(package_root):
                actions.append(
                    m.Infra.CodegenRecoveryAction(
                        entry=entry,
                        current=cls._plain_resource_state(target.value),
                        operation="noop",
                    ),
                )
                continue
            current = files.read_state(target.value, required=False)
            if current.failure:
                return result_type.from_failure(current)
            identity = cls._classify_identity(current.value)
            original = cls._classify_entry_identity(entry, "original")
            desired = cls._classify_entry_identity(entry, "desired")
            rollback = cls._classify_entry_identity(entry, "rollback")
            if (
                journal.state == "committed"
                or identity == original
                or (journal.state == "recovering" and identity == rollback)
            ):
                operation: Literal["noop", "delete", "restore"] = "noop"
            elif identity == desired:
                operation = "restore" if entry.original_exists else "delete"
            else:
                # Um estado nao reconhecido nunca bloqueia a recuperacao: a
                # geracao e a dona do arquivo e o reescreve. Travar aqui criava
                # impasse circular (gen nao roda para consertar o que ele gera).
                operation = "noop"
            if operation == "restore" and cls._staging_tree_is_absent(layout, entry):
                # The staged rollback tree vanished whole (a crashed run
                # removed it before the journal could be cleaned), so required
                # reads under it can never succeed. The same anti-impasse law
                # as an unrecognized state applies: the generation owns the
                # file and rewrites it on the next apply pass.
                operation = "noop"
            actions.append(
                m.Infra.CodegenRecoveryAction(
                    entry=entry,
                    current=current.value,
                    operation=operation,
                ),
            )
        return result_type.ok(tuple(actions))

    @staticmethod
    def _staging_tree_is_absent(
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        entry: m.Infra.CodegenJournalEntry,
    ) -> bool:
        """Whether the entry's staged rollback tree is gone entirely.

        Returns:
            The resulting ``bool``.

        """
        if entry.original_backup is None:
            return False
        backup = files.resolve_transaction(
            layout,
            entry.original_backup,
            purpose="generation recovery backup",
        )
        return backup.failure or not backup.value.parent.is_dir()

    @classmethod
    def _prepare_restore_candidates(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        actions: t.VariadicTuple[m.Infra.CodegenRecoveryAction],
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenStagedFile | None]]:
        result_type = r[tuple[m.Infra.CodegenStagedFile | None, ...]]
        candidates: list[m.Infra.CodegenStagedFile | None] = []
        for action in actions:
            if action.operation != "restore":
                candidates.append(None)
                continue
            if not action.entry.original_exists or action.entry.original_backup is None:
                candidates.append(None)
                continue
            backup_path = files.resolve_transaction(
                layout,
                action.entry.original_backup,
                purpose="generation recovery backup",
            )
            if backup_path.failure:
                return result_type.from_failure(backup_path)
            if not backup_path.value.exists():
                candidates.append(None)
                continue
            prepared = cls._prepare_restore_candidate(layout, action)
            if prepared.failure:
                return result_type.from_failure(prepared)
            candidates.append(prepared.value)
        return result_type.ok(tuple(candidates))

    @classmethod
    def _prepare_restore_candidate(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        action: m.Infra.CodegenRecoveryAction,
    ) -> p.Result[m.Infra.CodegenStagedFile]:
        entry = action.entry
        if (
            entry.original_backup is None
            or entry.original_sha256 is None
            or entry.original_mode is None
        ):
            return r[m.Infra.CodegenStagedFile].fail(
                f"generation recovery tuple is incomplete: {entry.path}",
            )
        backup = cls._verified_backup(layout, entry)
        if backup.failure:
            return r[m.Infra.CodegenStagedFile].from_failure(backup)
        candidate = cls._restore_candidate_state(layout, entry, backup.value)
        if candidate.failure:
            return r[m.Infra.CodegenStagedFile].from_failure(candidate)
        project = next(
            item.root
            for item in files.transaction_participants(layout)
            if item.selector == entry.project
        )
        return r[m.Infra.CodegenStagedFile].ok(
            m.Infra.CodegenStagedFile(
                phase=c.Infra.CodegenStagedFilePhase.RECOVERY,
                project=project,
                before=action.current,
                replacement=candidate.value,
            ),
        )

    @staticmethod
    def _verified_backup(
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        entry: m.Infra.CodegenJournalEntry,
    ) -> p.Result[m.Cli.AtomicFileState]:
        """Read and authenticate one recovery backup against its receipt.

        Returns:
            The resulting ``p.Result[m.Cli.AtomicFileState]``.

        """
        result_type = r[m.Cli.AtomicFileState]
        if entry.original_backup is None:
            return result_type.fail(
                f"generation recovery entry has no backup: {entry.path}",
            )
        backup_path = files.resolve_transaction(
            layout,
            entry.original_backup,
            purpose="generation recovery backup",
        )
        if backup_path.failure:
            return result_type.from_failure(backup_path)
        backup = files.read_state(backup_path.value, required=True)
        if backup.failure or backup.value.content is None:
            return result_type.fail(
                backup.error or f"generation recovery backup is absent: {entry.path}",
            )
        if (
            backup.value.mode != c.Infra.JOURNAL_MODE
            or files.digest(backup.value.content) != entry.original_sha256
        ):
            return result_type.fail(
                f"generation recovery backup differs: {entry.path}",
            )
        return result_type.ok(backup.value)

    @classmethod
    def _restore_candidate_state(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        entry: m.Infra.CodegenJournalEntry,
        backup: m.Cli.AtomicFileState,
    ) -> p.Result[m.Cli.AtomicFileState]:
        """Materialize the restore candidate beside its backup and prove it.

        Returns:
            The resulting ``p.Result[m.Cli.AtomicFileState]``.

        """
        result_type = r[m.Cli.AtomicFileState]
        if entry.original_backup is None:
            return result_type.fail(
                f"generation recovery entry has no backup: {entry.path}",
            )
        backup_path = files.resolve_transaction(
            layout,
            entry.original_backup,
            purpose="generation recovery backup",
        )
        if backup_path.failure:
            return result_type.from_failure(backup_path)
        candidate_path = backup_path.value.with_suffix(".restore")
        candidate = files.read_state(candidate_path, required=False)
        if candidate.failure:
            return result_type.from_failure(candidate)
        if candidate.value.content is None:
            written = cls._written_restore_candidate(candidate_path, entry, backup)
            if written.failure:
                return result_type.from_failure(written)
            candidate = written
        if (
            candidate.value.content != backup.content
            or candidate.value.mode != entry.original_mode
        ):
            return result_type.fail(
                f"generation restore candidate differs: {entry.path}",
            )
        return result_type.ok(candidate.value)

    @staticmethod
    def _written_restore_candidate(
        candidate_path: Path,
        entry: m.Infra.CodegenJournalEntry,
        backup: m.Cli.AtomicFileState,
    ) -> p.Result[m.Cli.AtomicFileState]:
        """Write and re-read one fresh restore candidate beside its backup.

        Returns:
            The resulting ``p.Result[m.Cli.AtomicFileState]``.

        """
        result_type = r[m.Cli.AtomicFileState]
        if backup.content is None or entry.original_mode is None:
            return result_type.fail(
                f"generation recovery backup identity is incomplete: {entry.path}",
            )
        created = process.write_new(
            candidate_path,
            backup.content,
            entry.original_mode,
        )
        if created.failure:
            return result_type.from_failure(created)
        candidate = files.read_state(candidate_path, required=True)
        if candidate.failure:
            return result_type.from_failure(candidate)
        return result_type.ok(candidate.value)

    def _load_restore_candidates(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        actions: t.VariadicTuple[m.Infra.CodegenRecoveryAction],
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenStagedFile | None]]:
        result_type = r[tuple[m.Infra.CodegenStagedFile | None, ...]]
        candidates: list[m.Infra.CodegenStagedFile | None] = []
        for action in actions:
            entry = action.entry
            if action.operation != "restore":
                candidates.append(None)
                continue
            if entry.original_backup is None:
                return result_type.fail(
                    f"generation rollback backup is absent: {entry.path}",
                )
            backup = files.resolve_transaction(
                layout,
                entry.original_backup,
                purpose="generation recovery backup",
            )
            if backup.failure:
                return result_type.from_failure(backup)
            candidate = files.read_state(
                backup.value.with_suffix(".restore"),
                required=True,
            )
            if candidate.failure:
                return result_type.from_failure(candidate)
            if (
                self._identity(candidate.value)[2:]
                != self._entry_identity(entry, "rollback")[2:]
            ):
                return result_type.fail(
                    f"generation rollback candidate changed: {entry.path}",
                )
            project = next(
                item.root
                for item in files.transaction_participants(layout)
                if item.selector == entry.project
            )
            candidates.append(
                m.Infra.CodegenStagedFile(
                    phase=c.Infra.CodegenStagedFilePhase.RECOVERY,
                    project=project,
                    before=action.current,
                    replacement=candidate.value,
                ),
            )
        return result_type.ok(tuple(candidates))

    def _restored_and_verified(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        actions: t.VariadicTuple[m.Infra.CodegenRecoveryAction],
    ) -> p.Result[bool]:
        """Restore every journaled destination, then verify the rollback set.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        candidates = self._prepare_restore_candidates(layout, actions)
        if candidates.failure:
            return r[bool].from_failure(candidates)
        restored = FlextInfraMiseRecovery._restore(actions, candidates.value)
        if restored.failure:
            return restored
        return self._verify_rollback(layout, journal, actions)

    @staticmethod
    def _restore(
        actions: t.VariadicTuple[m.Infra.CodegenRecoveryAction],
        candidates: t.VariadicTuple[m.Infra.CodegenStagedFile | None],
    ) -> p.Result[bool]:
        paired = tuple(zip(actions, candidates, strict=True))
        for action, candidate in reversed(paired):
            if action.operation == "restore":
                if candidate is None:
                    continue
                restored = files.write_publication(candidate)
                if restored.failure:
                    return r[bool].from_failure(restored)
            elif action.operation == "delete":
                removed = files.delete_state(action.current)
                if removed.failure:
                    return r[bool].from_failure(removed)
        return r[bool].ok(value=True)

    def _verify_rollback(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        actions: t.VariadicTuple[m.Infra.CodegenRecoveryAction],
    ) -> p.Result[bool]:
        by_path = {action.entry.path: action for action in actions}
        for entry in journal.entries:
            target = files.resolve_transaction(
                layout,
                entry.path,
                purpose="generated destination",
            )
            if target.failure:
                return r[bool].from_failure(target)
            current = files.read_state(target.value, required=False)
            if current.failure:
                return r[bool].from_failure(current)
            identity = self._identity(current.value)
            expected = {
                self._entry_identity(entry, "original"),
                self._entry_identity(entry, "rollback"),
            }
            action = by_path.get(entry.path)
            if action is None:
                return r[bool].fail(
                    f"generation recovery action is absent: {entry.path}",
                )
            if action.operation == "noop":
                expected.add(self._identity(action.current))
            if identity not in expected:
                return r[bool].fail(f"generated file was not restored: {entry.path}")
        return r[bool].ok(value=True)

    @staticmethod
    def _classify_identity(state: m.Cli.AtomicFileState) -> _FileOwnershipIdentity:
        """Classify by durable content and parent identity, never per-copy inode.

        Returns:
            The resulting ``_FileOwnershipIdentity``.

        """
        return (
            state.content is not None,
            state.parent_device,
            state.parent_inode,
            None if state.content is None else files.digest(state.content),
            state.mode,
            state.file_attributes,
            state.reparse_tag,
        )

    @staticmethod
    def _classify_entry_identity(
        entry: m.Infra.CodegenJournalEntry,
        prefix: Literal["original", "desired", "rollback"],
    ) -> _FileOwnershipIdentity:
        stored = {
            "original": (
                entry.original_exists,
                entry.original_parent_device,
                entry.original_parent_inode,
                entry.original_sha256,
                entry.original_mode,
                entry.original_file_attributes,
                entry.original_reparse_tag,
            ),
            "desired": (
                entry.desired_exists,
                entry.desired_parent_device,
                entry.desired_parent_inode,
                entry.desired_sha256,
                entry.desired_mode,
                entry.desired_file_attributes,
                entry.desired_reparse_tag,
            ),
            "rollback": (
                entry.rollback_exists,
                entry.rollback_parent_device,
                entry.rollback_parent_inode,
                entry.rollback_sha256,
                entry.rollback_mode,
                entry.rollback_file_attributes,
                entry.rollback_reparse_tag,
            ),
        }
        return stored[prefix]

    @staticmethod
    def _identity(state: m.Cli.AtomicFileState) -> _FileIdentity:
        return (
            state.parent_device,
            state.parent_inode,
            None if state.content is None else files.digest(state.content),
            state.mode,
            state.device,
            state.inode,
            state.link_count,
            state.file_attributes,
            state.reparse_tag,
        )

    @staticmethod
    def _entry_identity(
        entry: m.Infra.CodegenJournalEntry,
        prefix: Literal["original", "desired", "rollback"],
    ) -> _FileIdentity:
        """Build one journal identity without dynamically addressing model fields.

        Returns:
            The resulting ``_FileIdentity``.

        """
        stored: t.MappingKV[str, t.Pair[bool | None, _FileIdentity]] = {
            "original": (
                entry.original_exists,
                (
                    entry.original_parent_device,
                    entry.original_parent_inode,
                    entry.original_sha256,
                    entry.original_mode,
                    entry.original_device,
                    entry.original_inode,
                    entry.original_link_count,
                    entry.original_file_attributes,
                    entry.original_reparse_tag,
                ),
            ),
            "desired": (
                entry.desired_exists,
                (
                    entry.desired_parent_device,
                    entry.desired_parent_inode,
                    entry.desired_sha256,
                    entry.desired_mode,
                    entry.desired_device,
                    entry.desired_inode,
                    entry.desired_link_count,
                    entry.desired_file_attributes,
                    entry.desired_reparse_tag,
                ),
            ),
            "rollback": (
                entry.rollback_exists,
                (
                    entry.rollback_parent_device,
                    entry.rollback_parent_inode,
                    entry.rollback_sha256,
                    entry.rollback_mode,
                    entry.rollback_device,
                    entry.rollback_inode,
                    entry.rollback_link_count,
                    entry.rollback_file_attributes,
                    entry.rollback_reparse_tag,
                ),
            ),
        }
        exists, identity = stored[prefix]
        if not exists:
            # An absent file keeps only its parent directory identity.
            return (identity[0], identity[1], None, None, None, None, None, None, None)
        return identity


__all__: list[str] = ["FlextInfraMiseRecovery"]
