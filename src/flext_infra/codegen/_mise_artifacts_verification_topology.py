"""Journal topology binding and committed-destination verification.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import m, t
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraMiseArtifactsVerificationTopology:
    """Bind journal selectors, directories, and entries to the locked layout."""

    @classmethod
    def journal_topology(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[bool]:
        """Bind every journal selector and physical identity to the locked layout.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        identifiers = cls._verified_topology_identifiers(layout, journal)
        if identifiers.failure:
            return identifiers
        by_selector = cls._verified_recorded_identities(layout, journal)
        if by_selector.failure:
            return r[bool].from_failure(by_selector)
        directory_targets = cls._resolved_directory_targets(layout, journal)
        if directory_targets.failure:
            return r[bool].from_failure(directory_targets)
        bindings = cls._verified_directory_bindings(
            journal,
            by_selector.value,
            directory_targets.value,
        )
        if bindings.failure:
            return bindings
        return cls._verified_entry_bindings(layout, journal, by_selector.value)

    @classmethod
    def _verified_topology_identifiers(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[bool]:
        """Bind the journal transaction id, scope identity, and inventories.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if layout.transaction_id != journal.transaction_id:
            return r[bool].fail("generation journal transaction id differs from layout")
        scope = files.physical_directory_identity(layout.scope_root)
        if scope.failure:
            return r[bool].from_failure(scope)
        if scope.value != (journal.scope_device, journal.scope_inode):
            return r[bool].fail("generation journal scope identity differs from layout")
        if tuple(project.selector for project in journal.projects) != tuple(
            project.selector for project in layout.projects
        ):
            return r[bool].fail(
                "generation journal project topology differs from layout",
            )
        if journal.file_participants != layout.file_participants:
            return r[bool].fail("generation file capabilities differ from the journal")
        return r[bool].ok(value=True)

    @classmethod
    def _resolved_directory_targets(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[t.MappingKV[Path, m.Infra.CodegenJournalDirectory]]:
        """Resolve every journaled directory onto its transaction path.

        Returns:
            The resulting ``p.Result[t.MappingKV[Path,
                m.Infra.CodegenJournalDirectory]]``.

        """
        directory_targets: MutableMapping[Path, m.Infra.CodegenJournalDirectory] = {}
        for directory in journal.directories:
            target = files.resolve_transaction(
                layout,
                directory.path,
                purpose="journaled generation directory",
            )
            if target.failure:
                failure = r[t.MappingKV[Path, m.Infra.CodegenJournalDirectory]]
                return failure.from_failure(target)
            directory_targets[target.value] = directory
        return r[t.MappingKV[Path, m.Infra.CodegenJournalDirectory]].ok(
            directory_targets,
        )

    @classmethod
    def _verified_recorded_identities(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[
        t.MappingKV[
            str,
            m.Infra.MiseToolchainProjectLayout | m.Infra.CodegenFileParticipant,
        ]
    ]:
        """Prove every recorded project and participant kept its physical identity.

        Returns:
            The resulting ``p.Result[t.MappingKV[str,
                m.Infra.MiseToolchainProjectLayout |
                m.Infra.CodegenFileParticipant]]`` keyed by selector.

        """
        result_type = r[
            t.MappingKV[
                str,
                m.Infra.MiseToolchainProjectLayout | m.Infra.CodegenFileParticipant,
            ]
        ]
        by_selector: t.MappingKV[
            str,
            m.Infra.MiseToolchainProjectLayout | m.Infra.CodegenFileParticipant,
        ] = {
            project.selector: project
            for project in files.transaction_participants(layout)
        }
        recorded_participants: t.VariadicTuple[
            m.Infra.CodegenJournalProject | m.Infra.CodegenFileParticipant
        ] = (*journal.projects, *journal.file_participants)
        for recorded in recorded_participants:
            project = by_selector[recorded.selector]
            identity = files.physical_directory_identity(project.root)
            if identity.failure:
                return result_type.from_failure(identity)
            if identity.value != (recorded.device, recorded.inode):
                return result_type.fail(
                    f"generation project identity changed: {recorded.selector}",
                )
        return result_type.ok(by_selector)

    @classmethod
    def _verified_directory_bindings(
        cls,
        journal: m.Infra.CodegenTransactionJournal,
        by_selector: t.MappingKV[
            str,
            m.Infra.MiseToolchainProjectLayout | m.Infra.CodegenFileParticipant,
        ],
        directory_targets: t.MappingKV[Path, m.Infra.CodegenJournalDirectory],
    ) -> p.Result[bool]:
        """Bind every journaled directory to its project and parent identity.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for directory in journal.directories:
            binding = cls._verified_directory_binding(
                by_selector,
                directory_targets,
                directory,
            )
            if binding.failure:
                return binding
        return r[bool].ok(value=True)

    @classmethod
    def _verified_directory_binding(
        cls,
        by_selector: t.MappingKV[
            str,
            m.Infra.MiseToolchainProjectLayout | m.Infra.CodegenFileParticipant,
        ],
        directory_targets: t.MappingKV[Path, m.Infra.CodegenJournalDirectory],
        directory: m.Infra.CodegenJournalDirectory,
    ) -> p.Result[bool]:
        """Bind one journaled directory to its project and parent identity.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        project = by_selector[directory.project]
        resolved_target = next(
            path
            for path, candidate in directory_targets.items()
            if candidate == directory
        )
        if resolved_target == project.root or not resolved_target.is_relative_to(
            project.root,
        ):
            return r[bool].fail(
                f"generation directory escapes its project: {directory.path}",
            )
        if directory.before is not None and directory.before.path != resolved_target:
            return r[bool].fail(
                f"generation directory preflight path differs: {directory.path}",
            )
        if directory.created is not None:
            parent_bound = cls._verified_created_parent(
                directory,
                directory_targets,
                resolved_target,
            )
            if parent_bound.failure:
                return parent_bound
        if directory.disposition == "temporary":
            transaction_root = project.transaction_root
            if (
                directory.phase != "transaction"
                or transaction_root is None
                or not (
                    transaction_root.is_relative_to(resolved_target)
                    or resolved_target.is_relative_to(transaction_root)
                )
            ):
                return r[bool].fail(
                    (f"temporary directory escapes transaction root: {directory.path}"),
                )
        return r[bool].ok(value=True)

    @staticmethod
    def _verified_created_parent(
        directory: m.Infra.CodegenJournalDirectory,
        directory_targets: t.MappingKV[Path, m.Infra.CodegenJournalDirectory],
        resolved_target: Path,
    ) -> p.Result[bool]:
        """Bind a created directory's parent to its journaled ancestry.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        created = directory.created
        if created is None:
            return r[bool].fail(f"directory has no created identity: {directory.path}")
        if created.path != resolved_target:
            return r[bool].fail(
                f"generation created directory path differs: {directory.path}",
            )
        parent = directory_targets.get(resolved_target.parent)
        expected_parent = (
            (directory.before.parent_device, directory.before.parent_inode)
            if directory.before is not None
            else (
                None
                if parent is None or parent.created is None
                else (parent.created.device, parent.created.inode)
            )
        )
        if (
            expected_parent is None
            or (created.parent_device, created.parent_inode) != expected_parent
        ):
            return r[bool].fail(
                (f"generation directory parent binding differs: {directory.path}"),
            )
        return r[bool].ok(value=True)

    @classmethod
    def _verified_entry_bindings(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        by_selector: t.MappingKV[
            str,
            m.Infra.MiseToolchainProjectLayout | m.Infra.CodegenFileParticipant,
        ],
    ) -> p.Result[bool]:
        """Bind every journal entry and its staging paths to the transaction root.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for entry in journal.entries:
            project = by_selector[entry.project]
            target = files.resolve_transaction(
                layout,
                entry.path,
                purpose="generated destination",
            )
            if target.failure:
                return r[bool].from_failure(target)
            if not target.value.is_relative_to(project.root):
                return r[bool].fail(
                    f"generation entry escapes its project: {entry.path}",
                )
            staging_paths: list[t.Pair[str, str]] = []
            if entry.original_backup is not None:
                staging_paths.append(("backup", entry.original_backup))
            if entry.desired_staging is not None:
                staging_paths.append(("desired", entry.desired_staging))
            if entry.rollback_staging is not None:
                staging_paths.append(("rollback", entry.rollback_staging))
            if staging_paths and project.transaction_root is None:
                return r[bool].fail(
                    "generation recovery layout has no transaction root",
                )
            staged = cls._verified_entry_staging(
                layout,
                entry,
                staging_paths,
                project.transaction_root,
            )
            if staged.failure:
                return staged
        return r[bool].ok(value=True)

    @classmethod
    def _verified_entry_staging(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        entry: m.Infra.CodegenJournalEntry,
        staging_paths: t.SequenceOf[t.Pair[str, str]],
        transaction_root: Path | None,
    ) -> p.Result[bool]:
        """Bind one entry's backup, desired, and rollback staging selectors.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for role, selector in staging_paths:
            staging = files.resolve_transaction(
                layout,
                selector,
                purpose=f"generation {role} staging",
            )
            if staging.failure:
                return r[bool].from_failure(staging)
            if transaction_root is None or not staging.value.is_relative_to(
                transaction_root,
            ):
                return r[bool].fail(
                    (
                        f"generation {role} staging escapes "
                        f"transaction root: {entry.path}"
                    ),
                )
        if entry.original_backup is not None:
            backup = files.resolve_transaction(
                layout,
                entry.original_backup,
                purpose="generation recovery backup",
            )
            if backup.failure:
                return r[bool].from_failure(backup)
            if transaction_root is None or backup.value.parent != (
                transaction_root / "recovery"
            ):
                return r[bool].fail(
                    f"generation backup escapes its recovery root: {entry.path}",
                )
        return r[bool].ok(value=True)

    @classmethod
    def journal_destinations_live(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[bool]:
        """Require every exact desired identity before irrevocable commit.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        topology = cls.journal_topology(layout, journal)
        if topology.failure:
            return topology
        for entry in journal.entries:
            path = files.resolve_transaction(
                layout,
                entry.path,
                purpose="published destination",
            )
            if path.failure:
                return r[bool].from_failure(path)
            observed = files.read_state(path.value, required=entry.desired_exists)
            if observed.failure:
                return r[bool].from_failure(observed)
            current = observed.value
            identity = (
                current.parent_device,
                current.parent_inode,
                None if current.content is None else files.digest(current.content),
                current.mode,
                current.device,
                current.inode,
                current.link_count,
                current.file_attributes,
                current.reparse_tag,
            )
            expected = (
                entry.desired_parent_device,
                entry.desired_parent_inode,
                entry.desired_sha256,
                entry.desired_mode,
                entry.desired_device,
                entry.desired_inode,
                entry.desired_link_count,
                entry.desired_file_attributes,
                entry.desired_reparse_tag,
            )
            if identity != expected:
                return r[bool].fail(
                    f"published generation identity changed: {entry.path}",
                )
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraMiseArtifactsVerificationTopology"]
