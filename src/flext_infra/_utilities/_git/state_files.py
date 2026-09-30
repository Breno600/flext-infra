"""Guarded filesystem effects for the Git capture owner."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from flext_cli import u

from flext_infra import m, t

from .state_publication import FlextInfraUtilitiesGitStatePublicationMixin
from .worktree_io import FlextInfraUtilitiesGitWorktreeIO


class FlextInfraUtilitiesGitStateFilesMixin(
    FlextInfraUtilitiesGitStatePublicationMixin
):
    """Consume CLI physical-state primitives under the shared writer lease."""

    @staticmethod
    def _state_require_directory_scope(
        root: Path, path: Path, owned: t.SequenceOf[Path]
    ) -> None:
        manifest = u.Cli.atomic_inventory_physical_tree(root / path).unwrap()
        for entry in manifest.entries:
            relative = entry.path.relative_to(root)
            if entry.kind != "directory" and relative not in owned:
                msg = f"directory transition would remove unowned content: {relative}"
                raise ValueError(msg)

    @classmethod
    def _state_require_payload(
        cls,
        root: Path,
        before: m.Cli.AtomicFileState | m.Cli.AtomicSymlinkState,
        allowed: t.SequenceOf[m.Infra.GitWorktreeFileState | None],
    ) -> None:
        path = before.path.relative_to(root)
        if isinstance(before, m.Cli.AtomicFileState):
            content = before.content
            permissions = before.mode if before.mode is not None else 0
            mode = "100755" if permissions & stat.S_IXUSR else "100644"
        else:
            identity = before.identity
            if identity is None or before.target is None:
                msg = f"symlink disappeared before guarded effect: {path}"
                raise ValueError(msg)
            content = os.fsencode(before.target)
            permissions = identity.mode
            mode = "120000"
        if content is None and None in allowed:
            return
        if content is not None:
            with FlextInfraUtilitiesGitWorktreeIO.git_stdin(content) as stream:
                oid = cls._repo(root).git.hash_object("--stdin", istream=stream)
            observed = m.Infra.GitWorktreeFileState(
                path=path, mode=mode, permissions=permissions, oid=oid
            )
            if observed in allowed:
                return
        msg = f"owned file changed before guarded effect: {path}"
        raise ValueError(msg)

    @classmethod
    def _state_effect_file(
        cls,
        root: Path,
        path: Path,
        desired: m.Infra.GitWorktreeFileState | None,
        allowed: t.SequenceOf[m.Infra.GitWorktreeFileState | None],
    ) -> None:
        destination = root / path
        if destination.is_symlink():
            before_link = u.Cli.atomic_read_symlink_state(
                destination, required=True
            ).unwrap()
            cls._state_require_payload(root, before_link, allowed)
            if desired is not None and desired.mode == "120000":
                payload = cls._repo(root).odb.stream(bytes.fromhex(desired.oid)).read()
                u.Cli.atomic_write_symlink_guarded(
                    before_link, os.fsdecode(payload)
                ).unwrap()
                return
            u.Cli.atomic_delete_symlink_guarded(before_link).unwrap()
        else:
            before_file = u.Cli.atomic_read_binary_file_state(
                destination, required=False
            ).unwrap()
            cls._state_require_payload(root, before_file, allowed)
            if desired is not None and desired.mode != "120000":
                payload = cls._repo(root).odb.stream(bytes.fromhex(desired.oid)).read()
                u.Cli.atomic_write_binary_file_guarded(
                    before_file, payload, permission_mode=desired.permissions
                ).unwrap()
                return
            if before_file.content is not None:
                u.Cli.atomic_delete_binary_file_guarded(before_file).unwrap()
        if desired is not None:
            # A kind transition has a recorded, recoverable absent intermediate.
            if desired.mode == "120000":
                absent = u.Cli.atomic_read_symlink_state(
                    destination, required=False
                ).unwrap()
                if absent.target is not None:
                    msg = f"destination appeared during kind transition: {path}"
                    raise ValueError(msg)
                payload = cls._repo(root).odb.stream(bytes.fromhex(desired.oid)).read()
                u.Cli.atomic_write_symlink_guarded(
                    absent, os.fsdecode(payload)
                ).unwrap()
            else:
                cls._state_effect_file(root, path, desired, (None,))

    @staticmethod
    def _state_remove_empty_tree(path: Path) -> None:
        manifest = u.Cli.atomic_inventory_physical_tree(path).unwrap()
        if any(entry.kind != "directory" for entry in manifest.entries):
            msg = f"directory gained content before file replacement: {path}"
            raise ValueError(msg)
        u.Cli.atomic_cleanup_physical_tree_guarded(manifest).unwrap()


__all__: list[str] = ["FlextInfraUtilitiesGitStateFilesMixin"]
