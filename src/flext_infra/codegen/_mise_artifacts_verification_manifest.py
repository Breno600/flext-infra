"""Temporary-tree manifest registration and transition verification.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping, Set as AbstractSet
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from flext_core import r
from flext_infra import c, m, t, u
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)

if TYPE_CHECKING:
    from flext_infra import p

type _JournalFileRole = Literal["desired", "backup", "rollback"]


class FlextInfraMiseArtifactsVerificationManifest:
    """Register and authenticate transaction temporary-tree manifests."""

    @classmethod
    def register_transaction_manifests(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        *,
        created: t.VariadicTuple[
            m.Cli.AtomicFileState | m.Cli.AtomicDirectoryState
        ] = (),
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenJournalDirectory]]:
        """Register exact transaction trees after validating any prior authority.

        Returns:
            The resulting
                ``p.Result[t.VariadicTuple[m.Infra.CodegenJournalDirectory]]``.

        """
        result_type = r[tuple[m.Infra.CodegenJournalDirectory, ...]]
        for receipt in created:
            if not any(
                project.transaction_root is not None
                and receipt.path != project.transaction_root
                and receipt.path.is_relative_to(project.transaction_root)
                for project in files.transaction_participants(layout)
            ):
                return result_type.fail(
                    (
                        f"created staging receipt escapes "
                        f"transaction topology: {receipt.path}"
                    ),
                )
        registered: list[m.Infra.CodegenJournalDirectory] = []
        for directory in journal.directories:
            validated = cls._registered_directory(
                layout,
                journal,
                directory,
                created,
            )
            if validated.failure:
                return result_type.from_failure(validated)
            validated_value, _validated_present = validated.value
            registered.append(validated_value)
        return result_type.ok(tuple(registered))

    @classmethod
    def _registered_directory(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        directory: m.Infra.CodegenJournalDirectory,
        created: t.VariadicTuple[m.Cli.AtomicFileState | m.Cli.AtomicDirectoryState],
    ) -> p.Result[t.Pair[m.Infra.CodegenJournalDirectory, bool]]:
        """Register one temporary-tree manifest or pass its directory through.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenJournalDirectory,
            bool]]`` where the boolean marks registration (False keeps the
            directory unchanged in the journal).

        """
        result_type = r[t.Pair[m.Infra.CodegenJournalDirectory, bool]]
        project = next(
            item
            for item in files.transaction_participants(layout)
            if item.selector == directory.project
        )
        target = files.resolve_transaction(
            layout,
            directory.path,
            purpose="temporary tree manifest",
        )
        if target.failure:
            return result_type.from_failure(target)
        unmanaged = directory.disposition != "temporary" or (
            target.value != project.transaction_root
        )
        if unmanaged or (not target.value.exists() and not target.value.is_symlink()):
            return result_type.ok((directory, False))
        observed = cls._temporary_tree_manifest(layout, journal, directory, created)
        if observed.failure:
            return result_type.from_failure(observed)
        if observed.value is None:
            return result_type.ok((directory, False))
        validated: p.Result[m.Infra.CodegenJournalDirectory] = u.validate_value(
            m.Infra.CodegenJournalDirectory,
            {**directory.model_dump(), "manifest": observed.value},
        )
        if validated.failure:
            return result_type.fail_op(
                "validate temporary-tree manifest",
                validated.error,
            )
        return result_type.ok((validated.value, True))

    @classmethod
    def _temporary_tree_manifest(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        directory: m.Infra.CodegenJournalDirectory,
        created: t.VariadicTuple[m.Cli.AtomicFileState | m.Cli.AtomicDirectoryState],
    ) -> p.Result[m.Cli.AtomicPhysicalTreeManifest | None]:
        """Inventory a live temporary tree and validate it against its receipt.

        Returns:
            The resulting ``p.Result[m.Cli.AtomicPhysicalTreeManifest | None]``
            where None marks a manifest that did not change.

        """
        result_type = r[m.Cli.AtomicPhysicalTreeManifest | None]
        if directory.created is None:
            return result_type.fail(
                f"temporary tree has no created identity: {directory.path}",
            )
        manifest = directory.manifest
        if manifest is None:
            # First registration: the transaction just created this tree, so
            # its created receipt is the only authorization. Inventory the
            # live root and register that inventory as the manifest; the
            # authorized and observed manifests coincide on the first cycle.
            seeded = u.Cli.atomic_inventory_physical_tree(directory.created.path)
            if seeded.failure:
                return result_type.from_failure(seeded)
            manifest = seeded.value
        observed = cls._validated_tree_inventory(directory, manifest)
        if observed.failure:
            return result_type.from_failure(observed)
        transition = cls._validate_manifest_transition(
            layout,
            journal,
            manifest,
            observed.value,
            created=created,
        )
        if transition.failure:
            return result_type.from_failure(transition)
        return result_type.ok(observed.value)

    @classmethod
    def _validated_tree_inventory(
        cls,
        directory: m.Infra.CodegenJournalDirectory,
        manifest: m.Cli.AtomicPhysicalTreeManifest,
    ) -> p.Result[m.Cli.AtomicPhysicalTreeManifest]:
        """Inventory the live tree and prove it matches its created receipt.

        Returns:
            The resulting ``p.Result[m.Cli.AtomicPhysicalTreeManifest]``.

        """
        result_type = r[m.Cli.AtomicPhysicalTreeManifest]
        observed = u.Cli.atomic_inventory_physical_tree(manifest.root.path)
        if observed.failure:
            return result_type.from_failure(observed)
        physical = cls._manifest_root_matches_created(directory, observed.value)
        if physical.failure:
            return result_type.from_failure(physical)
        aliases = tuple(
            entry.path for entry in observed.value.entries if entry.kind == "symlink"
        )
        if aliases:
            return result_type.fail(
                "temporary tree contains aliases: "
                + ", ".join(path.as_posix() for path in aliases),
            )
        return result_type.ok(observed.value)

    @classmethod
    def authorized_cleanup_manifest(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        directory: m.Infra.CodegenJournalDirectory,
    ) -> p.Result[m.Cli.AtomicPhysicalTreeManifest]:
        """Observe a tree, prove it is a journal-authorized projection, then return it.

        Returns:
            The resulting ``p.Result[m.Cli.AtomicPhysicalTreeManifest]``.

        """
        result_type = r[m.Cli.AtomicPhysicalTreeManifest]
        if directory.manifest is None:
            return result_type.fail(
                f"temporary tree has no authorized manifest: {directory.path}",
            )
        root = directory.manifest.root.path
        if not root.exists() and not root.is_symlink():
            return result_type.ok(directory.manifest)
        observed = u.Cli.atomic_inventory_physical_tree(root)
        if observed.failure:
            return result_type.from_failure(observed)
        if any(entry.kind == "symlink" for entry in observed.value.entries):
            return result_type.fail(
                f"temporary tree contains an unregistered alias: {directory.path}",
            )
        transition = cls._validate_manifest_transition(
            layout,
            journal,
            directory.manifest,
            observed.value,
        )
        if transition.failure:
            return result_type.from_failure(transition)
        return result_type.ok(observed.value)

    @classmethod
    def _validate_manifest_transition(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        authorized: m.Cli.AtomicPhysicalTreeManifest,
        observed: m.Cli.AtomicPhysicalTreeManifest,
        *,
        created: t.VariadicTuple[
            m.Cli.AtomicFileState | m.Cli.AtomicDirectoryState
        ] = (),
    ) -> p.Result[bool]:
        """Accept only stable objects and explicitly journaled file transitions.

        An addition is admitted only as a registered transition: a created
        receipt, a directory above a journaled file, or a journaled file.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if not cls._same_directory_identity(authorized.root, observed.root):
            return r[bool].fail(
                f"temporary tree root identity changed: {authorized.root.path}",
            )
        expected = {entry.path: entry for entry in authorized.entries}
        current = {entry.path: entry for entry in observed.entries}
        file_specs = cls._journal_file_specs(layout, journal)
        if file_specs.failure:
            return r[bool].from_failure(file_specs)
        consumable = {
            path
            for path, (role, _entry) in file_specs.value.items()
            if role in {"desired", "rollback"}
        }
        expected_check = cls._verified_expected_entries(expected, current, consumable)
        if expected_check.failure:
            return expected_check
        created_by_path = {receipt.path: receipt for receipt in created}
        for directory in journal.directories:
            receipt = directory.created
            if (
                receipt is not None
                and receipt.path in current
                and receipt.path not in expected
            ):
                created_by_path[receipt.path] = receipt
        registered = cls._registered_staging_intents(
            layout,
            journal,
            expected,
            current,
        )
        if registered.failure:
            return r[bool].from_failure(registered)
        return cls._verified_tree_additions(
            authorized,
            expected,
            registered.value,
            file_specs.value,
            created_by_path,
        )

    @classmethod
    def _registered_staging_intents(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        expected: t.MappingKV[Path, m.Cli.AtomicPhysicalTreeEntry],
        current: t.MappingKV[Path, m.Cli.AtomicPhysicalTreeEntry],
    ) -> p.Result[t.MappingKV[Path, m.Cli.AtomicPhysicalTreeEntry]]:
        """Authenticate staging intentions before admitting tree additions.

        Returns:
            The observed entries excluding authenticated pending intentions.

        """
        result_type = r[t.MappingKV[Path, m.Cli.AtomicPhysicalTreeEntry]]
        for intent in journal.staging_intents:
            path = intent.before.path
            participant = next(
                (
                    item
                    for item in files.transaction_participants(layout)
                    if item.transaction_root is not None
                    and path != item.transaction_root
                    and path.is_relative_to(item.transaction_root)
                ),
                None,
            )
            if participant is None:
                return result_type.fail(
                    f"staging intention escapes transaction root: {path}",
                )
            entry = current.get(path)
            if entry is None or path in expected:
                continue
            if intent.created is not None:
                if entry != intent.created:
                    return result_type.fail(
                        f"finalized staging identity changed: {path}",
                    )
                current = {key: value for key, value in current.items() if key != path}
            elif (
                entry.kind,
                entry.sha256,
                entry.mode,
                entry.parent_device,
                entry.parent_inode,
                entry.link_count,
            ) != (
                "file",
                intent.sha256,
                intent.mode,
                intent.before.parent_device,
                intent.before.parent_inode,
                1,
            ):
                return result_type.fail(
                    f"pending staging identity differs from intention: {path}",
                )
            else:
                # These exact bytes were authorized before creation; recovery
                # must not pretend a finalized physical receipt already exists.
                current = {key: value for key, value in current.items() if key != path}
        return result_type.ok(current)

    @classmethod
    def _verified_expected_entries(
        cls,
        expected: t.MappingKV[Path, m.Cli.AtomicPhysicalTreeEntry],
        current: t.MappingKV[Path, m.Cli.AtomicPhysicalTreeEntry],
        consumable: AbstractSet[Path],
    ) -> p.Result[bool]:
        """Prove every authorized entry survived with a stable identity.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for path, entry in expected.items():
            current_entry = current.get(path)
            if current_entry is None:
                if entry.kind == "file" and path in consumable:
                    continue
                return r[bool].fail(
                    f"journaled temporary-tree entry is missing: {path}",
                )
            if entry.kind == "directory":
                if not cls._same_directory_identity(entry, current_entry):
                    return r[bool].fail(
                        f"temporary-tree directory identity changed: {path}",
                    )
            elif current_entry != entry:
                return r[bool].fail(f"temporary-tree file identity changed: {path}")
        return r[bool].ok(value=True)

    @classmethod
    def _verified_tree_additions(
        cls,
        authorized: m.Cli.AtomicPhysicalTreeManifest,
        expected: t.MappingKV[Path, m.Cli.AtomicPhysicalTreeEntry],
        current: t.MappingKV[Path, m.Cli.AtomicPhysicalTreeEntry],
        file_specs: t.MappingKV[
            Path,
            t.Pair[_JournalFileRole, m.Infra.CodegenJournalEntry],
        ],
        created_by_path: t.MappingKV[
            Path,
            m.Cli.AtomicFileState | m.Cli.AtomicDirectoryState,
        ],
    ) -> p.Result[bool]:
        """Authenticate every observed addition against receipts or the journal.

        An addition is admitted only as a registered transition: a created
        receipt, a directory above a journaled file, or a journaled file.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        additions = tuple(
            entry for path, entry in current.items() if path not in expected
        )
        authorized_files = set(file_specs)
        for path in created_by_path:
            if path.is_relative_to(authorized.root.path) and (
                path in expected or path not in current
            ):
                return r[bool].fail(
                    (
                        f"created temporary-tree entry is "
                        f"not a new present artifact: {path}"
                    ),
                )
        for entry in additions:
            receipt = created_by_path.get(entry.path)
            if receipt is not None:
                if not cls._matches_created_entry(entry, receipt):
                    return r[bool].fail(
                        f"created temporary-tree identity changed: {entry.path}",
                    )
                continue
            if entry.kind == "directory":
                if not any(entry.path in path.parents for path in authorized_files):
                    return r[bool].fail(
                        f"unregistered temporary-tree directory exists: {entry.path}",
                    )
                continue
            spec = file_specs.get(entry.path)
            if spec is None or not cls._matches_journal_file(entry, *spec):
                return r[bool].fail(
                    f"unregistered temporary-tree file exists: {entry.path}",
                )
        return r[bool].ok(value=True)

    @classmethod
    def _matches_created_entry(
        cls,
        entry: m.Cli.AtomicPhysicalTreeEntry,
        receipt: m.Cli.AtomicFileState | m.Cli.AtomicDirectoryState,
    ) -> bool:
        """Authenticate additions from invocation receipts, never their inventory.

        Returns:
            The resulting ``bool``.

        """
        if (
            entry.path,
            entry.parent_device,
            entry.parent_inode,
            entry.mode,
            entry.device,
            entry.inode,
            entry.file_attributes,
            entry.reparse_tag,
        ) != (
            receipt.path,
            receipt.parent_device,
            receipt.parent_inode,
            receipt.mode,
            receipt.device,
            receipt.inode,
            receipt.file_attributes,
            receipt.reparse_tag,
        ):
            return False
        if isinstance(receipt, m.Cli.AtomicFileState):
            return (
                entry.kind == "file"
                and receipt.content is not None
                and entry.sha256 == files.digest(receipt.content)
                and entry.link_count == receipt.link_count
            )
        return entry.kind == "directory" and receipt.exists is True

    @classmethod
    def _journal_file_specs(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[
        MutableMapping[Path, t.Pair[_JournalFileRole, m.Infra.CodegenJournalEntry]]
    ]:
        result_type = r[
            MutableMapping[Path, tuple[_JournalFileRole, m.Infra.CodegenJournalEntry]]
        ]
        specs: MutableMapping[
            Path,
            t.Pair[_JournalFileRole, m.Infra.CodegenJournalEntry],
        ] = {}
        for entry in journal.entries:
            selectors: t.VariadicTuple[t.Pair[_JournalFileRole, str | None]] = (
                ("desired", entry.desired_staging),
                ("backup", entry.original_backup),
                ("rollback", entry.rollback_staging),
            )
            for role, selector in selectors:
                if selector is None:
                    continue
                resolved = files.resolve_transaction(
                    layout,
                    selector,
                    purpose=f"{role} staging file",
                )
                if resolved.failure:
                    return result_type.from_failure(resolved)
                previous = specs.get(resolved.value)
                if previous is not None and previous != (role, entry):
                    return result_type.fail(
                        f"temporary file has multiple journal owners: {selector}",
                    )
                specs[resolved.value] = (role, entry)
        return result_type.ok(specs)

    @classmethod
    def _matches_journal_file(
        cls,
        observed: m.Cli.AtomicPhysicalTreeEntry,
        role: _JournalFileRole,
        entry: m.Infra.CodegenJournalEntry,
    ) -> bool:
        if observed.kind != "file":
            return False
        if role == "desired":
            expected = (
                entry.desired_sha256,
                entry.desired_mode,
                entry.desired_device,
                entry.desired_inode,
                entry.desired_link_count,
                entry.desired_file_attributes,
                entry.desired_reparse_tag,
            )
        elif role == "rollback":
            expected = (
                entry.rollback_sha256,
                entry.rollback_mode,
                entry.rollback_device,
                entry.rollback_inode,
                entry.rollback_link_count,
                entry.rollback_file_attributes,
                entry.rollback_reparse_tag,
            )
        else:
            expected = (
                entry.original_sha256,
                c.Infra.JOURNAL_MODE,
                observed.device,
                observed.inode,
                1,
                observed.file_attributes,
                observed.reparse_tag,
            )
        actual = (
            observed.sha256,
            observed.mode,
            observed.device,
            observed.inode,
            observed.link_count,
            observed.file_attributes,
            observed.reparse_tag,
        )
        return actual == expected

    @classmethod
    def _same_directory_identity(
        cls,
        expected: m.Cli.AtomicPhysicalTreeEntry,
        observed: m.Cli.AtomicPhysicalTreeEntry,
    ) -> bool:
        return (
            expected.path,
            expected.kind,
            expected.parent_device,
            expected.parent_inode,
            expected.parent_mount_id,
            expected.mode,
            expected.device,
            expected.inode,
            expected.mount_id,
            expected.uid,
            expected.gid,
            expected.file_attributes,
            expected.reparse_tag,
        ) == (
            observed.path,
            observed.kind,
            observed.parent_device,
            observed.parent_inode,
            observed.parent_mount_id,
            observed.mode,
            observed.device,
            observed.inode,
            observed.mount_id,
            observed.uid,
            observed.gid,
            observed.file_attributes,
            observed.reparse_tag,
        )

    @classmethod
    def _manifest_root_matches_created(
        cls,
        directory: m.Infra.CodegenJournalDirectory,
        manifest: m.Cli.AtomicPhysicalTreeManifest,
    ) -> p.Result[bool]:
        created = directory.created
        if created is None:
            return r[bool].fail(
                f"temporary tree has no created identity: {directory.path}",
            )
        root = manifest.root
        if (
            root.path,
            root.parent_device,
            root.parent_inode,
            root.mode,
            root.device,
            root.inode,
            root.file_attributes,
            root.reparse_tag,
        ) != (
            created.path,
            created.parent_device,
            created.parent_inode,
            created.mode,
            created.device,
            created.inode,
            created.file_attributes,
            created.reparse_tag,
        ):
            return r[bool].fail(
                f"temporary tree differs from created identity: {directory.path}",
            )
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraMiseArtifactsVerificationManifest"]
