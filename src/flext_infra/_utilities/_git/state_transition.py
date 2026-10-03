"""Scoped transition preflight and recoverable file/directory ordering.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
from pathlib import Path

from flext_cli import u

from flext_infra import c, m, t
from flext_infra._utilities._git.state_files import (
    FlextInfraUtilitiesGitStateFilesMixin,
)


class FlextInfraUtilitiesGitStateTransitionMixin(FlextInfraUtilitiesGitStateFilesMixin):
    """Accept only captured, baseline, or planned kind-transition absence."""

    @staticmethod
    def _state_baseline_file(
        entry: m.Infra.GitWorktreeIndexEntry,
        original: m.Infra.GitWorktreeFileState | None = None,
    ) -> m.Infra.GitWorktreeFileState:
        permissions = (
            0
            if entry.mode == c.Infra.GIT_GITLINK_MODE_TEXT
            else 0o777
            if entry.mode == "120000"
            else int(entry.mode, 8) & 0o777
        )
        if (
            original is not None
            and original.mode in {"100644", "100755"}
            and entry.mode in {"100644", "100755"}
        ):
            permissions = original.permissions & ~0o111 | (int(entry.mode, 8) & 0o111)
        return m.Infra.GitWorktreeFileState(
            path=entry.path,
            mode=entry.mode,
            permissions=permissions,
            oid=entry.oid,
        )

    @classmethod
    def _state_baseline_at(
        cls,
        root: Path,
        entry: m.Infra.GitWorktreeIndexEntry,
        original: m.Infra.GitWorktreeFileState | None,
        *,
        cleanup: bool,
    ) -> m.Infra.GitWorktreeFileState:
        baseline = cls._state_baseline_file(entry, original)
        target = root / entry.path
        if (
            not cleanup
            and cls._state_obstruction(root, entry.path) is None
            and target.is_file()
            and not target.is_symlink()
        ):
            current = cls._state_file(root, entry.path)
            if current.mode == baseline.mode and current.oid == baseline.oid:
                return current
        return baseline

    @staticmethod
    def _state_obstruction(root: Path, path: Path) -> Path | None:
        return next(
            (
                parent
                for parent in path.parents
                if (root / parent).is_symlink()
                or ((root / parent).exists() and not (root / parent).is_dir())
            ),
            None,
        )

    @classmethod
    def _state_allowed_files(
        cls,
        original: m.Infra.GitWorktreeFileState | None,
        baseline: m.Infra.GitWorktreeFileState | None,
    ) -> t.VariadicTuple[m.Infra.GitWorktreeFileState | None]:
        allowed: list[m.Infra.GitWorktreeFileState | None] = [original, baseline]
        if (
            original is not None
            and baseline is not None
            and (original.mode == "120000") != (baseline.mode == "120000")
        ):
            allowed.append(None)
        return tuple(allowed)

    @classmethod
    def _state_preflight_transition(
        cls,
        snapshot: m.Infra.GitWorktreeStateSnapshot,
        root: Path,
        *,
        cleanup: bool,
    ) -> t.VariadicTuple[m.Infra.GitWorktreeIndexEntry]:
        actual = cls._state_snapshot(
            m.Infra.GitWorktreeStateRequest(repo_root=root, paths=snapshot.paths),
        )
        if actual.common_dir != snapshot.common_dir or actual.head != snapshot.head:
            msg = "state transition requires the captured repository and HEAD"
            raise ValueError(msg)
        baseline = cls._state_tree_entries(root, snapshot.head, snapshot.paths)
        base = {entry.path: entry for entry in baseline}
        indexed = {entry.path: entry for entry in snapshot.index_entries}
        current_index = {entry.path: entry for entry in actual.index_entries}
        expected = {file.path: file for file in snapshot.files}
        current_files = {file.path: file for file in actual.files}
        paths = (
            set(base)
            | set(indexed)
            | set(current_index)
            | set(expected)
            | set(current_files)
        )
        desired = base if cleanup else expected
        for entry in desired.values():
            if entry.mode == "120000":
                payload = cls._state_blob_payload(root, entry.oid)
                os.fsdecode(payload).encode(c.Cli.ENCODING_DEFAULT, errors="strict")
        for path in paths:
            current_entry = current_index.get(path)
            if current_entry != base.get(path) and current_entry != indexed.get(path):
                msg = f"owned index entry changed: {path}"
                raise ValueError(msg)
            original = expected.get(path)
            previous = (
                cls._state_baseline_at(root, base[path], original, cleanup=cleanup)
                if path in base
                else None
            )
            current = current_files.get(path)
            target = root / path
            obstruction = cls._state_obstruction(root, path)
            if obstruction is not None and (
                obstruction not in paths or (obstruction in desired and path in desired)
            ):
                msg = f"unowned ancestor obstructs state transition: {path}"
                raise ValueError(msg)
            if obstruction is None and current is None:
                if target.is_dir() and not target.is_symlink():
                    cls._state_require_directory_scope(root, path, tuple(paths))
                elif target.exists() or target.is_symlink():
                    current = cls._state_file(root, path)
            if current is not None and current.mode == c.Infra.GIT_GITLINK_MODE_TEXT:
                required = previous if cleanup else original
                if current != required:
                    msg = f"nested worktree requires independent reconciliation: {path}"
                    raise ValueError(msg)
            elif current not in cls._state_allowed_files(original, previous):
                msg = f"owned working file changed: {path}"
                raise ValueError(msg)
        return baseline

    @classmethod
    def _state_materialize(
        cls,
        snapshot: m.Infra.GitWorktreeStateSnapshot,
        root: Path,
        baseline: t.SequenceOf[m.Infra.GitWorktreeIndexEntry],
        *,
        cleanup: bool,
    ) -> None:
        expected = {file.path: file for file in snapshot.files}
        base = {
            entry.path: cls._state_baseline_at(
                root,
                entry,
                expected.get(entry.path),
                cleanup=cleanup,
            )
            for entry in baseline
        }
        paths = (
            set(base) | set(expected) | {entry.path for entry in snapshot.index_entries}
        )
        desired = base if cleanup else expected
        # Remove leaves first. Physical directories are retained until every
        # owned descendant is removed and an exact empty-tree proof succeeds.
        for path in sorted(
            paths - set(desired),
            key=lambda item: len(item.parts),
            reverse=True,
        ):
            destination = root / path
            if cls._state_obstruction(root, path) is None and (
                destination.is_symlink() or destination.is_file()
            ):
                allowed = cls._state_allowed_files(expected.get(path), base.get(path))
                cls._state_effect_file(root, path, None, allowed)
        for path, entry in sorted(desired.items(), key=lambda pair: len(pair[0].parts)):
            if entry.mode == c.Infra.GIT_GITLINK_MODE_TEXT:
                continue
            destination = root / path
            allowed = cls._state_allowed_files(expected.get(path), base.get(path))
            if destination.is_dir() and not destination.is_symlink():
                cls._state_remove_empty_tree(destination)
            plan = u.Cli.atomic_plan_directory_chain(destination.parent).unwrap()
            u.Cli.atomic_create_directory_chain_guarded(
                plan,
                permission_mode=0o755,
            ).unwrap()
            cls._state_effect_file(root, path, entry, allowed)
        # An index change made by another writer remains visible before the
        # one atomic index-info publication; no intermediate empty index.
        cls._state_preflight_transition(snapshot, root, cleanup=cleanup)
        cls._state_index_update(
            root,
            tuple(paths),
            baseline if cleanup else snapshot.index_entries,
        )


__all__: list[str] = ["FlextInfraUtilitiesGitStateTransitionMixin"]
