"""Authenticated physical-scope relocation for durable generation journals.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import m, p, r, t, u
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)


class FlextInfraMiseArtifactsJournalRelocation:
    """Rebind paths only after proving the journal's unchanged physical owners."""

    @classmethod
    def _relocate_journal(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[m.Infra.CodegenTransactionJournal]:
        """Rebind authenticated paths when the same physical worktree was moved.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionJournal]``.

        """
        result_type = r[m.Infra.CodegenTransactionJournal]
        recorded_root = cls._relocation_context(layout, journal)
        if recorded_root.failure:
            return result_type.from_failure(recorded_root)
        relocation_root, relocation_needed = recorded_root.value
        if not relocation_needed:
            return result_type.ok(journal)
        relocated = cls._relocated_bodies(layout, journal, relocation_root)
        if relocated.failure:
            return result_type.from_failure(relocated)
        sources, directories, staging_intents = relocated.value
        validated: p.Result[m.Infra.CodegenTransactionJournal] = u.validate_value(
            m.Infra.CodegenTransactionJournal,
            {
                **journal.model_dump(),
                "file_participants": layout.file_participants,
                "sources": sources,
                "directories": directories,
                "staging_intents": staging_intents,
            },
        )
        if validated.failure:
            return result_type.fail_op("relocate generation journal", validated.error)
        return result_type.ok(validated.value)

    @classmethod
    def _relocation_context(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[t.Pair[Path, bool]]:
        """Prove the journal belongs to this scope and derive its recorded root.

        Returns:
            The resulting ``p.Result[t.Pair[Path, bool]]`` where the boolean
            marks relocation need (False: a journal already recorded against
            the current scope, nothing to relocate).

        """
        identity = files.physical_directory_identity(layout.scope_root)
        if identity.failure:
            return r[t.Pair[Path, bool]].from_failure(identity)
        if identity.value != (journal.scope_device, journal.scope_inode):
            return r[t.Pair[Path, bool]].fail(
                "generation journal belongs to another physical scope",
            )
        recorded_root = cls._recorded_scope_root(journal, layout.scope_root)
        if recorded_root.failure:
            return r[t.Pair[Path, bool]].from_failure(recorded_root)
        if recorded_root.value == layout.scope_root:
            return r[t.Pair[Path, bool]].ok((layout.scope_root, False))
        return r[t.Pair[Path, bool]].ok((recorded_root.value, True))

    @staticmethod
    def _verified_relocation_participants(
        recorded_participants: t.MappingKV[str, m.Infra.CodegenFileParticipant],
        current_participants: t.MappingKV[str, m.Infra.CodegenFileParticipant],
    ) -> p.Result[bool]:
        """Require identical participant inventories and physical identities.

        Returns:
            Whether the recorded participants match the current layout.

        """
        if recorded_participants.keys() != current_participants.keys():
            return r[bool].fail(
                "generation journal file participant inventory changed",
            )
        for selector, recorded in recorded_participants.items():
            current = current_participants[selector]
            if (recorded.device, recorded.inode) != (current.device, current.inode):
                return r[bool].fail(
                    f"generation journal file participant changed: {selector}",
                )
        return r[bool].ok(value=True)

    @classmethod
    def _relocated_bodies(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        recorded_root: Path,
    ) -> p.Result[
        t.Triple[
            t.VariadicTuple[m.Infra.CodegenJournalSource],
            t.VariadicTuple[m.Infra.CodegenJournalDirectory],
            t.VariadicTuple[m.Infra.CodegenStagingIntent],
        ]
    ]:
        """Rebind sources, directories, and staging intentions onto the scope.

        Returns:
            The three ordered inventories with their physical identities retained.

        """
        result_type = r[
            t.Triple[
                t.VariadicTuple[m.Infra.CodegenJournalSource],
                t.VariadicTuple[m.Infra.CodegenJournalDirectory],
                t.VariadicTuple[m.Infra.CodegenStagingIntent],
            ]
        ]
        recorded_participants = {
            participant.selector: participant
            for participant in journal.file_participants
        }
        current_participants = {
            participant.selector: participant
            for participant in layout.file_participants
        }
        verified = cls._verified_relocation_participants(
            recorded_participants,
            current_participants,
        )
        if verified.failure:
            return result_type.from_failure(verified)
        sources: list[m.Infra.CodegenJournalSource] = []
        directories: list[m.Infra.CodegenJournalDirectory] = []
        for source in journal.sources:
            previous_root, current_root = cls._relocation_roots(
                source.path,
                recorded_root,
                layout.scope_root,
                recorded_participants,
                current_participants,
            )
            rebound = cls._relocated_path(source.path, previous_root, current_root)
            if rebound.failure:
                return result_type.from_failure(rebound)
            sources.append(source.model_copy(update={"path": rebound.value}))
        for directory in journal.directories:
            previous_root = recorded_root
            current_root = layout.scope_root
            recorded_participant = recorded_participants.get(directory.project)
            if recorded_participant is not None:
                previous_root = recorded_participant.root
                current_root = current_participants[directory.project].root
            relocated = cls._relocated_directory(
                directory,
                previous_root,
                current_root,
            )
            if relocated.failure:
                return result_type.from_failure(relocated)
            directories.append(relocated.value)
        intents: list[m.Infra.CodegenStagingIntent] = []
        for intent in journal.staging_intents:
            previous_root, current_root = cls._relocation_roots(
                intent.before.path,
                recorded_root,
                layout.scope_root,
                recorded_participants,
                current_participants,
            )
            rebound = cls._relocated_path(
                intent.before.path,
                previous_root,
                current_root,
            )
            if rebound.failure:
                return result_type.from_failure(rebound)
            created = intent.created
            if created is not None:
                created = created.model_copy(update={"path": rebound.value})
            intents.append(
                m.Infra.CodegenStagingIntent.model_validate({
                    **intent.model_dump(),
                    "before": intent.before.model_copy(update={"path": rebound.value}),
                    "created": created,
                }),
            )
        return result_type.ok((tuple(sources), tuple(directories), tuple(intents)))

    @classmethod
    def _relocated_directory(
        cls,
        directory: m.Infra.CodegenJournalDirectory,
        previous_root: Path,
        current_root: Path,
    ) -> p.Result[m.Infra.CodegenJournalDirectory]:
        """Rebind one directory's states and manifest onto the current scope.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenJournalDirectory]``.

        """
        before: m.Cli.AtomicDirectoryState | None = None
        if directory.before is not None:
            relocated_before = cls._relocate_directory_state(
                directory.before,
                previous_root,
                current_root,
            )
            if relocated_before.failure:
                return r[m.Infra.CodegenJournalDirectory].from_failure(
                    relocated_before,
                )
            before = relocated_before.value
        created: m.Cli.AtomicDirectoryState | None = None
        if directory.created is not None:
            relocated_created = cls._relocate_directory_state(
                directory.created,
                previous_root,
                current_root,
            )
            if relocated_created.failure:
                return r[m.Infra.CodegenJournalDirectory].from_failure(
                    relocated_created,
                )
            created = relocated_created.value
        manifest: m.Cli.AtomicPhysicalTreeManifest | None = None
        if directory.manifest is not None:
            relocated_manifest = cls._relocate_manifest(
                directory.manifest,
                previous_root,
                current_root,
            )
            if relocated_manifest.failure:
                return r[m.Infra.CodegenJournalDirectory].from_failure(
                    relocated_manifest,
                )
            manifest = relocated_manifest.value
        return u.validate_value(
            m.Infra.CodegenJournalDirectory,
            {
                **directory.model_dump(),
                "before": before,
                "created": created,
                "manifest": manifest,
            },
        ).map_error(lambda error: f"relocate generation directory: {error}")

    @classmethod
    def _recorded_scope_root(
        cls,
        journal: m.Infra.CodegenTransactionJournal,
        current_scope: Path,
    ) -> p.Result[Path]:
        candidates = {
            participant.root
            for participant in journal.file_participants
            if (participant.device, participant.inode)
            == (journal.scope_device, journal.scope_inode)
        }
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
        directory: m.Infra.CodegenJournalDirectory,
        participants: t.MappingKV[str, Path],
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Recover the workspace root candidates or validate an external owner.

        A directory owned by a recorded participant contributes no candidate, so
        the empty tuple is the typed absence here, never None.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

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
                f"generation directory path is inconsistent: {directory.path}",
            )
        candidates: set[Path] = set()
        for state in states:
            candidate = state.path
            for _part in relative.parts:
                candidate = candidate.parent
            if candidate / relative != state.path:
                return r[t.VariadicTuple[Path]].fail(
                    f"generation directory path is inconsistent: {directory.path}",
                )
            candidates.add(candidate)
        if len(candidates) > 1:
            return r[t.VariadicTuple[Path]].fail(
                f"generation directory path is inconsistent: {directory.path}",
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
        """Resolve the physical owner roots for one journaled absolute path.

        Returns:
            The resulting ``t.Pair[Path, Path]``.

        """
        for selector, participant in recorded_participants.items():
            if path.is_relative_to(participant.root):
                return participant.root, current_participants[selector].root
        return recorded_scope, current_scope

    @classmethod
    def _relocated_path(
        cls,
        path: Path,
        previous_root: Path,
        current_root: Path,
    ) -> p.Result[Path]:
        if not path.is_relative_to(previous_root):
            return r[Path].fail(
                f"generation journal path escapes recorded scope: {path}",
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
            directory_state.model_copy(update={"path": rebound.value}),
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
                "relocate generation tree manifest",
                validated.error,
            )
        return result_type.ok(validated.value)


__all__: list[str] = ["FlextInfraMiseArtifactsJournalRelocation"]
