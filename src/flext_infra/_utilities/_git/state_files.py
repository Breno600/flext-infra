"""Guarded filesystem effects for the Git capture owner."""

from __future__ import annotations

import os
import shutil
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
    def _state_remove_symlink_target(target: Path) -> None:
        """Remove an existing file, directory, or symlink at ``target``.

        The CLI facet publishes no public removal primitive on this line
        (only its private helper exists upstream), so the guarded-effects
        owner keeps the physical removal inside its own lease boundary.
        """
        if not target.exists() and not target.is_symlink():
            return
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()

    @classmethod
    def _state_blob_payload(cls, root: Path, oid: str) -> bytes:
        """Read one blob through a reaped one-shot cat-file process.

        The shared odb batch stream races its final end-of-file read against
        subprocess teardown during garbage collection; a one-shot process
        fully reaped by ``communicate`` leaves no lingering handle behind.
        """
        proc = cls._repo(root).git.cat_file("blob", oid, as_process=True)
        payload, stderr = proc.communicate()
        if proc.returncode != 0:
            msg = f"cat-file failed for {oid}: {stderr!r}"
            raise ValueError(msg)
        return payload

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
        path: Path,
        observed: m.Infra.GitWorktreeObservedFile,
        allowed: t.SequenceOf[m.Infra.GitWorktreeFileState | None],
    ) -> None:
        """Hash the observed bytes and accept only an allowed captured state."""
        if observed.content is None and None in allowed:
            return
        if observed.content is not None:
            with FlextInfraUtilitiesGitWorktreeIO.git_stdin(observed.content) as stream:
                oid = cls._repo(root).git.hash_object("--stdin", istream=stream)
            captured = m.Infra.GitWorktreeFileState(
                path=path, mode=observed.mode, permissions=observed.permissions, oid=oid
            )
            if captured in allowed:
                return
        msg = f"owned file changed before guarded effect: {path}"
        raise ValueError(msg)

    @staticmethod
    def _state_write_symlink(destination: Path, target: str) -> None:
        """Atomically point ``destination`` at the raw ``target`` text."""
        staged = destination.parent / f".{destination.name}.symlink-{os.getpid()}"
        FlextInfraUtilitiesGitStateFilesMixin._state_remove_symlink_target(staged)
        staged.symlink_to(target)
        staged.replace(destination)

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
            try:
                raw_target = destination.readlink()
                link_mode = stat.S_IMODE(destination.lstat().st_mode)
            except OSError as exc:
                msg = f"symlink disappeared before guarded effect: {path}"
                raise ValueError(msg) from exc
            cls._state_require_payload(
                root,
                path,
                m.Infra.GitWorktreeObservedFile(
                    content=os.fsencode(raw_target),
                    mode="120000",
                    permissions=link_mode,
                ),
                allowed,
            )
            if desired is not None and desired.mode == "120000":
                payload = cls._state_blob_payload(root, desired.oid)
                cls._state_write_symlink(destination, os.fsdecode(payload))
                return
            cls._state_remove_symlink_target(destination)
        else:
            before_file = u.Cli.atomic_read_binary_file_state(
                destination, required=False
            ).unwrap()
            permissions = before_file.mode if before_file.mode is not None else 0
            cls._state_require_payload(
                root,
                path,
                m.Infra.GitWorktreeObservedFile(
                    content=before_file.content,
                    mode="100755" if permissions & stat.S_IXUSR else "100644",
                    permissions=permissions,
                ),
                allowed,
            )
            if desired is not None and desired.mode != "120000":
                payload = cls._state_blob_payload(root, desired.oid)
                u.Cli.atomic_write_binary_file_guarded(
                    before_file, payload, permission_mode=desired.permissions
                ).unwrap()
                return
            if before_file.content is not None:
                u.Cli.atomic_delete_binary_file_guarded(before_file).unwrap()
        if desired is not None:
            # A kind transition has a recorded, recoverable absent intermediate.
            if desired.mode == "120000":
                if destination.is_symlink() or destination.exists():
                    msg = f"destination appeared during kind transition: {path}"
                    raise ValueError(msg)
                payload = cls._state_blob_payload(root, desired.oid)
                cls._state_write_symlink(destination, os.fsdecode(payload))
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
