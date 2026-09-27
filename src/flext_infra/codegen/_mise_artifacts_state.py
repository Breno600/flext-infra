"""Persistent coordination-state lifecycle for Mise transactions."""

from __future__ import annotations

import os
import stat
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from flext_core import r
from flext_infra import c, m, u

from ._mise_artifacts_files import FlextInfraMiseArtifactsFiles as files
from ._mise_artifacts_verification import FlextInfraMiseArtifactsVerification as verify

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraMiseArtifactsState:
    """Journaled directory state for Mise artifact transactions."""

    @classmethod
    def _hosting_device(cls, path: Path) -> int:
        """Return the filesystem device that will host ``path``.

        The check below proves every destination shares one device with the
        project root, because the transaction publishes by rename and a rename
        cannot cross filesystems. A destination directory need not exist yet --
        a freshly scaffolded project has no ``external/bin`` until this
        transaction creates it -- and `lstat` on the absent directory raised
        `FileNotFoundError`, failing generation for every new project. What will
        host it is its nearest existing ancestor, which is what the rename
        actually has to satisfy.
        """
        for candidate in (path, *path.parents):
            if candidate.exists():
                return candidate.lstat().st_dev
        msg = f"no existing ancestor hosts the destination: {path}"
        raise FileNotFoundError(msg)

    @classmethod
    def _project_depth(
        cls, item: m.Infra.MiseToolchainProjectLayout | m.Infra.CodegenFileParticipant
    ) -> int:
        """Order the narrowest project owner before its ancestors."""
        return -len(item.root.parts)

    @classmethod
    def _directory_cleanup_order(
        cls, item: m.Infra.CodegenJournalDirectory
    ) -> t.Pair[int, str]:
        """Order journaled directory cleanup from descendants to ancestors."""
        return cls._relative_order(item.path)

    @classmethod
    def plan_transaction_directories(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        *,
        destinations: t.VariadicTuple[Path] = (),
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenJournalDirectory]]:
        """Prove every transaction path absent before journal publication."""
        roots: list[Path] = []
        for project in layout.projects:
            transaction_root = project.transaction_root
            if transaction_root is None:
                return r[tuple[m.Infra.CodegenJournalDirectory, ...]].fail(
                    "Mise mutating layout has no transaction root"
                )
            try:
                destination_devices = {
                    cls._hosting_device(artifact.parent)
                    for artifact in (
                        project.artifacts.config,
                        project.artifacts.unix_launcher,
                        project.artifacts.windows_launcher,
                    )
                }
                project_device = cls._hosting_device(project.root)
            except OSError as exc:
                return r[tuple[m.Infra.CodegenJournalDirectory, ...]].fail_op(
                    "inspect Mise staging filesystem", exc
                )
            if destination_devices != {project_device}:
                return r[tuple[m.Infra.CodegenJournalDirectory, ...]].fail(
                    f"Mise state is not on destination filesystem: {project.selector}"
                )
            roots.append(transaction_root)
        roots.extend(
            participant.transaction_root for participant in layout.file_participants
        )
        temporary = cls.plan_directories(
            layout, phase="transaction", requested=tuple(roots), disposition="temporary"
        )
        if temporary.failure:
            return temporary
        parents = tuple(
            dict.fromkeys(
                artifact.parent
                for project in layout.projects
                for artifact in (
                    project.artifacts.config,
                    project.artifacts.unix_launcher,
                    project.artifacts.windows_launcher,
                )
                if artifact.parent != project.root
            )
        )
        project_roots = {item.root for item in files.transaction_participants(layout)}
        parents = tuple(
            dict.fromkeys((
                *parents,
                *(
                    path.parent
                    for path in destinations
                    if path.parent not in project_roots
                ),
            ))
        )
        generated = cls.plan_directories(
            layout, phase="mise", requested=parents, disposition="generated"
        )
        if generated.failure:
            return generated
        return r[tuple[m.Infra.CodegenJournalDirectory, ...]].ok((
            *temporary.value,
            *generated.value,
        ))

    @classmethod
    def bind_created_parents(
        cls,
        directories: t.VariadicTuple[m.Infra.CodegenJournalDirectory],
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenStagedFile]]:
        """Bind absent destinations only to parents created by this journal."""
        result_type = r[tuple[m.Infra.CodegenStagedFile, ...]]
        bound: list[m.Infra.CodegenStagedFile] = []
        for publication in publications:
            before = publication.before
            parent = next(
                (
                    entry.created
                    for entry in directories
                    if entry.created is not None
                    and entry.created.path == before.path.parent
                    and entry.disposition == "generated"
                ),
                None,
            )
            if before.parent_device is not None and before.parent_inode is not None:
                if parent is not None and (
                    before.parent_device,
                    before.parent_inode,
                ) != (parent.device, parent.inode):
                    return result_type.fail(
                        f"generation destination parent differs from journal: {before.path}"
                    )
                bound.append(publication)
                continue
            if (
                before.content is not None
                or parent is None
                or parent.device is None
                or parent.inode is None
            ):
                return result_type.fail(
                    f"generation destination has no created parent authority: {before.path}"
                )
            expected = m.Cli.AtomicFileState.model_validate({
                **before.model_dump(),
                "parent_device": parent.device,
                "parent_inode": parent.inode,
            })
            observed = files.read_state(before.path, required=False)
            if observed.failure:
                return result_type.from_failure(observed)
            if observed.value != expected:
                return result_type.fail(
                    f"generation destination changed after parent creation: {before.path}"
                )
            bound.append(
                m.Infra.CodegenStagedFile.model_validate({
                    **publication.model_dump(),
                    "before": expected,
                })
            )
        return result_type.ok(tuple(bound))

    @classmethod
    def plan_directories(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        *,
        phase: str,
        requested: t.VariadicTuple[Path],
        disposition: Literal["temporary", "generated"],
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenJournalDirectory]]:
        """Return unique missing paths after descriptor-authenticated preflight."""
        result_type = r[tuple[m.Infra.CodegenJournalDirectory, ...]]
        if len(set(requested)) != len(requested):
            return result_type.fail(f"duplicate {phase} directory request")
        projects = tuple(
            sorted(files.transaction_participants(layout), key=cls._project_depth)
        )
        planned: MutableMapping[Path, m.Infra.CodegenJournalDirectory] = {}
        for target in requested:
            path = target.expanduser().absolute()
            project = next(
                (item for item in projects if path.is_relative_to(item.root)), None
            )
            if project is None or path == project.root:
                return result_type.fail(
                    f"{phase} directory escapes its project: {path}"
                )
            chain = u.Cli.atomic_plan_directory_chain(path)
            if chain.failure:
                return result_type.from_failure(chain)
            for directory in chain.value.directories:
                owner = next(
                    (item for item in projects if directory.is_relative_to(item.root)),
                    None,
                )
                if owner is None or directory == owner.root:
                    return result_type.fail(
                        f"{phase} directory has no project owner: {directory}"
                    )
                relative = files.transaction_relative(layout, directory)
                if relative.failure:
                    return result_type.from_failure(relative)
                before: m.Cli.AtomicDirectoryState | None = None
                if directory.parent == chain.value.anchor_path:
                    observed = u.Cli.atomic_read_empty_directory_state(
                        directory, required=False
                    )
                    if observed.failure:
                        return result_type.from_failure(observed)
                    if observed.value.exists or (
                        observed.value.parent_device,
                        observed.value.parent_inode,
                    ) != (chain.value.anchor_device, chain.value.anchor_inode):
                        return result_type.fail(
                            f"{phase} directory anchor changed during planning: {directory}"
                        )
                    before = observed.value
                entry = m.Infra.CodegenJournalDirectory(
                    phase=phase,
                    project=owner.selector,
                    path=relative.value,
                    disposition=disposition,
                    before=before,
                )
                previous = planned.get(directory)
                if previous is not None and (
                    previous.phase,
                    previous.project,
                    previous.disposition,
                ) != (entry.phase, entry.project, entry.disposition):
                    return result_type.fail(
                        f"generation directory has conflicting owners: {directory}"
                    )
                if previous is None or (previous.before is None and before is not None):
                    planned[directory] = entry
        ordered = tuple(planned[path] for path in sorted(planned, key=cls._path_order))
        return result_type.ok(ordered)

    @classmethod
    def create_journaled_directory(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        directories: t.VariadicTuple[m.Infra.CodegenJournalDirectory],
        entry: m.Infra.CodegenJournalDirectory,
    ) -> p.Result[m.Infra.CodegenJournalDirectory]:
        """Create one durable intent and return its exact physical identity."""
        result_type = r[m.Infra.CodegenJournalDirectory]
        if entry.created is not None or entry not in directories:
            return result_type.fail(f"invalid directory creation cursor: {entry.path}")
        target = files.resolve_transaction(
            layout, entry.path, purpose="journaled generation directory"
        )
        if target.failure:
            return result_type.from_failure(target)
        project = next(
            (
                item
                for item in files.transaction_participants(layout)
                if item.selector == entry.project
            ),
            None,
        )
        if project is None or not target.value.is_relative_to(project.root):
            return result_type.fail(
                f"journaled directory differs from its project: {entry.path}"
            )
        before = entry.before
        if before is None:
            parent_entry = next(
                (
                    candidate
                    for candidate in directories
                    if candidate.created is not None
                    and candidate.created.path == target.value.parent
                ),
                None,
            )
            if (
                parent_entry is None
                or parent_entry.created is None
                or parent_entry.created.device is None
                or parent_entry.created.inode is None
            ):
                return result_type.fail(
                    f"journaled directory parent has no durable identity: {entry.path}"
                )
            observed = u.Cli.atomic_read_empty_directory_state(
                target.value, required=False
            )
            if observed.failure:
                return result_type.from_failure(observed)
            before = observed.value
            if before.exists or (before.parent_device, before.parent_inode) != (
                parent_entry.created.device,
                parent_entry.created.inode,
            ):
                return result_type.fail(
                    f"journaled directory parent changed before creation: {entry.path}"
                )
        elif before.path != target.value:
            return result_type.fail(
                f"journaled absent state belongs to another path: {entry.path}"
            )
        created = u.Cli.atomic_create_empty_directory_guarded(
            before, permission_mode=0o700 if entry.disposition == "temporary" else 0o755
        )
        if created.failure:
            return result_type.from_failure(created)
        validated: p.Result[m.Infra.CodegenJournalDirectory] = u.validate_value(
            m.Infra.CodegenJournalDirectory,
            {**entry.model_dump(), "before": before, "created": created.value},
        )
        if validated.failure:
            rolled_back = u.Cli.atomic_delete_empty_directory_guarded(created.value)
            if rolled_back.failure:
                return result_type.fail(
                    f"validate created directory identity failed: {validated.error}; "
                    f"compensation failed: {rolled_back.error}"
                )
            return result_type.fail_op(
                "validate created directory identity", validated.error
            )
        return result_type.ok(validated.value)

    @classmethod
    def compensate_created_directory(
        cls, entry: m.Infra.CodegenJournalDirectory
    ) -> p.Result[bool]:
        """Remove only the exact empty directory returned by this invocation."""
        if entry.created is None:
            return r[bool].fail(f"directory has no created identity: {entry.path}")
        return u.Cli.atomic_delete_empty_directory_guarded(entry.created)

    @classmethod
    def journal_state(
        cls, layout: m.Infra.MiseToolchainWorkspaceLayout
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicFileState]]:
        """Read the typed Git-owned journal without creating filesystem state."""
        result_type = r[tuple[m.Cli.AtomicFileState, ...]]
        snapshot = files.read_state(layout.journal_path, required=False)
        if snapshot.failure:
            return result_type.from_failure(snapshot)
        return result_type.ok((snapshot.value,))

    @classmethod
    def journal_snapshot(
        cls, states: t.VariadicTuple[m.Cli.AtomicFileState]
    ) -> m.Cli.AtomicFileState | None:
        """Return the optional journal snapshot from its non-null result payload."""
        return states[0] if states else None

    @classmethod
    def transaction_residue(
        cls, layout: m.Infra.MiseToolchainWorkspaceLayout
    ) -> t.VariadicTuple[Path]:
        """Return every transaction-prefixed child or unsafe state-root alias."""
        residue: list[Path] = []
        for project in files.transaction_participants(layout):
            state_root = project.root / c.Infra.MISE_ARTIFACTS_STATE_DIRECTORY
            if not state_root.exists() and not state_root.is_symlink():
                continue
            if state_root.is_symlink():
                residue.append(state_root)
                continue
            try:
                root_state = state_root.lstat()
                if not stat.S_ISDIR(root_state.st_mode) or cls._is_reparse(root_state):
                    residue.append(state_root)
                    continue
                children = tuple(state_root.iterdir())
            except OSError:
                residue.append(state_root)
                continue
            residue.extend(
                child
                for child in children
                if child.name.startswith(c.Infra.TRANSACTION_DIR_PREFIX)
            )
        return tuple(sorted(set(residue)))

    @classmethod
    def cleanup_journaled_directories(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        *,
        include_generated: bool,
    ) -> p.Result[bool]:
        """Remove authenticated temporary trees and authorized empty directories."""
        topology = verify.journal_topology(layout, journal)
        if topology.failure:
            return topology
        validated = cls.validate_transaction_roots(layout, journal)
        if validated.failure:
            return validated
        removed_temporary_roots: set[str] = set()
        for project in files.transaction_participants(layout):
            transaction_root = project.transaction_root
            if transaction_root is None:
                return r[bool].fail("Mise recovery layout has no transaction root")
            if not transaction_root.exists() and not transaction_root.is_symlink():
                continue
            relative = files.transaction_relative(layout, transaction_root)
            if relative.failure:
                return r[bool].from_failure(relative)
            entry = next(
                (item for item in journal.directories if item.path == relative.value),
                None,
            )
            if entry is None or entry.created is None:
                return r[bool].fail(
                    f"transaction root has no durable physical identity: {relative.value}"
                )
            if entry.manifest is None:
                # A created directory receipt owns only that empty directory,
                # never descendants discovered after an interrupted stage.
                if cls._hosts_lease_lock(layout, transaction_root):
                    removed_temporary_roots.add(entry.path)
                    continue
                removed = u.Cli.atomic_delete_empty_directory_guarded(entry.created)
            else:
                observed = verify.authorized_cleanup_manifest(layout, journal, entry)
                if observed.failure:
                    return r[bool].from_failure(observed)
                removed = u.Cli.atomic_cleanup_physical_tree_guarded(observed.value)
            if removed.failure:
                return removed
            removed_temporary_roots.add(entry.path)
        removable = tuple(
            directory
            for directory in journal.directories
            if (
                directory.path not in removed_temporary_roots
                and (directory.disposition == "temporary" or include_generated)
            )
        )
        for entry in sorted(removable, key=cls._directory_cleanup_order, reverse=True):
            target = files.resolve_transaction(
                layout, entry.path, purpose="journaled cleanup directory"
            )
            if target.failure:
                return r[bool].from_failure(target)
            if not target.value.exists() and not target.value.is_symlink():
                continue
            if entry.created is None:
                return r[bool].fail(
                    f"journaled directory exists without durable identity: {entry.path}"
                )
            if cls._hosts_lease_lock(layout, target.value):
                # The journal lease lock file persists by identity across
                # transactions, so its home directory is durable state the
                # cleanup must leave in place rather than delete empty.
                continue
            removed = u.Cli.atomic_delete_empty_directory_guarded(entry.created)
            if removed.failure:
                # A journaled generated directory may keep journaled residents
                # whose recovery classified noop (unrecognized state the
                # generation owns and rewrites). Only residents the journal
                # itself authenticated preserve the directory; anything else
                # inside is foreign state and the cleanup still fails closed.
                residents = (
                    tuple(target.value.iterdir()) if target.value.is_dir() else ()
                )
                journaled = {j.path for j in journal.entries}
                preserved = set(removed_temporary_roots) | {
                    d.path for d in removable if d.path != entry.path
                }

                def _journaled_resident(
                    resident: Path, journaled: set[str], preserved: set[str]
                ) -> p.Result[bool]:
                    selector = files.transaction_relative(layout, resident)
                    if selector.failure:
                        return r[bool].from_failure(selector)
                    relative = selector.value
                    if relative in journaled or relative in preserved:
                        return r[bool].ok(True)
                    # An ancestor is preservable when everything between it
                    # and a preserved descendant is itself journaled: the
                    # descendant's own guard already authenticated its subtree.
                    prefix = relative + "/"
                    return r[bool].ok(
                        any(candidate.startswith(prefix) for candidate in preserved)
                    )

                authenticated = r[bool].ok(True)
                for resident in residents:
                    authenticated = _journaled_resident(resident, journaled, preserved)
                    if authenticated.failure:
                        break
                if authenticated.failure:
                    return r[bool].from_failure(authenticated)
                if residents and authenticated.value:
                    continue
                return r[bool].from_failure(removed)
        return r[bool].ok(True)

    @staticmethod
    def _hosts_lease_lock(
        layout: m.Infra.MiseToolchainWorkspaceLayout, directory: Path
    ) -> bool:
        """Keep the journal lease lock's file identity across transactions."""
        lock_path = layout.journal_path.with_name(f"{layout.journal_path.name}.lock")
        return lock_path.is_relative_to(directory)

    @classmethod
    def validate_transaction_roots(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[bool]:
        """Authenticate the sole journal-derived staging root in every project."""
        expected = {
            project.transaction_root
            for project in files.transaction_participants(layout)
            if project.transaction_root is not None
        }
        unexpected = sorted(set(cls.transaction_residue(layout)) - expected)
        if unexpected:
            return r[bool].fail(
                f"foreign generation transaction residue exists: {unexpected[0]}"
            )
        for project in files.transaction_participants(layout):
            transaction_root = project.transaction_root
            if transaction_root is None:
                return r[bool].fail("Mise recovery layout has no transaction root")
            transaction = cls._validate_transaction_root(transaction_root)
            if transaction.failure:
                return r[bool].from_failure(transaction)
            if transaction.value is False:
                continue
            relative = files.transaction_relative(layout, transaction_root)
            if relative.failure:
                return r[bool].from_failure(relative)
            recorded = next(
                (item for item in journal.directories if item.path == relative.value),
                None,
            )
            if (
                recorded is None
                or recorded.created is None
                or (recorded.created.device, recorded.created.inode)
                != transaction.value
            ):
                return r[bool].fail(
                    f"Mise transaction root identity is not journaled: {relative.value}"
                )
            if recorded.manifest is None:
                empty = u.Cli.atomic_read_empty_directory_state(
                    transaction_root, required=True
                )
                if empty.failure:
                    return r[bool].from_failure(empty)
                if empty.value != recorded.created:
                    return r[bool].fail(
                        f"unmanifested transaction root identity changed: {relative.value}"
                    )
            else:
                authorized = verify.authorized_cleanup_manifest(
                    layout, journal, recorded
                )
                if authorized.failure:
                    return r[bool].from_failure(authorized)
        # Foreign residents inside recorded temporary trees never block the
        # restore itself. The journal receipt authenticates the destinations;
        # staging residue revokes only the cleanup, which still fails closed
        # after the rollback (guarded deletion refuses unmanifested or
        # non-empty trees), so a mixed recovery retains the journal and the
        # foreign bytes instead of stranding published destinations behind
        # them. Pre-restore authentication of every recorded tree and resident
        # aborted the rollback before it started, which replaced the tested
        # mixed outcome with a lost publication.
        return r[bool].ok(True)

    @classmethod
    def _validate_transaction_root(
        cls, target: Path
    ) -> p.Result[t.Pair[int, int] | bool]:
        if not target.exists() and not target.is_symlink():
            return r[tuple[int, int] | bool].ok(False)
        identifier = target.name.removeprefix(c.Infra.TRANSACTION_DIR_PREFIX)
        if (
            not target.name.startswith(c.Infra.TRANSACTION_DIR_PREFIX)
            or len(identifier) != c.Infra.TRANSACTION_ID_LENGTH
            or any(character not in "0123456789abcdef" for character in identifier)
            or target.is_symlink()
        ):
            return r[tuple[int, int] | bool].fail(
                f"refusing invalid Mise transaction target: {target}"
            )
        try:
            state = target.lstat()
        except OSError as exc:
            return r[tuple[int, int] | bool].fail_op(
                "inspect Mise transaction target", exc
            )
        if not stat.S_ISDIR(state.st_mode) or cls._is_reparse(state):
            return r[tuple[int, int] | bool].fail(
                f"Mise transaction target is not physical: {target}"
            )
        return r[tuple[int, int] | bool].ok((state.st_dev, state.st_ino))

    @classmethod
    def _path_order(cls, path: Path) -> t.Pair[int, str]:
        return len(path.parts), path.as_posix()

    @classmethod
    def _relative_order(cls, path: str) -> t.Pair[int, str]:
        relative = Path(path)
        return len(relative.parts), path

    @classmethod
    def _is_reparse(cls, state: os.stat_result) -> bool:
        attributes = getattr(state, "st_file_attributes", 0)
        marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        return bool(attributes & marker)


__all__: list[str] = ["FlextInfraMiseArtifactsState"]
