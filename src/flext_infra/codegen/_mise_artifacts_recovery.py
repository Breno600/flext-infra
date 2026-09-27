"""Crash recovery for staging, prepared, recovering, or committed journals."""

from __future__ import annotations

import stat
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from flext_core import r
from flext_infra import c, m

from ._mise_artifacts_files import FlextInfraMiseArtifactsFiles as files
from ._mise_artifacts_journal import FlextInfraMiseArtifactsJournal as journal_io
from ._mise_artifacts_process import FlextInfraMiseArtifactsProcess as process
from ._mise_artifacts_state import FlextInfraMiseArtifactsState as state
from ._mise_artifacts_verification import FlextInfraMiseArtifactsVerification as verify

if TYPE_CHECKING:
    from flext_infra import p, t

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
    bool | None, int | None, int | None, str | None, int | None, int | None, int | None
]


class FlextInfraMiseRecovery:
    """Restore only full states attributable to one durable journal."""

    def execute(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        journal_state: m.Cli.AtomicFileState,
    ) -> p.Result[bool]:
        """Recover an authenticated journal without consulting source topology."""
        topology = verify.journal_topology(layout, journal)
        if topology.failure:
            return topology
        roots = state.validate_transaction_roots(layout, journal)
        if roots.failure:
            return roots
        if journal.state == "staging":
            return journal_io.cleanup(layout, journal, journal_state)
        classified = self._classify(layout, journal)
        if classified.failure:
            return r[bool].from_failure(classified)
        if journal.state == "committed":
            return journal_io.cleanup(layout, journal, journal_state)
        if journal.state == "prepared":
            prepared = self._prepare_restore_candidates(layout, classified.value)
            if prepared.failure:
                return r[bool].from_failure(prepared)
            recovering = journal_io.begin_recovery(journal, prepared.value)
            if recovering.failure:
                return r[bool].from_failure(recovering)
            manifests = verify.register_transaction_manifests(layout, recovering.value)
            if manifests.failure:
                return r[bool].from_failure(manifests)
            recorded = journal_io.record_directories(recovering.value, manifests.value)
            if recorded.failure:
                return r[bool].from_failure(recorded)
            persisted = journal_io.write(layout, recorded.value, expected=journal_state)
            if persisted.failure:
                return r[bool].from_failure(persisted)
            journal = recorded.value
            journal_state = persisted.value
            classified = self._classify(layout, journal)
            if classified.failure:
                return r[bool].from_failure(classified)
        candidates = self._load_restore_candidates(layout, classified.value)
        if candidates.failure:
            return r[bool].from_failure(candidates)
        restored = self._restore(classified.value, candidates.value)
        if restored.failure:
            return restored
        exact = self._verify_rollback(layout, journal, classified.value)
        if exact.failure:
            return exact
        return journal_io.cleanup(layout, journal, journal_state)

    @staticmethod
    def _plain_resource_state(path: Path) -> m.Cli.AtomicFileState:
        """Read one package-owned resource without atomic-ownership semantics.

        uv hard-links installed package files to its cache, so their link
        count exceeds one by construction; the atomic-state reader rejects
        such leaves. Package resources are immutable data read as bytes, and
        their physical identities still come from lstat for the action log.
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

    def _classify(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenRecoveryAction]]:
        """Classify every live target before preparing any recovery effect."""
        result_type = r[tuple[m.Infra.CodegenRecoveryAction, ...]]
        actions: list[m.Infra.CodegenRecoveryAction] = []
        for entry in journal.entries:
            target = files.resolve_transaction(
                layout, entry.path, purpose="generated destination"
            )
            if target.failure:
                return result_type.from_failure(target)
            # Package-owned resources (uv hard-links installed templates into
            # site-packages) are never uniquely-owned workspace state: a stale
            # journal entry pointing inside the installed package classifies
            # as a noop instead of failing the whole recovery on the nlink
            # guard of the atomic-state reader (ai-hub runner, flext-6ep5y).
            package_root = Path(__file__).resolve().parents[2]
            if target.value.is_relative_to(package_root):
                actions.append(
                    m.Infra.CodegenRecoveryAction(
                        entry=entry,
                        current=self._plain_resource_state(target.value),
                        operation="noop",
                    )
                )
                continue
            current = files.read_state(target.value, required=False)
            if current.failure:
                return result_type.from_failure(current)
            identity = self._classify_identity(current.value)
            original = self._classify_entry_identity(entry, "original")
            desired = self._classify_entry_identity(entry, "desired")
            rollback = self._classify_entry_identity(entry, "rollback")
            if (
                journal.state == "committed"
                or identity == original
                or (journal.state == "recovering" and identity == rollback)
            ):
                operation = "noop"
            elif identity == desired:
                operation = "restore" if entry.original_exists else "delete"
            else:
                # Um estado nao reconhecido nunca bloqueia a recuperacao: a
                # geracao e a dona do arquivo e o reescreve. Travar aqui criava
                # impasse circular (gen nao roda para consertar o que ele gera).
                operation = "noop"
            if operation == "restore" and self._staging_tree_is_absent(layout, entry):
                # The staged rollback tree vanished whole (a crashed run
                # removed it before the journal could be cleaned), so required
                # reads under it can never succeed. The same anti-impasse law
                # as an unrecognized state applies: the generation owns the
                # file and rewrites it on the next apply pass.
                operation = "noop"
            actions.append(
                m.Infra.CodegenRecoveryAction(
                    entry=entry, current=current.value, operation=operation
                )
            )
        return result_type.ok(tuple(actions))

    @staticmethod
    def _staging_tree_is_absent(
        layout: m.Infra.MiseToolchainWorkspaceLayout, entry: m.Infra.CodegenJournalEntry
    ) -> bool:
        """Whether the entry's staged rollback tree is gone entirely."""
        if entry.original_backup is None:
            return False
        backup = files.resolve_transaction(
            layout, entry.original_backup, purpose="generation recovery backup"
        )
        return backup.failure or not backup.value.parent.is_dir()

    def _prepare_restore_candidates(
        self,
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
            prepared = self._prepare_restore_candidate(layout, action)
            if prepared.failure:
                return result_type.from_failure(prepared)
            candidates.append(prepared.value)
        return result_type.ok(tuple(candidates))

    @staticmethod
    def _prepare_restore_candidate(
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
                f"generation recovery tuple is incomplete: {entry.path}"
            )
        backup_path = files.resolve_transaction(
            layout, entry.original_backup, purpose="generation recovery backup"
        )
        if backup_path.failure:
            return r[m.Infra.CodegenStagedFile].from_failure(backup_path)
        backup = files.read_state(backup_path.value, required=True)
        if backup.failure or backup.value.content is None:
            return r[m.Infra.CodegenStagedFile].fail(
                backup.error or f"generation recovery backup is absent: {entry.path}"
            )
        if (
            backup.value.mode != c.Infra.JOURNAL_MODE
            or files.digest(backup.value.content) != entry.original_sha256
        ):
            return r[m.Infra.CodegenStagedFile].fail(
                f"generation recovery backup differs: {entry.path}"
            )
        candidate_path = backup_path.value.with_suffix(".restore")
        candidate = files.read_state(candidate_path, required=False)
        if candidate.failure:
            return r[m.Infra.CodegenStagedFile].from_failure(candidate)
        if candidate.value.content is None:
            created = process.write_new(
                candidate_path, backup.value.content, entry.original_mode
            )
            if created.failure:
                return r[m.Infra.CodegenStagedFile].from_failure(created)
            candidate = files.read_state(candidate_path, required=True)
            if candidate.failure:
                return r[m.Infra.CodegenStagedFile].from_failure(candidate)
        if (
            candidate.value.content != backup.value.content
            or candidate.value.mode != entry.original_mode
        ):
            return r[m.Infra.CodegenStagedFile].fail(
                f"generation restore candidate differs: {entry.path}"
            )
        project = next(
            item.root
            for item in files.transaction_participants(layout)
            if item.selector == entry.project
        )
        return r[m.Infra.CodegenStagedFile].ok(
            m.Infra.CodegenStagedFile(
                phase="recovery",
                project=project,
                before=action.current,
                replacement=candidate.value,
            )
        )

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
                    f"generation rollback backup is absent: {entry.path}"
                )
            backup = files.resolve_transaction(
                layout, entry.original_backup, purpose="generation recovery backup"
            )
            if backup.failure:
                return result_type.from_failure(backup)
            candidate = files.read_state(
                backup.value.with_suffix(".restore"), required=True
            )
            if candidate.failure:
                return result_type.from_failure(candidate)
            if (
                self._identity(candidate.value)[2:]
                != self._entry_identity(entry, "rollback")[2:]
            ):
                return result_type.fail(
                    f"generation rollback candidate changed: {entry.path}"
                )
            project = next(
                item.root
                for item in files.transaction_participants(layout)
                if item.selector == entry.project
            )
            candidates.append(
                m.Infra.CodegenStagedFile(
                    phase="recovery",
                    project=project,
                    before=action.current,
                    replacement=candidate.value,
                )
            )
        return result_type.ok(tuple(candidates))

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
        return r[bool].ok(True)

    def _verify_rollback(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        actions: t.VariadicTuple[m.Infra.CodegenRecoveryAction],
    ) -> p.Result[bool]:
        by_path = {action.entry.path: action for action in actions}
        for entry in journal.entries:
            target = files.resolve_transaction(
                layout, entry.path, purpose="generated destination"
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
                    f"generation recovery action is absent: {entry.path}"
                )
            if action.operation == "noop":
                expected.add(self._identity(action.current))
            if identity not in expected:
                return r[bool].fail(f"generated file was not restored: {entry.path}")
        return r[bool].ok(True)

    @staticmethod
    def _classify_identity(state: m.Cli.AtomicFileState) -> _FileOwnershipIdentity:
        """Classify by durable content and parent identity, never per-copy inode."""
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
        if prefix == "original":
            return FlextInfraMiseRecovery._stored_identity(
                exists=entry.original_exists,
                parent_device=entry.original_parent_device,
                parent_inode=entry.original_parent_inode,
                sha256=entry.original_sha256,
                mode=entry.original_mode,
                device=entry.original_device,
                inode=entry.original_inode,
                link_count=entry.original_link_count,
                file_attributes=entry.original_file_attributes,
                reparse_tag=entry.original_reparse_tag,
            )
        if prefix == "desired":
            return FlextInfraMiseRecovery._stored_identity(
                exists=entry.desired_exists,
                parent_device=entry.desired_parent_device,
                parent_inode=entry.desired_parent_inode,
                sha256=entry.desired_sha256,
                mode=entry.desired_mode,
                device=entry.desired_device,
                inode=entry.desired_inode,
                link_count=entry.desired_link_count,
                file_attributes=entry.desired_file_attributes,
                reparse_tag=entry.desired_reparse_tag,
            )
        return FlextInfraMiseRecovery._stored_identity(
            exists=entry.rollback_exists,
            parent_device=entry.rollback_parent_device,
            parent_inode=entry.rollback_parent_inode,
            sha256=entry.rollback_sha256,
            mode=entry.rollback_mode,
            device=entry.rollback_device,
            inode=entry.rollback_inode,
            link_count=entry.rollback_link_count,
            file_attributes=entry.rollback_file_attributes,
            reparse_tag=entry.rollback_reparse_tag,
        )

    @staticmethod
    def _stored_identity(
        *,
        exists: bool | None,
        parent_device: int | None,
        parent_inode: int | None,
        sha256: str | None,
        mode: int | None,
        device: int | None,
        inode: int | None,
        link_count: int | None,
        file_attributes: int | None,
        reparse_tag: int | None,
    ) -> _FileIdentity:
        """Build one journal identity without dynamically addressing model fields."""
        parent = (parent_device, parent_inode)
        if not exists:
            return (*parent, None, None, None, None, None, None, None)
        return (
            *parent,
            sha256,
            mode,
            device,
            inode,
            link_count,
            file_attributes,
            reparse_tag,
        )


__all__: list[str] = ["FlextInfraMiseRecovery"]
