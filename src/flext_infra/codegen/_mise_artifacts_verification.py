"""Physical topology, source, destination, and real-consumer verification.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from flext_infra import c, m, r, u
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)

if TYPE_CHECKING:
    from flext_infra import p, t

type _JournalFileRole = Literal["desired", "backup", "rollback"]


class FlextInfraMiseArtifactsVerification:
    """Manifest, topology, and liveness verification for Mise transactions."""

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
            if (
                directory.disposition != "temporary"
                or target.value != project.transaction_root
            ):
                registered.append(directory)
                continue
            if directory.created is None:
                return result_type.fail(
                    f"temporary tree has no created identity: {directory.path}",
                )
            if not target.value.exists() and not target.value.is_symlink():
                registered.append(directory)
                continue
            observed = u.Cli.atomic_inventory_physical_tree(target.value)
            if observed.failure:
                return result_type.from_failure(observed)
            physical = cls._manifest_root_matches_created(directory, observed.value)
            if physical.failure:
                return result_type.from_failure(physical)
            aliases = tuple(
                entry.path
                for entry in observed.value.entries
                if entry.kind == "symlink"
            )
            if aliases:
                return result_type.fail(
                    "temporary tree contains aliases: "
                    + ", ".join(path.as_posix() for path in aliases),
                )
            if directory.manifest is not None:
                transition = cls._validate_manifest_transition(
                    layout,
                    journal,
                    directory.manifest,
                    observed.value,
                    created=created,
                )
                if transition.failure:
                    return result_type.from_failure(transition)
            validated: p.Result[m.Infra.CodegenJournalDirectory] = u.validate_value(
                m.Infra.CodegenJournalDirectory,
                {**directory.model_dump(), "manifest": observed.value},
            )
            if validated.failure:
                return result_type.fail_op(
                    "validate temporary-tree manifest",
                    validated.error,
                )
            registered.append(validated.value)
        return result_type.ok(tuple(registered))

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
    def journal_topology(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[bool]:
        """Bind every journal selector and physical identity to the locked layout.

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
        by_selector = {
            project.selector: project
            for project in files.transaction_participants(layout)
        }
        directory_targets: MutableMapping[Path, m.Infra.CodegenJournalDirectory] = {}
        for directory in journal.directories:
            target = files.resolve_transaction(
                layout,
                directory.path,
                purpose="journaled generation directory",
            )
            if target.failure:
                return r[bool].from_failure(target)
            directory_targets[target.value] = directory
        for recorded in (*journal.projects, *journal.file_participants):
            project = by_selector[recorded.selector]
            identity = files.physical_directory_identity(project.root)
            if identity.failure:
                return r[bool].from_failure(identity)
            if identity.value != (recorded.device, recorded.inode):
                return r[bool].fail(
                    f"generation project identity changed: {recorded.selector}",
                )
        for directory in journal.directories:
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
            if (
                directory.before is not None
                and directory.before.path != resolved_target
            ):
                return r[bool].fail(
                    f"generation directory preflight path differs: {directory.path}",
                )
            if directory.created is not None:
                if directory.created.path != resolved_target:
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
                    or (directory.created.parent_device, directory.created.parent_inode)
                    != expected_parent
                ):
                    return r[bool].fail(
                        (
                            f"generation directory parent "
                            f"binding differs: {directory.path}"
                        ),
                    )
            if directory.disposition == "temporary":
                transaction_root = project.transaction_root
                if (
                    directory.phase != "transaction"
                    or transaction_root is None
                    or not transaction_root.is_relative_to(resolved_target)
                ):
                    return r[bool].fail(
                        (
                            f"temporary directory escapes "
                            f"transaction root: {directory.path}"
                        ),
                    )
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
            transaction_root = project.transaction_root
            if staging_paths and transaction_root is None:
                return r[bool].fail(
                    "generation recovery layout has no transaction root",
                )
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

    @classmethod
    def states_current(
        cls,
        states: t.VariadicTuple[m.Cli.AtomicFileState],
        *,
        journal: m.Infra.CodegenTransactionJournal | None = None,
    ) -> p.Result[bool]:
        """Prove every full file state still equals its authenticated snapshot.

        This barrier is what makes the transaction atomic: it proves nothing
        moved between planning and publication. It compares the FULL state --
        content, mode and physical identity -- because a snapshot whose inode or
        device changed underneath the transaction is exactly the race the
        barrier exists to catch.

        It must never be softened to make a run pass. It briefly was: content
        was compared whitespace-normalised, mode drift was downgraded to a
        warning "logged but does not block the pipeline", and a literal
        `_models/config.py` was skipped as "expected to drift". That file
        carries no generation marker -- it is authored source and is not
        expected to drift at all; the drift being masked was the truncation
        churn of that same afternoon. A verifier that cannot fail is not a
        verifier, and a hardcoded path exemption in a fleet-wide generator hides
        the next real corruption just as effectively as it hid that one.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for original_expected in states:
            expected = original_expected
            if expected.parent_device is None and journal is not None:
                rebound = cls._bind_source_parent(expected, journal)
                if rebound.failure:
                    return r[bool].from_failure(rebound)
                rebound_expected = rebound.value
            else:
                rebound_expected = expected
            observed = files.read_state(
                rebound_expected.path,
                required=rebound_expected.content is not None,
            )
            if observed.failure:
                return r[bool].from_failure(observed)
            if observed.value != rebound_expected:
                return r[bool].fail(
                    f"generation authenticated state changed: {rebound_expected.path}",
                )
        return r[bool].ok(value=True)

    @classmethod
    def _bind_source_parent(
        cls,
        expected: m.Cli.AtomicFileState,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[m.Cli.AtomicFileState]:
        """Recognize only parent identities created under the durable absence witness.

        Returns:
            The resulting ``p.Result[m.Cli.AtomicFileState]``.

        """
        result = r[m.Cli.AtomicFileState]
        source = next(
            (item for item in journal.sources if item.path == expected.path),
            None,
        )
        if (
            source is None
            or source.absent_parent is None
            or expected.content is not None
        ):
            return result.fail(
                f"generation source has no absence witness: {expected.path}",
            )
        witness = source.absent_parent
        current = u.Cli.atomic_plan_directory_chain(witness.target)
        if current.failure:
            return result.from_failure(current)
        if current.value == witness:
            return result.ok(expected)
        created = {
            item.created.path: item.created
            for item in journal.directories
            if item.created is not None and item.disposition == "generated"
        }
        ancestry = list(witness.anchor_ancestry)
        for path in witness.directories:
            identity = created.get(path)
            if identity is None or identity.device is None or identity.inode is None:
                return result.fail(
                    f"generation source parent was not created by this journal: {path}",
                )
            if (identity.parent_device, identity.parent_inode) != ancestry[-1]:
                return result.fail(
                    (
                        f"generation source parent ancestry "
                        f"differs from its journal: {path}"
                    ),
                )
            ancestry.append((identity.device, identity.inode))
        observed = current.value
        if observed.directories or observed.anchor_ancestry != tuple(ancestry):
            return result.fail(
                f"generation source parent identity changed: {expected.path}",
            )
        return result.ok(
            expected.model_copy(
                update={
                    "parent_device": ancestry[-1][0],
                    "parent_inode": ancestry[-1][1],
                },
            ),
        )

    @classmethod
    def phase_analysis_live(
        cls,
        analysis: m.Infra.CodegenPhaseAnalysis,
    ) -> p.Result[bool]:
        """Prove one published phase from its authenticated analysis receipt.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        destination_paths = frozenset(file.path for file in analysis.files)
        u.Cli.info(
            f"phase={analysis.phase} verify inputs={len(analysis.inputs)} "
            f"destinations={len(analysis.files)}",
        )
        source_state = cls.states_current(
            tuple(
                state
                for state in analysis.inputs
                if state.path not in destination_paths
            ),
        )
        if source_state.failure:
            return source_state
        for plan in analysis.files:
            before = u.Infra.codegen_file_before_state(plan)
            if before.failure:
                return r[bool].from_failure(before)
            observed = files.read_state(
                plan.path,
                required=plan.desired_content is not None,
            )
            if observed.failure:
                return r[bool].from_failure(observed)
            current = observed.value
            if (
                current.content,
                current.mode,
                current.parent_device,
                current.parent_inode,
            ) != (
                plan.desired_content,
                plan.desired_mode,
                before.value.parent_device,
                before.value.parent_inode,
            ):
                return r[bool].fail(
                    f"published {analysis.phase} destination differs from receipt: "
                    f"{plan.path}",
                )
        return r[bool].ok(value=True)

    @classmethod
    def sources(cls, plan: m.Infra.MiseToolchainWorkspacePlan) -> p.Result[bool]:
        """Prove every Mise config source still equals its full snapshot.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for project in plan.projects:
            if project.config.before.content is None:
                # First publication: the config sources are themselves created
                # by this transaction, so their post-transaction bytes cannot
                # equal a pre-publication snapshot. Integrity for these is
                # owned by the publication-receipt verification.
                continue
            current = u.Infra.snapshot_config_sources(project.layout.root)
            if current.failure:
                return r[bool].from_failure(current)
            if current.value != project.config.sources:
                return r[bool].fail(f"Mise sources changed: {project.layout.selector}")
        return r[bool].ok(value=True)

    @classmethod
    def destinations(cls, plan: m.Infra.MiseToolchainWorkspacePlan) -> p.Result[bool]:
        """Prove all Mise destinations still equal the captured preflight snapshot.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for project in plan.projects:
            expected_states = (
                project.config.before,
                project.artifacts.unix_launcher,
                project.artifacts.windows_launcher,
                project.artifacts.version_pin,
            )
            current = cls.states_current(expected_states)
            if current.failure:
                return current
        return r[bool].ok(value=True)

    @classmethod
    def publications_live(
        cls,
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[bool]:
        """Prove live destinations have the exact staged inode or planned absence.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for publication in publications:
            observed = files.read_state(publication.before.path, required=False)
            if observed.failure:
                return r[bool].from_failure(observed)
            current = observed.value
            before = publication.before
            if (
                current.parent_device is None
                or current.parent_inode is None
                or before.parent_device is None
                or before.parent_inode is None
            ):
                return r[bool].fail(
                    (
                        f"generation destination parent "
                        f"identity is incomplete: {before.path}"
                    ),
                )
            replacement = publication.replacement
            if replacement is None:
                if (
                    observed.value.content is not None
                    or observed.value.parent_device != publication.before.parent_device
                    or observed.value.parent_inode != publication.before.parent_inode
                ):
                    return r[bool].fail(
                        "deleted generation destination or its parent changed: "
                        f"{publication.before.path}",
                    )
                continue
            if cls._file_identity(
                current,
                parent_device=current.parent_device,
                parent_inode=current.parent_inode,
            ) != cls._file_identity(
                replacement,
                parent_device=before.parent_device,
                parent_inode=before.parent_inode,
            ):
                return r[bool].fail(
                    (
                        f"live generation destination differs "
                        f"from staged identity: {current.path}"
                    ),
                )
        return r[bool].ok(value=True)

    @classmethod
    def live(
        cls,
        owner: p.Infra.MiseArtifactsOwner,
        plan: m.Infra.MiseToolchainWorkspacePlan,
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile] | None = None,
    ) -> p.Result[bool]:
        """Exercise every real Mise consumer while guarding sources and live bytes.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        source_before = cls.sources(plan)
        if source_before.failure:
            return source_before
        replacements: MutableMapping[Path, t.Pair[bytes, int | None]] = {}
        for publication in publications or ():
            replacement = publication.replacement
            if replacement is None or replacement.content is None:
                return r[bool].fail(
                    f"Mise replacement is absent: {publication.before.path}",
                )
            replacements[publication.before.path] = (
                replacement.content,
                replacement.mode,
            )
        artifact_before = cls._artifact_snapshot(plan, replacements)
        if artifact_before.failure:
            return r[bool].from_failure(artifact_before)
        for project in plan.projects:
            validated = owner.validate_artifacts(
                project.layout.root,
                plan.layout.scope_root,
            )
            if validated.failure:
                return r[bool].from_failure(validated)
        artifact_after = cls._artifact_snapshot(plan, replacements)
        if artifact_after.failure:
            return r[bool].from_failure(artifact_after)
        if artifact_after.value != artifact_before.value:
            return r[bool].fail("published Mise artifacts changed during validation")
        source_after = cls.sources(plan)
        if source_after.failure:
            return source_after
        return r[bool].ok(value=True)

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
        additions = tuple(
            entry for path, entry in current.items() if path not in expected
        )
        authorized_files = set(file_specs.value)
        created_by_path = {receipt.path: receipt for receipt in created}
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
            spec = file_specs.value.get(entry.path)
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

    @classmethod
    def _artifact_snapshot(
        cls,
        plan: m.Infra.MiseToolchainWorkspacePlan,
        replacements: MutableMapping[Path, t.Pair[bytes, int | None]],
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicFileState]]:
        states: list[m.Cli.AtomicFileState] = []
        for project in plan.projects:
            artifacts = (
                project.config.before,
                project.artifacts.unix_launcher,
                project.artifacts.windows_launcher,
                project.artifacts.version_pin,
            )
            for expected, (_name, required_mode) in zip(
                artifacts,
                c.Infra.PUBLICATION_SPECS,
                strict=True,
            ):
                current = files.read_state(expected.path, required=False)
                if current.failure or current.value.content is None:
                    repair = (
                        "make gen" if expected is project.config.before else "make upg"
                    )
                    return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                        f"published Mise artifact is absent: {expected.path}; "
                        f"run {repair}",
                    )
                if current.value.mode is None:
                    return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                        f"published Mise artifact mode is unreadable: {expected.path}",
                    )
                expected_state = replacements.get(
                    expected.path,
                    (expected.content, expected.mode),
                )
                if (current.value.content, current.value.mode) != expected_state:
                    return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                        f"published Mise artifact differs from plan: {expected.path}",
                    )
                if current.value.mode != required_mode:
                    return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                        "published Mise artifact mode is noncanonical:"
                        f" {expected.path}"
                        f" (observed {oct(current.value.mode)},"
                        f" canonical {oct(required_mode)})",
                    )
                states.append(current.value)
        return r[tuple[m.Cli.AtomicFileState, ...]].ok(tuple(states))

    @classmethod
    def _file_identity(
        cls,
        value: m.Cli.AtomicFileState,
        *,
        parent_device: int,
        parent_inode: int,
    ) -> tuple[
        int,
        int,
        bytes | None,
        int | None,
        int | None,
        int | None,
        int | None,
        int | None,
        int | None,
    ]:
        """Return every physical and byte field except the intentionally moved path.

        Returns:
            Every physical and byte field except the intentionally moved path.

        """
        return (
            parent_device,
            parent_inode,
            value.content,
            value.mode,
            value.device,
            value.inode,
            value.link_count,
            value.file_attributes,
            value.reparse_tag,
        )


__all__: list[str] = ["FlextInfraMiseArtifactsVerification"]
