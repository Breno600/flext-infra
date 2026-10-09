"""Durable journal for one extensible workspace generation transaction.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, m, p, r, t, u
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)
from flext_infra.codegen._mise_artifacts_journal_relocation import (
    FlextInfraMiseArtifactsJournalRelocation,
)
from flext_infra.codegen._mise_artifacts_process import (
    FlextInfraMiseArtifactsProcess as process,
)
from flext_infra.codegen._mise_artifacts_state import (
    FlextInfraMiseArtifactsState as journal_state,
)
from flext_infra.codegen._mise_artifacts_verification import (
    FlextInfraMiseArtifactsVerification,
)


class FlextInfraMiseArtifactsJournal(FlextInfraMiseArtifactsJournalRelocation):
    """Durable transaction journal for Mise artifact generation."""

    @classmethod
    def begin(
        cls,
        plan: m.Infra.MiseToolchainWorkspacePlan | m.Infra.CodegenFileSessionPlan,
        *,
        transaction_id: str,
        sources: t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]] = (),
        directories: t.VariadicTuple[m.Infra.CodegenJournalDirectory] = (),
    ) -> p.Result[m.Infra.CodegenTransactionJournal]:
        """Build staging authority before any disposable transaction root exists.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionJournal]``.

        """
        physical_scope = files.physical_directory_identity(plan.layout.scope_root)
        if physical_scope.failure:
            return r[m.Infra.CodegenTransactionJournal].from_failure(physical_scope)
        projects: list[m.Infra.CodegenJournalProject] = []
        for project in plan.layout.projects:
            physical_project = files.physical_directory_identity(project.root)
            if physical_project.failure:
                return r[m.Infra.CodegenTransactionJournal].from_failure(
                    physical_project,
                )
            projects.append(
                m.Infra.CodegenJournalProject(
                    selector=project.selector,
                    device=physical_project.value[0],
                    inode=physical_project.value[1],
                ),
            )
        encoded_sources = cls._merge_sources((), sources)
        if encoded_sources.failure:
            return r[m.Infra.CodegenTransactionJournal].from_failure(encoded_sources)
        validated: p.Result[m.Infra.CodegenTransactionJournal] = u.validate_value(
            m.Infra.CodegenTransactionJournal,
            {
                "version": 8,
                "transaction_id": transaction_id,
                "scope_device": physical_scope.value[0],
                "scope_inode": physical_scope.value[1],
                "state": "staging",
                "projects": tuple(projects),
                "file_participants": plan.layout.file_participants,
                "sources": encoded_sources.value,
                "directories": directories,
                "entries": (),
            },
        )
        if validated.failure:
            return r[m.Infra.CodegenTransactionJournal].fail_op(
                "validate staging codegen journal",
                validated.error,
            )
        return r[m.Infra.CodegenTransactionJournal].ok(validated.value)

    @classmethod
    def append_prepared(
        cls,
        plan: m.Infra.MiseToolchainWorkspacePlan | m.Infra.CodegenFileSessionPlan,
        journal: m.Infra.CodegenTransactionJournal,
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
        *,
        sources: t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]] = (),
    ) -> p.Result[m.Infra.CodegenTransactionJournal]:
        """Back up one complete phase and return its extended prepared authority.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionJournal]``.

        """
        if journal.state not in {"staging", "prepared"}:
            return r[m.Infra.CodegenTransactionJournal].fail(
                "only staging or prepared codegen journal accepts a phase",
            )
        topology = cls._validate_physical_topology(plan, journal)
        if topology.failure:
            return r[m.Infra.CodegenTransactionJournal].from_failure(topology)
        prepared_entries = cls._prepared_phase_entries(plan, journal, publications)
        if prepared_entries.failure:
            return r[m.Infra.CodegenTransactionJournal].from_failure(prepared_entries)
        entries = list(journal.entries)
        entries.extend(prepared_entries.value)
        encoded_sources = cls._merge_sources(journal.sources, sources)
        if encoded_sources.failure:
            return r[m.Infra.CodegenTransactionJournal].from_failure(encoded_sources)
        validated: p.Result[m.Infra.CodegenTransactionJournal] = u.validate_value(
            m.Infra.CodegenTransactionJournal,
            {
                "version": 8,
                "transaction_id": journal.transaction_id,
                "scope_device": journal.scope_device,
                "scope_inode": journal.scope_inode,
                "state": "prepared",
                "projects": journal.projects,
                "file_participants": journal.file_participants,
                "sources": encoded_sources.value,
                "directories": journal.directories,
                "entries": tuple(entries),
                "staging_intents": journal.staging_intents,
            },
        )
        if validated.failure:
            return r[m.Infra.CodegenTransactionJournal].fail_op(
                "validate prepared codegen journal",
                validated.error,
            )
        return r[m.Infra.CodegenTransactionJournal].ok(validated.value)

    @classmethod
    def _prepared_phase_entries(
        cls,
        plan: m.Infra.MiseToolchainWorkspacePlan | m.Infra.CodegenFileSessionPlan,
        journal: m.Infra.CodegenTransactionJournal,
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenJournalEntry]]:
        """Build one journal entry per staged publication, rejecting collisions.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.CodegenJournalEntry]]
            ``.

        """
        result_type = r[t.VariadicTuple[m.Infra.CodegenJournalEntry]]
        existing_paths = {entry.path for entry in journal.entries}
        entries: list[m.Infra.CodegenJournalEntry] = []
        recovery_roots: set[Path] = set()
        for offset, publication in enumerate(publications, start=len(journal.entries)):
            target = files.transaction_relative(plan.layout, publication.before.path)
            if target.failure:
                return result_type.from_failure(target)
            if target.value in existing_paths:
                return result_type.fail(
                    f"multiple generation phases own one destination: {target.value}",
                )
            entry = cls._journal_entry(
                plan,
                publication,
                index=offset,
                recovery_roots=recovery_roots,
                staging_intents=journal.staging_intents,
            )
            if entry.failure:
                return result_type.from_failure(entry)
            entries.append(entry.value)
            existing_paths.add(entry.value.path)
        return result_type.ok(tuple(entries))

    @classmethod
    def append_directories(
        cls,
        journal: m.Infra.CodegenTransactionJournal,
        directories: t.VariadicTuple[m.Infra.CodegenJournalDirectory],
    ) -> p.Result[m.Infra.CodegenTransactionJournal]:
        """Extend durable directory authority before materializing any new path.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionJournal]``.

        """
        if journal.state not in {"staging", "prepared"}:
            return r[m.Infra.CodegenTransactionJournal].fail(
                "only staging or prepared codegen journal accepts directories",
            )
        existing = {directory.path for directory in journal.directories}
        duplicate = next(
            (directory.path for directory in directories if directory.path in existing),
            None,
        )
        if duplicate is not None:
            return r[m.Infra.CodegenTransactionJournal].fail(
                f"generation directory already has an owner: {duplicate}",
            )
        validated: p.Result[m.Infra.CodegenTransactionJournal] = u.validate_value(
            m.Infra.CodegenTransactionJournal,
            {
                "version": 8,
                "transaction_id": journal.transaction_id,
                "scope_device": journal.scope_device,
                "scope_inode": journal.scope_inode,
                "state": journal.state,
                "projects": journal.projects,
                "file_participants": journal.file_participants,
                "sources": journal.sources,
                "directories": (*journal.directories, *directories),
                "entries": journal.entries,
                "staging_intents": journal.staging_intents,
            },
        )
        if validated.failure:
            return r[m.Infra.CodegenTransactionJournal].fail_op(
                "validate extended codegen directory journal",
                validated.error,
            )
        return r[m.Infra.CodegenTransactionJournal].ok(validated.value)

    @classmethod
    def record_transaction_manifests(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        *,
        created: t.VariadicTuple[
            m.Cli.AtomicFileState | m.Cli.AtomicDirectoryState
        ] = (),
    ) -> p.Result[m.Infra.CodegenTransactionJournal]:
        """Validate physical manifests and retain them in the transaction journal.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionJournal]``.

        """
        finalized: list[m.Infra.CodegenStagingIntent] = []
        for intent in journal.staging_intents:
            observed = files.read_state(intent.before.path, required=False)
            if observed.failure:
                return r[m.Infra.CodegenTransactionJournal].from_failure(observed)
            current = observed.value
            if current.content is None:
                finalized.append(intent)
                continue
            if (
                current.parent_device != intent.before.parent_device
                or current.parent_inode != intent.before.parent_inode
                or current.mode != intent.mode
                or files.digest(current.content) != intent.sha256
            ):
                return r[m.Infra.CodegenTransactionJournal].fail(
                    f"staging bytes differ from durable intention: {current.path}",
                )
            inventory = u.Cli.atomic_inventory_physical_tree(current.path.parent)
            if inventory.failure:
                return r[m.Infra.CodegenTransactionJournal].from_failure(inventory)
            receipt = next(
                (
                    entry
                    for entry in inventory.value.entries
                    if entry.path == current.path
                ),
                None,
            )
            if receipt is None or (
                intent.created is not None and receipt != intent.created
            ):
                return r[m.Infra.CodegenTransactionJournal].fail(
                    f"staging physical identity changed: {current.path}",
                )
            finalized.append(
                m.Infra.CodegenStagingIntent.model_validate({
                    **intent.model_dump(),
                    "created": receipt,
                }),
            )
        journal = m.Infra.CodegenTransactionJournal.model_validate({
            **journal.model_dump(),
            "staging_intents": tuple(finalized),
        })
        registered = FlextInfraMiseArtifactsVerification.register_transaction_manifests(
            layout,
            journal,
            created=created,
        )
        if registered.failure:
            return r[m.Infra.CodegenTransactionJournal].from_failure(registered)
        return cls.record_directories(journal, registered.value)

    @classmethod
    def record_directories(
        cls,
        journal: m.Infra.CodegenTransactionJournal,
        directories: t.VariadicTuple[m.Infra.CodegenJournalDirectory],
    ) -> p.Result[m.Infra.CodegenTransactionJournal]:
        """Advance physical directory evidence without changing its durable intent.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionJournal]``.

        """
        result_type = r[m.Infra.CodegenTransactionJournal]
        if tuple(directory.path for directory in directories) != tuple(
            directory.path for directory in journal.directories
        ):
            return result_type.fail("recorded directory topology differs from journal")
        for previous, current in zip(journal.directories, directories, strict=True):
            compared = cls._validated_recorded_directory(previous, current)
            if compared.failure:
                return result_type.from_failure(compared)
        validated: p.Result[m.Infra.CodegenTransactionJournal] = u.validate_value(
            m.Infra.CodegenTransactionJournal,
            {
                "version": 8,
                "transaction_id": journal.transaction_id,
                "scope_device": journal.scope_device,
                "scope_inode": journal.scope_inode,
                "state": journal.state,
                "projects": journal.projects,
                "file_participants": journal.file_participants,
                "sources": journal.sources,
                "directories": directories,
                "entries": journal.entries,
                "staging_intents": journal.staging_intents,
            },
        )
        if validated.failure:
            return result_type.fail_op(
                "validate recorded directory evidence",
                validated.error,
            )
        return result_type.ok(validated.value)

    @staticmethod
    def _validated_recorded_directory(
        previous: m.Infra.CodegenJournalDirectory,
        current: m.Infra.CodegenJournalDirectory,
    ) -> p.Result[bool]:
        """Prove one recorded directory kept its durable intent and evidence.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        result_type = r[bool]
        stable_previous = previous.model_dump(
            exclude={"before", "created", "manifest"},
        )
        stable_current = current.model_dump(
            exclude={"before", "created", "manifest"},
        )
        if stable_current != stable_previous:
            return result_type.fail(
                f"recorded directory intent changed: {previous.path}",
            )
        if previous.before is not None and current.before != previous.before:
            return result_type.fail(
                f"recorded directory parent binding changed: {previous.path}",
            )
        if previous.before is None and current.before is None and current.created:
            return result_type.fail(
                f"created directory lacks parent binding: {previous.path}",
            )
        if previous.created is not None and current.created != previous.created:
            return result_type.fail(
                f"recorded directory physical identity changed: {previous.path}",
            )
        if previous.manifest is not None and current.manifest is None:
            return result_type.fail(
                f"recorded directory manifest disappeared: {previous.path}",
            )
        return result_type.ok(value=True)

    @classmethod
    def commit(
        cls,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[m.Infra.CodegenTransactionJournal]:
        """Validate the sole prepared-to-committed transition.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionJournal]``.

        """
        if journal.state != "prepared":
            return r[m.Infra.CodegenTransactionJournal].fail(
                "only a prepared codegen journal can be committed",
            )
        validated: p.Result[m.Infra.CodegenTransactionJournal] = u.validate_value(
            m.Infra.CodegenTransactionJournal,
            {
                "version": 8,
                "transaction_id": journal.transaction_id,
                "scope_device": journal.scope_device,
                "scope_inode": journal.scope_inode,
                "state": "committed",
                "projects": journal.projects,
                "file_participants": journal.file_participants,
                "sources": journal.sources,
                "directories": journal.directories,
                "entries": journal.entries,
                "staging_intents": journal.staging_intents,
            },
        )
        if validated.failure:
            return r[m.Infra.CodegenTransactionJournal].fail_op(
                "validate committed codegen journal",
                validated.error,
            )
        return r[m.Infra.CodegenTransactionJournal].ok(validated.value)

    @classmethod
    def begin_recovery(
        cls,
        journal: m.Infra.CodegenTransactionJournal,
        candidates: t.VariadicTuple[m.Infra.CodegenStagedFile | None],
    ) -> p.Result[m.Infra.CodegenTransactionJournal]:
        """Persist every rollback replacement identity before the first restore.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionJournal]``.

        """
        if journal.state != "prepared" or len(candidates) != len(journal.entries):
            return r[m.Infra.CodegenTransactionJournal].fail(
                "codegen recovery candidates differ from prepared journal",
            )
        entries: list[m.Infra.CodegenJournalEntry] = []
        for entry, candidate in zip(journal.entries, candidates, strict=True):
            replacement = None if candidate is None else candidate.replacement
            if (
                entry.original_exists
                and candidate is not None
                and (replacement is None or replacement.content is None)
            ):
                return r[m.Infra.CodegenTransactionJournal].fail(
                    f"codegen rollback candidate is incomplete: {entry.path}",
                )
            entry_data = entry.model_dump()
            entry_data.update({
                "rollback_exists": (
                    replacement is not None and replacement.content is not None
                ),
                "rollback_parent_device": entry.original_parent_device,
                "rollback_parent_inode": entry.original_parent_inode,
                "rollback_sha256": (
                    None
                    if replacement is None or replacement.content is None
                    else files.digest(replacement.content)
                ),
                "rollback_mode": None if replacement is None else replacement.mode,
                "rollback_device": None if replacement is None else replacement.device,
                "rollback_inode": None if replacement is None else replacement.inode,
                "rollback_link_count": (
                    None if replacement is None else replacement.link_count
                ),
                "rollback_file_attributes": (
                    None if replacement is None else replacement.file_attributes
                ),
                "rollback_reparse_tag": (
                    None if replacement is None else replacement.reparse_tag
                ),
                "rollback_staging": (
                    None
                    if replacement is None or entry.original_backup is None
                    else Path(entry.original_backup).with_suffix(".restore").as_posix()
                ),
            })
            validated_entry: p.Result[m.Infra.CodegenJournalEntry] = u.validate_value(
                m.Infra.CodegenJournalEntry,
                entry_data,
            )
            if validated_entry.failure:
                return r[m.Infra.CodegenTransactionJournal].fail_op(
                    "validate recovering codegen journal entry",
                    validated_entry.error,
                )
            entries.append(validated_entry.value)
        validated: p.Result[m.Infra.CodegenTransactionJournal] = u.validate_value(
            m.Infra.CodegenTransactionJournal,
            {
                "version": 8,
                "transaction_id": journal.transaction_id,
                "scope_device": journal.scope_device,
                "scope_inode": journal.scope_inode,
                "state": "recovering",
                "projects": journal.projects,
                "file_participants": journal.file_participants,
                "sources": journal.sources,
                "directories": journal.directories,
                "entries": tuple(entries),
                "staging_intents": journal.staging_intents,
            },
        )
        if validated.failure:
            return r[m.Infra.CodegenTransactionJournal].fail_op(
                "validate recovering codegen journal",
                validated.error,
            )
        return r[m.Infra.CodegenTransactionJournal].ok(validated.value)

    @classmethod
    def write(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        *,
        expected: m.Cli.AtomicFileState,
    ) -> p.Result[m.Cli.AtomicFileState]:
        """Create or transition the common journal with full-state CAS.

        Returns:
            The resulting ``p.Result[m.Cli.AtomicFileState]``.

        """
        content = journal.model_dump_json(indent=2).encode(c.Cli.ENCODING_DEFAULT)
        if expected.path != layout.journal_path:
            return r[m.Cli.AtomicFileState].fail(
                "codegen journal expected state belongs to another path",
            )
        written = u.Cli.atomic_write_binary_file_guarded(
            expected,
            content,
            permission_mode=c.Infra.JOURNAL_MODE,
        )
        if written.failure:
            return r[m.Cli.AtomicFileState].from_failure(written)
        observed = journal_state.journal_state(layout)
        if observed.failure:
            return r[m.Cli.AtomicFileState].from_failure(observed)
        observed_snapshot = journal_state.journal_snapshot(observed.value)
        if observed_snapshot is None:
            return r[m.Cli.AtomicFileState].fail(
                "published codegen journal parent disappeared",
            )
        if (
            observed_snapshot.content != content
            or observed_snapshot.mode != c.Infra.JOURNAL_MODE
        ):
            return r[m.Cli.AtomicFileState].fail(
                "published codegen journal differs from exact bytes or mode",
            )
        return r[m.Cli.AtomicFileState].ok(observed_snapshot)

    @classmethod
    def read(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Parse the typed v8 journal without deriving a second filesystem path.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        snapshot = journal_state.journal_state(layout)
        result_type = r[tuple[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]
        if snapshot.failure:
            return result_type.from_failure(snapshot)
        journal_snapshot = journal_state.journal_snapshot(snapshot.value)
        if journal_snapshot is None or journal_snapshot.content is None:
            return result_type.fail("codegen transaction journal is absent")
        if journal_snapshot.mode != c.Infra.JOURNAL_MODE:
            return result_type.fail("codegen transaction journal mode is not 0600")
        validated = m.Infra.CodegenTransactionJournal.model_validate_json(
            journal_snapshot.content,
        )
        relocated = cls._relocate_journal(layout, validated)
        if relocated.failure:
            return result_type.from_failure(relocated)
        return result_type.ok((relocated.value, journal_snapshot))

    @classmethod
    def cleanup(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        journal_snapshot: m.Cli.AtomicFileState,
    ) -> p.Result[bool]:
        """Retain journal authority until all journal-authorized cleanup completes.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        directories = journal_state.cleanup_journaled_directories(
            layout,
            journal,
            include_generated=journal.state != "committed",
        )
        if directories.failure:
            return directories
        removed = files.delete_state(journal_snapshot)
        if removed.failure:
            return r[bool].from_failure(removed)
        return r[bool].ok(value=True)

    @classmethod
    def source_record(
        cls,
        phase: str,
        source: m.Cli.AtomicFileState,
        previous: m.Infra.CodegenJournalSource | None = None,
    ) -> p.Result[m.Infra.CodegenJournalSource]:
        absent_parent = None
        if source.parent_device is None or source.parent_inode is None:
            if previous is not None:
                absent_parent = previous.absent_parent
            else:
                witness = u.Cli.atomic_plan_directory_chain(source.path.parent)
                if witness.failure:
                    return r[m.Infra.CodegenJournalSource].from_failure(witness)
                absent_parent = witness.value
        incomplete_source = source.content is not None and any((
            source.mode is None,
            source.device is None,
            source.inode is None,
            source.link_count is None,
            source.link_count is not None and source.link_count < 1,
        ))
        if incomplete_source:
            return r[m.Infra.CodegenJournalSource].fail(
                f"generation source identity is incomplete: {source.path}",
            )
        return r[m.Infra.CodegenJournalSource].ok(
            m.Infra.CodegenJournalSource(
                phase=phase,
                path=source.path,
                parent_device=source.parent_device,
                parent_inode=source.parent_inode,
                sha256=files.digest(source.content)
                if source.content is not None
                else None,
                mode=source.mode,
                device=source.device,
                inode=source.inode,
                link_count=source.link_count,
                file_attributes=source.file_attributes,
                reparse_tag=source.reparse_tag,
                absent_parent=absent_parent,
            ),
        )

    @classmethod
    def _merge_sources(
        cls,
        existing: t.VariadicTuple[m.Infra.CodegenJournalSource],
        sources: t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]],
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenJournalSource]]:
        result_type = r[tuple[m.Infra.CodegenJournalSource, ...]]
        by_key = {(source.phase, source.path): source for source in existing}
        order = [(source.phase, source.path) for source in existing]
        for phase, source in sources:
            key = (phase, source.path)
            previous = by_key.get(key)
            encoded = cls.source_record(phase, source, previous)
            if encoded.failure:
                return result_type.from_failure(encoded)
            if previous is not None and previous != encoded.value:
                return result_type.fail(
                    f"generation source changed between phases: {encoded.value.path}",
                )
            if previous is None:
                by_key[key] = encoded.value
                order.append(key)
        return result_type.ok(tuple(by_key[key] for key in order))

    @staticmethod
    def _entry_project(
        plan: m.Infra.MiseToolchainWorkspacePlan | m.Infra.CodegenFileSessionPlan,
        publication: m.Infra.CodegenStagedFile,
    ) -> p.Result[
        t.Pair[
            m.Infra.MiseToolchainProjectLayout | m.Infra.CodegenFileParticipant,
            str,
        ]
    ]:
        """Resolve the transaction participant and relative selector of a target.

        Returns:
            The registered Mise or file participant and relative selector.

        """
        result_type = r[
            t.Pair[
                m.Infra.MiseToolchainProjectLayout | m.Infra.CodegenFileParticipant,
                str,
            ]
        ]
        before = publication.before
        if before.parent_device is None or before.parent_inode is None:
            return result_type.fail(
                f"generation destination parent identity is incomplete: {before.path}",
            )
        project = next(
            (
                item
                for item in files.transaction_participants(plan.layout)
                if item.root == publication.project
            ),
            None,
        )
        if project is None or project.transaction_root is None:
            return result_type.fail(
                f"generation publication has no transaction participant: {before.path}",
            )
        selector = files.transaction_relative(plan.layout, before.path)
        if selector.failure:
            return result_type.from_failure(
                selector,
            )
        return result_type.ok(
            (project, selector.value),
        )

    @staticmethod
    def _backup_original(
        project: m.Infra.MiseToolchainProjectLayout | m.Infra.CodegenFileParticipant,
        before: m.Cli.AtomicFileState,
        index: int,
        recovery_roots: set[Path],
    ) -> p.Result[t.Pair[Path, bytes]]:
        """Authenticate one original and prepare its project recovery root.

        Returns:
            The backup path and original bytes, with their identity proven.

        """
        if (
            before.content is None
            or before.mode is None
            or before.device is None
            or before.inode is None
            or before.link_count != 1
        ):
            return r[t.Pair[Path, bytes]].fail(
                f"generation original identity is incomplete: {before.path}",
            )
        recovery_root = FlextInfraMiseArtifactsJournal._prepared_recovery_root(
            project,
            recovery_roots,
        )
        if recovery_root.failure:
            return r[t.Pair[Path, bytes]].from_failure(recovery_root)
        backup = recovery_root.value / f"{index:06d}.original"
        return r[t.Pair[Path, bytes]].ok((backup, before.content))

    @staticmethod
    def _write_original_backup(
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        prepared: t.Pair[Path, bytes],
        staging_intents: t.VariadicTuple[m.Infra.CodegenStagingIntent],
    ) -> p.Result[t.Pair[str, str]]:
        """Guard the backup write with its durable intention, then encode it.

        Returns:
            The backup selector and original digest after the guarded write.

        """
        backup, content = prepared
        intent = next(
            (item for item in staging_intents if item.before.path == backup),
            None,
        )
        if staging_intents and intent is None:
            return r[t.Pair[str, str]].fail(
                f"backup has no durable intention: {backup}",
            )
        written = process.write_new(
            backup,
            content,
            c.Infra.JOURNAL_MODE,
            intent=intent,
        )
        if written.failure:
            return r[t.Pair[str, str]].from_failure(written)
        relative_backup = files.transaction_relative(layout, backup)
        if relative_backup.failure:
            return r[t.Pair[str, str]].from_failure(relative_backup)
        return r[t.Pair[str, str]].ok((
            relative_backup.value,
            files.digest(content),
        ))

    @staticmethod
    def _prepared_recovery_root(
        project: m.Infra.MiseToolchainProjectLayout | m.Infra.CodegenFileParticipant,
        recovery_roots: set[Path],
    ) -> p.Result[Path]:
        """Inventory or create the project recovery root exactly once.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        if project.transaction_root is None:
            return r[Path].fail(
                f"transaction participant has no transaction root: {project.root}",
            )
        recovery_root = project.transaction_root / "recovery"
        if recovery_root in recovery_roots:
            return r[Path].ok(recovery_root)
        if recovery_root.exists() or recovery_root.is_symlink():
            inventory = u.Cli.atomic_inventory_physical_tree(recovery_root)
            if inventory.failure:
                return r[Path].from_failure(inventory)
        else:
            directory_before = u.Cli.atomic_read_empty_directory_state(
                recovery_root,
                required=False,
            )
            if directory_before.failure:
                return r[Path].from_failure(directory_before)
            created = u.Cli.atomic_create_empty_directory_guarded(
                directory_before.value,
                permission_mode=0o700,
            )
            if created.failure:
                return r[Path].from_failure(created)
        recovery_roots.add(recovery_root)
        return r[Path].ok(recovery_root)

    @classmethod
    def _desired_staging_selector(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        replacement: m.Cli.AtomicFileState,
        destination: Path,
    ) -> p.Result[str]:
        """Prove a replacement's complete identity before encoding its path.

        Returns:
            The staging selector for an authenticated replacement.

        """
        incomplete = any((
            replacement.content is None,
            replacement.mode is None,
            replacement.device is None,
            replacement.inode is None,
            replacement.link_count != 1,
        ))
        if incomplete:
            return r[str].fail(
                f"generation staged identity is incomplete: {destination}",
            )
        relative_staging = files.transaction_relative(layout, replacement.path)
        if relative_staging.failure:
            return r[str].from_failure(relative_staging)
        return r[str].ok(relative_staging.value)

    @classmethod
    def _journal_entry(
        cls,
        plan: m.Infra.MiseToolchainWorkspacePlan | m.Infra.CodegenFileSessionPlan,
        publication: m.Infra.CodegenStagedFile,
        *,
        index: int,
        recovery_roots: set[Path],
        staging_intents: t.VariadicTuple[m.Infra.CodegenStagingIntent] = (),
    ) -> p.Result[m.Infra.CodegenJournalEntry]:
        before = publication.before
        if before.parent_device is None or before.parent_inode is None:
            return r[m.Infra.CodegenJournalEntry].fail(
                f"generation destination parent identity is incomplete: {before.path}",
            )
        located = cls._entry_project(plan, publication)
        if located.failure:
            return r[m.Infra.CodegenJournalEntry].from_failure(located)
        project, selector = located.value
        backup_selector: str | None = None
        original_sha: str | None = None
        if before.content is not None:
            backup = cls._backup_original(
                project,
                before,
                index,
                recovery_roots,
            )
            if backup.failure:
                return r[m.Infra.CodegenJournalEntry].from_failure(backup)
            written_backup = cls._write_original_backup(
                plan.layout,
                backup.value,
                staging_intents,
            )
            if written_backup.failure:
                return r[m.Infra.CodegenJournalEntry].from_failure(written_backup)
            backup_selector, original_sha = written_backup.value
        replacement = publication.replacement
        desired_exists = replacement is not None
        desired_staging: str | None = None
        if replacement is not None:
            staging = cls._desired_staging_selector(
                plan.layout,
                replacement,
                before.path,
            )
            if staging.failure:
                return r[m.Infra.CodegenJournalEntry].from_failure(staging)
            desired_staging = staging.value
        return r[m.Infra.CodegenJournalEntry].ok(
            m.Infra.CodegenJournalEntry(
                phase=publication.phase,
                project=project.selector,
                path=selector,
                desired_staging=desired_staging,
                original_exists=before.content is not None,
                original_parent_device=before.parent_device,
                original_parent_inode=before.parent_inode,
                original_backup=backup_selector,
                original_sha256=original_sha,
                original_mode=before.mode,
                original_device=before.device,
                original_inode=before.inode,
                original_link_count=1 if before.content is not None else None,
                original_file_attributes=before.file_attributes,
                original_reparse_tag=before.reparse_tag,
                desired_exists=desired_exists,
                desired_parent_device=before.parent_device,
                desired_parent_inode=before.parent_inode,
                desired_sha256=(
                    files.digest(replacement.content)
                    if replacement is not None and replacement.content is not None
                    else None
                ),
                desired_mode=None if replacement is None else replacement.mode,
                desired_device=None if replacement is None else replacement.device,
                desired_inode=None if replacement is None else replacement.inode,
                desired_link_count=1 if replacement is not None else None,
                desired_file_attributes=(
                    None if replacement is None else replacement.file_attributes
                ),
                desired_reparse_tag=(
                    None if replacement is None else replacement.reparse_tag
                ),
            ),
        )

    @classmethod
    def _validate_physical_topology(
        cls,
        plan: m.Infra.MiseToolchainWorkspacePlan | m.Infra.CodegenFileSessionPlan,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[bool]:
        """Use the same capability and physical topology proof as recovery.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return FlextInfraMiseArtifactsVerification.journal_topology(
            plan.layout,
            journal,
        )


__all__: list[str] = ["FlextInfraMiseArtifactsJournal"]
