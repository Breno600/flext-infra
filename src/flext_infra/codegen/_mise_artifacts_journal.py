"""Durable journal for one extensible workspace generation transaction."""

from __future__ import annotations

from pathlib import Path

from flext_core import r
from flext_infra import c, m, p, t, u

from ._mise_artifacts_files import FlextInfraMiseArtifactsFiles as files
from ._mise_artifacts_process import FlextInfraMiseArtifactsProcess as process
from ._mise_artifacts_state import FlextInfraMiseArtifactsState as journal_state


class FlextInfraMiseArtifactsJournal:
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
        """Build staging authority before any disposable transaction root exists."""
        physical_scope = files.physical_directory_identity(plan.layout.scope_root)
        if physical_scope.failure:
            return r[m.Infra.CodegenTransactionJournal].from_failure(physical_scope)
        projects: list[m.Infra.CodegenJournalProject] = []
        for project in plan.layout.projects:
            physical_project = files.physical_directory_identity(project.root)
            if physical_project.failure:
                return r[m.Infra.CodegenTransactionJournal].from_failure(
                    physical_project
                )
            projects.append(
                m.Infra.CodegenJournalProject(
                    selector=project.selector,
                    device=physical_project.value[0],
                    inode=physical_project.value[1],
                )
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
                "validate staging codegen journal", validated.error
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
        """Back up one complete phase and return its extended prepared authority."""
        if journal.state not in {"staging", "prepared"}:
            return r[m.Infra.CodegenTransactionJournal].fail(
                "only staging or prepared codegen journal accepts a phase"
            )
        topology = cls._validate_physical_topology(plan, journal)
        if topology.failure:
            return r[m.Infra.CodegenTransactionJournal].from_failure(topology)
        existing_paths = {entry.path for entry in journal.entries}
        entries = list(journal.entries)
        recovery_roots: set[Path] = set()
        for offset, publication in enumerate(publications, start=len(entries)):
            target = files.transaction_relative(plan.layout, publication.before.path)
            if target.failure:
                return r[m.Infra.CodegenTransactionJournal].from_failure(target)
            if target.value in existing_paths:
                return r[m.Infra.CodegenTransactionJournal].fail(
                    f"multiple generation phases own one destination: {target.value}"
                )
            entry = cls._journal_entry(
                plan, publication, index=offset, recovery_roots=recovery_roots
            )
            if entry.failure:
                return r[m.Infra.CodegenTransactionJournal].from_failure(entry)
            entries.append(entry.value)
            existing_paths.add(entry.value.path)
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
            },
        )
        if validated.failure:
            return r[m.Infra.CodegenTransactionJournal].fail_op(
                "validate prepared codegen journal", validated.error
            )
        return r[m.Infra.CodegenTransactionJournal].ok(validated.value)

    @classmethod
    def append_directories(
        cls,
        journal: m.Infra.CodegenTransactionJournal,
        directories: t.VariadicTuple[m.Infra.CodegenJournalDirectory],
    ) -> p.Result[m.Infra.CodegenTransactionJournal]:
        """Extend durable directory authority before materializing any new path."""
        if journal.state not in {"staging", "prepared"}:
            return r[m.Infra.CodegenTransactionJournal].fail(
                "only staging or prepared codegen journal accepts directories"
            )
        existing = {directory.path for directory in journal.directories}
        duplicate = next(
            (directory.path for directory in directories if directory.path in existing),
            None,
        )
        if duplicate is not None:
            return r[m.Infra.CodegenTransactionJournal].fail(
                f"generation directory already has an owner: {duplicate}"
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
            },
        )
        if validated.failure:
            return r[m.Infra.CodegenTransactionJournal].fail_op(
                "validate extended codegen directory journal", validated.error
            )
        return r[m.Infra.CodegenTransactionJournal].ok(validated.value)

    @classmethod
    def record_transaction_manifests(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[m.Infra.CodegenTransactionJournal]:
        """Validate physical manifests and retain them in the transaction journal."""
        from ._mise_artifacts_verification import FlextInfraMiseArtifactsVerification

        registered = FlextInfraMiseArtifactsVerification.register_transaction_manifests(
            layout, journal
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
        """Advance physical directory evidence without changing its durable intent."""
        result_type = r[m.Infra.CodegenTransactionJournal]
        if tuple(directory.path for directory in directories) != tuple(
            directory.path for directory in journal.directories
        ):
            return result_type.fail("recorded directory topology differs from journal")
        for previous, current in zip(journal.directories, directories, strict=True):
            stable_previous = previous.model_dump(
                exclude={"before", "created", "manifest"}
            )
            stable_current = current.model_dump(
                exclude={"before", "created", "manifest"}
            )
            if stable_current != stable_previous:
                return result_type.fail(
                    f"recorded directory intent changed: {previous.path}"
                )
            if previous.before is not None and current.before != previous.before:
                return result_type.fail(
                    f"recorded directory parent binding changed: {previous.path}"
                )
            if previous.before is None and current.before is None and current.created:
                return result_type.fail(
                    f"created directory lacks parent binding: {previous.path}"
                )
            if previous.created is not None and current.created != previous.created:
                return result_type.fail(
                    f"recorded directory physical identity changed: {previous.path}"
                )
            if previous.manifest is not None and current.manifest is None:
                return result_type.fail(
                    f"recorded directory manifest disappeared: {previous.path}"
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
                "directories": directories,
                "entries": journal.entries,
            },
        )
        if validated.failure:
            return result_type.fail_op(
                "validate recorded directory evidence", validated.error
            )
        return result_type.ok(validated.value)

    @classmethod
    def commit(
        cls, journal: m.Infra.CodegenTransactionJournal
    ) -> p.Result[m.Infra.CodegenTransactionJournal]:
        """Validate the sole prepared-to-committed transition."""
        if journal.state != "prepared":
            return r[m.Infra.CodegenTransactionJournal].fail(
                "only a prepared codegen journal can be committed"
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
            },
        )
        if validated.failure:
            return r[m.Infra.CodegenTransactionJournal].fail_op(
                "validate committed codegen journal", validated.error
            )
        return r[m.Infra.CodegenTransactionJournal].ok(validated.value)

    @classmethod
    def begin_recovery(
        cls,
        journal: m.Infra.CodegenTransactionJournal,
        candidates: t.VariadicTuple[m.Infra.CodegenStagedFile | None],
    ) -> p.Result[m.Infra.CodegenTransactionJournal]:
        """Persist every rollback replacement identity before the first restore."""
        if journal.state != "prepared" or len(candidates) != len(journal.entries):
            return r[m.Infra.CodegenTransactionJournal].fail(
                "codegen recovery candidates differ from prepared journal"
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
                    f"codegen rollback candidate is incomplete: {entry.path}"
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
                m.Infra.CodegenJournalEntry, entry_data
            )
            if validated_entry.failure:
                return r[m.Infra.CodegenTransactionJournal].fail_op(
                    "validate recovering codegen journal entry", validated_entry.error
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
            },
        )
        if validated.failure:
            return r[m.Infra.CodegenTransactionJournal].fail_op(
                "validate recovering codegen journal", validated.error
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
        """Create or transition the common journal with full-state CAS."""
        content = journal.model_dump_json(indent=2).encode(c.Cli.ENCODING_DEFAULT)
        if expected.path != layout.journal_path:
            return r[m.Cli.AtomicFileState].fail(
                "codegen journal expected state belongs to another path"
            )
        written = u.Cli.atomic_write_binary_file_guarded(
            expected, content, permission_mode=c.Infra.JOURNAL_MODE
        )
        if written.failure:
            return r[m.Cli.AtomicFileState].from_failure(written)
        observed = journal_state.journal_state(layout)
        if observed.failure:
            return r[m.Cli.AtomicFileState].from_failure(observed)
        observed_snapshot = journal_state.journal_snapshot(observed.value)
        if observed_snapshot is None:
            return r[m.Cli.AtomicFileState].fail(
                "published codegen journal parent disappeared"
            )
        if (
            observed_snapshot.content != content
            or observed_snapshot.mode != c.Infra.JOURNAL_MODE
        ):
            return r[m.Cli.AtomicFileState].fail(
                "published codegen journal differs from exact bytes or mode"
            )
        return r[m.Cli.AtomicFileState].ok(observed_snapshot)

    @classmethod
    def read(
        cls, layout: m.Infra.MiseToolchainWorkspaceLayout
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Parse the typed v8 journal without deriving a second filesystem path."""
        snapshot = journal_state.journal_state(layout)
        result_type = r[tuple[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]
        if snapshot.failure:
            return result_type.from_failure(snapshot)
        journal_snapshot = journal_state.journal_snapshot(snapshot.value)
        if journal_snapshot is None or journal_snapshot.content is None:
            return result_type.fail("codegen transaction journal is absent")
        if journal_snapshot.mode != c.Infra.JOURNAL_MODE:
            return result_type.fail("codegen transaction journal mode is not 0600")
        validated: p.Result[m.Infra.CodegenTransactionJournal] = u.validate_value(
            m.Infra.CodegenTransactionJournal, journal_snapshot.content, from_json=True
        )
        if validated.failure:
            return result_type.fail_op(
                "validate codegen transaction journal", validated.error
            )
        relocated = cls._relocate_journal(layout, validated.value)
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
        """Retain journal authority until all journal-authorized cleanup completes."""
        directories = journal_state.cleanup_journaled_directories(
            layout, journal, include_generated=journal.state != "committed"
        )
        if directories.failure:
            return directories
        removed = files.delete_state(journal_snapshot)
        if removed.failure:
            return r[bool].from_failure(removed)
        return r[bool].ok(True)

    @classmethod
    def _relocate_journal(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[m.Infra.CodegenTransactionJournal]:
        """Rebind authenticated paths when the same physical worktree was moved."""
        result_type = r[m.Infra.CodegenTransactionJournal]
        identity = files.physical_directory_identity(layout.scope_root)
        if identity.failure:
            return result_type.from_failure(identity)
        if identity.value != (journal.scope_device, journal.scope_inode):
            return result_type.fail(
                "generation journal belongs to another physical scope"
            )
        recorded_root = cls._recorded_scope_root(journal, layout.scope_root)
        if recorded_root.failure:
            return result_type.from_failure(recorded_root)
        recorded_participants = {
            participant.selector: participant
            for participant in journal.file_participants
        }
        current_participants = {
            participant.selector: participant
            for participant in layout.file_participants
        }
        if recorded_root.value == layout.scope_root:
            return result_type.ok(journal)
        if recorded_participants.keys() != current_participants.keys():
            return result_type.fail(
                "generation journal file participant inventory changed"
            )
        for selector, recorded in recorded_participants.items():
            current = current_participants[selector]
            if (recorded.device, recorded.inode) != (current.device, current.inode):
                return result_type.fail(
                    f"generation journal file participant changed: {selector}"
                )
        sources: list[m.Infra.CodegenJournalSource] = []
        directories: list[m.Infra.CodegenJournalDirectory] = []
        for source in journal.sources:
            previous_root, current_root = cls._relocation_roots(
                source.path,
                recorded_root.value,
                layout.scope_root,
                recorded_participants,
                current_participants,
            )
            rebound = cls._relocated_path(source.path, previous_root, current_root)
            if rebound.failure:
                return result_type.from_failure(rebound)
            sources.append(source.model_copy(update={"path": rebound.value}))
        for directory in journal.directories:
            previous_root = recorded_root.value
            current_root = layout.scope_root
            recorded_participant = recorded_participants.get(directory.project)
            if recorded_participant is not None:
                previous_root = recorded_participant.root
                current_root = current_participants[directory.project].root
            before: m.Cli.AtomicDirectoryState | None = None
            if directory.before is not None:
                relocated_before = cls._relocate_directory_state(
                    directory.before, previous_root, current_root
                )
                if relocated_before.failure:
                    return result_type.from_failure(relocated_before)
                before = relocated_before.value
            created: m.Cli.AtomicDirectoryState | None = None
            if directory.created is not None:
                relocated_created = cls._relocate_directory_state(
                    directory.created, previous_root, current_root
                )
                if relocated_created.failure:
                    return result_type.from_failure(relocated_created)
                created = relocated_created.value
            manifest: m.Cli.AtomicPhysicalTreeManifest | None = None
            if directory.manifest is not None:
                relocated_manifest = cls._relocate_manifest(
                    directory.manifest, previous_root, current_root
                )
                if relocated_manifest.failure:
                    return result_type.from_failure(relocated_manifest)
                manifest = relocated_manifest.value
            validated_directory: p.Result[m.Infra.CodegenJournalDirectory] = (
                u.validate_value(
                    m.Infra.CodegenJournalDirectory,
                    {
                        **directory.model_dump(),
                        "before": before,
                        "created": created,
                        "manifest": manifest,
                    },
                )
            )
            if validated_directory.failure:
                return result_type.fail_op(
                    "relocate generation directory", validated_directory.error
                )
            directories.append(validated_directory.value)
        validated: p.Result[m.Infra.CodegenTransactionJournal] = u.validate_value(
            m.Infra.CodegenTransactionJournal,
            {
                **journal.model_dump(),
                "file_participants": layout.file_participants,
                "sources": tuple(sources),
                "directories": tuple(directories),
            },
        )
        if validated.failure:
            return result_type.fail_op("relocate generation journal", validated.error)
        return result_type.ok(validated.value)

    @classmethod
    def _recorded_scope_root(
        cls, journal: m.Infra.CodegenTransactionJournal, current_scope: Path
    ) -> p.Result[Path]:
        candidates: set[Path] = set()
        participants = {
            participant.selector: participant.root
            for participant in journal.file_participants
        }
        for directory in journal.directories:
            candidate = cls._recorded_directory_roots(directory, participants)
            if candidate.failure:
                return r[Path].from_failure(candidate)
            candidates.update(candidate.value)
        if not candidates:
            return r[Path].ok(current_scope)
        if len(candidates) != 1:
            return r[Path].fail("generation journal has no single recorded scope path")
        return r[Path].ok(candidates.pop())

    @staticmethod
    def _recorded_directory_roots(
        directory: m.Infra.CodegenJournalDirectory, participants: t.MappingKV[str, Path]
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Recover the workspace root candidates or validate an external owner.

        A directory owned by a recorded participant contributes no candidate, so
        the empty tuple is the typed absence here, never None.
        """
        relative = Path(directory.path)
        selector = relative.parts[0]
        participant_root = participants.get(selector)
        states = tuple(
            state
            for state in (directory.before, directory.created)
            if state is not None
        )
        if participant_root is not None:
            expected = participant_root.joinpath(*relative.parts[1:])
            valid = directory.project == selector and all(
                state.path == expected for state in states
            )
            if valid:
                return r[t.VariadicTuple[Path]].ok(())
            return r[t.VariadicTuple[Path]].fail(
                f"generation directory path is inconsistent: {directory.path}"
            )
        candidates: set[Path] = set()
        for state in states:
            candidate = state.path
            for _part in relative.parts:
                candidate = candidate.parent
            if candidate / relative != state.path:
                return r[t.VariadicTuple[Path]].fail(
                    f"generation directory path is inconsistent: {directory.path}"
                )
            candidates.add(candidate)
        if len(candidates) > 1:
            return r[t.VariadicTuple[Path]].fail(
                f"generation directory path is inconsistent: {directory.path}"
            )
        return r[t.VariadicTuple[Path]].ok(tuple(candidates))

    @staticmethod
    def _relocation_roots(
        path: Path,
        recorded_scope: Path,
        current_scope: Path,
        recorded_participants: t.MappingKV[str, m.Infra.CodegenFileParticipant],
        current_participants: t.MappingKV[str, m.Infra.CodegenFileParticipant],
    ) -> t.Pair[Path, Path]:
        """Resolve the physical owner roots for one journaled absolute path."""
        for selector, participant in recorded_participants.items():
            if path.is_relative_to(participant.root):
                return participant.root, current_participants[selector].root
        return recorded_scope, current_scope

    @classmethod
    def _relocated_path(
        cls, path: Path, previous_root: Path, current_root: Path
    ) -> p.Result[Path]:
        if not path.is_relative_to(previous_root):
            return r[Path].fail(
                f"generation journal path escapes recorded scope: {path}"
            )
        return r[Path].ok(current_root / path.relative_to(previous_root))

    @classmethod
    def _relocate_directory_state(
        cls,
        directory_state: m.Cli.AtomicDirectoryState,
        previous_root: Path,
        current_root: Path,
    ) -> p.Result[m.Cli.AtomicDirectoryState]:
        rebound = cls._relocated_path(directory_state.path, previous_root, current_root)
        if rebound.failure:
            return r[m.Cli.AtomicDirectoryState].from_failure(rebound)
        return r[m.Cli.AtomicDirectoryState].ok(
            directory_state.model_copy(update={"path": rebound.value})
        )

    @classmethod
    def _relocate_manifest(
        cls,
        manifest: m.Cli.AtomicPhysicalTreeManifest,
        previous_root: Path,
        current_root: Path,
    ) -> p.Result[m.Cli.AtomicPhysicalTreeManifest]:
        result_type = r[m.Cli.AtomicPhysicalTreeManifest]
        relocated: list[m.Cli.AtomicPhysicalTreeEntry] = []
        for entry in (manifest.root, *manifest.entries):
            rebound = cls._relocated_path(entry.path, previous_root, current_root)
            if rebound.failure:
                return result_type.from_failure(rebound)
            relocated.append(entry.model_copy(update={"path": rebound.value}))
        validated: p.Result[m.Cli.AtomicPhysicalTreeManifest] = u.validate_value(
            m.Cli.AtomicPhysicalTreeManifest,
            {"root": relocated[0], "entries": tuple(relocated[1:])},
        )
        if validated.failure:
            return result_type.fail_op(
                "relocate generation tree manifest", validated.error
            )
        return result_type.ok(validated.value)

    @classmethod
    def _journal_source(
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
                f"generation source identity is incomplete: {source.path}"
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
            )
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
            encoded = cls._journal_source(phase, source, previous)
            if encoded.failure:
                return result_type.from_failure(encoded)
            if previous is not None and previous != encoded.value:
                return result_type.fail(
                    f"generation source changed between phases: {encoded.value.path}"
                )
            if previous is None:
                by_key[key] = encoded.value
                order.append(key)
        return result_type.ok(tuple(by_key[key] for key in order))

    @classmethod
    def _journal_entry(
        cls,
        plan: m.Infra.MiseToolchainWorkspacePlan | m.Infra.CodegenFileSessionPlan,
        publication: m.Infra.CodegenStagedFile,
        *,
        index: int,
        recovery_roots: set[Path],
    ) -> p.Result[m.Infra.CodegenJournalEntry]:
        before = publication.before
        if before.parent_device is None or before.parent_inode is None:
            return r[m.Infra.CodegenJournalEntry].fail(
                f"generation destination parent identity is incomplete: {before.path}"
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
            return r[m.Infra.CodegenJournalEntry].fail(
                f"generation publication has no transaction participant: {before.path}"
            )
        selector = files.transaction_relative(plan.layout, before.path)
        if selector.failure:
            return r[m.Infra.CodegenJournalEntry].from_failure(selector)
        backup_selector: str | None = None
        original_sha: str | None = None
        if before.content is not None:
            if (
                before.mode is None
                or before.device is None
                or before.inode is None
                or before.link_count != 1
            ):
                return r[m.Infra.CodegenJournalEntry].fail(
                    f"generation original identity is incomplete: {before.path}"
                )
            recovery_root = project.transaction_root / "recovery"
            if recovery_root not in recovery_roots:
                if recovery_root.exists() or recovery_root.is_symlink():
                    inventory = u.Cli.atomic_inventory_physical_tree(recovery_root)
                    if inventory.failure:
                        return r[m.Infra.CodegenJournalEntry].from_failure(inventory)
                else:
                    directory_before = u.Cli.atomic_read_empty_directory_state(
                        recovery_root, required=False
                    )
                    if directory_before.failure:
                        return r[m.Infra.CodegenJournalEntry].from_failure(
                            directory_before
                        )
                    created = u.Cli.atomic_create_empty_directory_guarded(
                        directory_before.value, permission_mode=0o700
                    )
                    if created.failure:
                        return r[m.Infra.CodegenJournalEntry].from_failure(created)
                recovery_roots.add(recovery_root)
            backup = recovery_root / f"{index:06d}.original"
            written = process.write_new(backup, before.content, c.Infra.JOURNAL_MODE)
            if written.failure:
                return r[m.Infra.CodegenJournalEntry].from_failure(written)
            relative_backup = files.transaction_relative(plan.layout, backup)
            if relative_backup.failure:
                return r[m.Infra.CodegenJournalEntry].from_failure(relative_backup)
            backup_selector = relative_backup.value
            original_sha = files.digest(before.content)
        replacement = publication.replacement
        desired_exists = replacement is not None
        incomplete_replacement = replacement is not None and any((
            replacement.content is None,
            replacement.mode is None,
            replacement.device is None,
            replacement.inode is None,
            replacement.link_count != 1,
        ))
        if incomplete_replacement:
            return r[m.Infra.CodegenJournalEntry].fail(
                f"generation staged identity is incomplete: {before.path}"
            )
        desired_staging: str | None = None
        if replacement is not None:
            relative_staging = files.transaction_relative(plan.layout, replacement.path)
            if relative_staging.failure:
                return r[m.Infra.CodegenJournalEntry].from_failure(relative_staging)
            desired_staging = relative_staging.value
        return r[m.Infra.CodegenJournalEntry].ok(
            m.Infra.CodegenJournalEntry(
                phase=publication.phase,
                project=project.selector,
                path=selector.value,
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
            )
        )

    @classmethod
    def _validate_physical_topology(
        cls,
        plan: m.Infra.MiseToolchainWorkspacePlan | m.Infra.CodegenFileSessionPlan,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[bool]:
        """Use the same capability and physical topology proof as recovery."""
        from ._mise_artifacts_verification import FlextInfraMiseArtifactsVerification

        return FlextInfraMiseArtifactsVerification.journal_topology(
            plan.layout, journal
        )


__all__: list[str] = ["FlextInfraMiseArtifactsJournal"]
