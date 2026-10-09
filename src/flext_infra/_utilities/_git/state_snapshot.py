"""Read scoped index and exact working bytes without changing the source.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import TYPE_CHECKING

from git import GitCommandError

from flext_infra import c, m, r, t
from flext_infra._utilities._git.repo import FlextInfraUtilitiesGitRepo
from flext_infra._utilities._git.worktree_io import FlextInfraUtilitiesGitWorktreeIO

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesGitStateSnapshotMixin(FlextInfraUtilitiesGitRepo):
    """Canonical scoped state discovery for capture, verification and cleanup."""

    @staticmethod
    def _state_pathspecs(paths: t.SequenceOf[Path]) -> t.VariadicTuple[str]:
        if not paths or any(
            path.is_absolute() or ".." in path.parts or ".git" in path.parts
            for path in paths
        ):
            msg = "capture requires nonempty literal repository-relative paths"
            raise ValueError(msg)
        return tuple(f":(top,literal){path.as_posix()}" for path in paths)

    @staticmethod
    def _state_file_bytes(path: Path) -> bytes:
        return os.fsencode(path.readlink()) if path.is_symlink() else path.read_bytes()

    @classmethod
    def _state_file(cls, root: Path, relative: Path) -> m.Infra.GitWorktreeFileState:
        path = root / relative
        if any((root / parent).is_symlink() for parent in relative.parents):
            msg = f"capture path traverses a symlink: {relative}"
            raise ValueError(msg)
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            git_mode = "120000"
        elif stat.S_ISREG(mode):
            git_mode = "100755" if mode & stat.S_IXUSR else "100644"
        else:
            msg = f"capture requires a regular file or symlink: {relative}"
            raise ValueError(msg)
        with FlextInfraUtilitiesGitWorktreeIO.git_stdin(
            cls._state_file_bytes(path),
        ) as stream:
            oid = cls._repo(root).git.hash_object("--stdin", istream=stream)
        return m.Infra.GitWorktreeFileState(
            path=relative,
            mode=git_mode,
            permissions=stat.S_IMODE(mode),
            oid=oid,
        )

    @classmethod
    def _state_snapshot_index(
        cls,
        root: Path,
        paths: t.SequenceOf[Path],
    ) -> t.VariadicTuple[m.Infra.GitWorktreeIndexEntry]:
        repo = cls._repo(root)
        pathspecs = cls._state_pathspecs(paths)
        for row in repo.git.ls_files("-v", "-z", "--", *pathspecs).split("\0"):
            if row and (row[0].islower() or row[0] == "S"):
                msg = (
                    "capture requires index entries without assume-unchanged "
                    "or skip-worktree flags"
                )
                raise ValueError(msg)
        entries: list[m.Infra.GitWorktreeIndexEntry] = []
        for row in repo.git.ls_files("--stage", "-z", "--", *pathspecs).split("\0"):
            if not row:
                continue
            metadata, raw_path = row.split("\t", 1)
            mode, oid, stage = metadata.split()
            if stage != "0":
                msg = f"capture requires resolved index entries: {raw_path}"
                raise ValueError(msg)
            entries.append(
                m.Infra.GitWorktreeIndexEntry(path=Path(raw_path), mode=mode, oid=oid),
            )
        intent_views = tuple(
            repo.git.diff("--cached", "--name-only", visibility, "--", *pathspecs)
            for visibility in ("--ita-visible-in-index", "--ita-invisible-in-index")
        )
        if intent_views[0] != intent_views[1]:
            msg = "capture requires intent-to-add entries to be explicitly staged first"
            raise ValueError(msg)
        return tuple(entries)

    @classmethod
    def _state_head_entries(
        cls,
        root: Path,
        paths: t.SequenceOf[Path],
    ) -> t.VariadicTuple[m.Infra.GitWorktreeIndexEntry]:
        rows = (
            cls._repo(root).git.ls_tree("-r", "--full-tree", "-z", "HEAD")
            if paths
            else ""
        )
        entries: list[m.Infra.GitWorktreeIndexEntry] = []
        for row in rows.split("\0"):
            if not row:
                continue
            metadata, raw_path = row.split("\t", 1)
            path = Path(raw_path)
            if not any(path == owned or owned in path.parents for owned in paths):
                continue
            mode, _kind, oid = metadata.split()
            entries.append(m.Infra.GitWorktreeIndexEntry(path=path, mode=mode, oid=oid))
        return tuple(entries)

    @classmethod
    def _state_snapshot_files(
        cls,
        root: Path,
        paths: t.SequenceOf[Path],
        entries: t.SequenceOf[m.Infra.GitWorktreeIndexEntry],
    ) -> t.VariadicTuple[m.Infra.GitWorktreeFileState]:
        repo = cls._repo(root)
        pathspecs = cls._state_pathspecs(paths)
        raw_paths = repo.git.ls_files(
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            *pathspecs,
        )
        head_paths = repo.git.ls_files(
            "--cached",
            "--with-tree=HEAD",
            "-z",
            "--",
            *pathspecs,
        )
        candidates = sorted(
            {
                Path(path)
                for path in (raw_paths + "\0" + head_paths).split("\0")
                if path
            },
            key=Path.as_posix,
        )
        gitlinks = {
            entry.path: entry.oid
            for entry in (*cls._state_head_entries(root, paths), *entries)
            if entry.mode == c.Infra.GIT_GITLINK_MODE_TEXT
        }
        indexed_gitlinks = {
            entry.path
            for entry in entries
            if entry.mode == c.Infra.GIT_GITLINK_MODE_TEXT
        }
        for path in (*paths, *candidates):
            for parent in path.parents:
                if (root / parent).is_symlink() and parent not in candidates:
                    msg = f"snapshot scope traverses an unowned symlink: {path}"
                    raise ValueError(msg)
        files: list[m.Infra.GitWorktreeFileState] = []
        for path in candidates:
            candidate = root / path
            if any((root / parent).is_symlink() for parent in path.parents):
                continue
            if path in gitlinks and (
                (candidate / ".git").exists() or path in indexed_gitlinks
            ):
                files.append(
                    m.Infra.GitWorktreeFileState(
                        path=path,
                        mode=c.Infra.GIT_GITLINK_MODE_TEXT,
                        permissions=0,
                        oid=cls._repo(candidate).head.commit.hexsha
                        if (candidate / ".git").exists()
                        else gitlinks[path],
                    ),
                )
            elif candidate.is_dir() and not candidate.is_symlink():
                if (candidate / ".git").exists():
                    msg = f"nested repository requires independent capture: {path}"
                    raise ValueError(msg)
                # A former HEAD file can now be a directory; its descendants
                # are separate ls-files entries and the old file is absent.
            elif candidate.exists() or candidate.is_symlink():
                files.append(cls._state_file(root, path))
        return tuple(files)

    @classmethod
    def _state_snapshot(
        cls,
        request: m.Infra.GitWorktreeStateRequest,
    ) -> m.Infra.GitWorktreeStateSnapshot:
        root = request.repo_root.resolve()
        repo = cls._repo(root)
        if Path(repo.working_tree_dir or "").resolve() != root:
            msg = "snapshot requires the repository root"
            raise ValueError(msg)
        entries = (
            cls._state_snapshot_index(root, request.paths) if request.paths else ()
        )
        files = (
            cls._state_snapshot_files(root, request.paths, entries)
            if request.paths
            else ()
        )
        head = repo.head.commit.hexsha
        retained = tuple(
            sorted(
                {repo.commit(oid).hexsha for oid in request.retained_commits} - {head},
            ),
        )
        return m.Infra.GitWorktreeStateSnapshot(
            repo_root=root,
            common_dir=Path(repo.common_dir).resolve(),
            head=head,
            retained_commits=retained,
            paths=tuple(request.paths),
            head_entries=cls._state_head_entries(root, request.paths),
            index_entries=entries,
            files=files,
        )

    @classmethod
    def git_snapshot_worktree_state(
        cls,
        request: m.Infra.GitWorktreeStateRequest,
    ) -> p.Result[m.Infra.GitWorktreeStateSnapshot]:
        """Measure owned index entries and raw files, without writing Git objects.

        Returns:
            The resulting ``p.Result[m.Infra.GitWorktreeStateSnapshot]``.

        """
        try:
            snapshot = cls._state_snapshot(request)
        except (GitCommandError, OSError, ValueError) as exc:
            return r[m.Infra.GitWorktreeStateSnapshot].fail(str(exc), exception=exc)
        return r[m.Infra.GitWorktreeStateSnapshot].ok(snapshot)

    @classmethod
    def git_verify_worktree_state(
        cls,
        snapshot: m.Infra.GitWorktreeStateSnapshot,
        destination_root: Path,
    ) -> p.Result[bool]:
        """Return false for layer differences, fail on foreign identity or read errors.

        Returns:
            False for layer differences, fail on foreign identity or read errors.

        """
        observed = cls.git_snapshot_worktree_state(
            m.Infra.GitWorktreeStateRequest(
                repo_root=destination_root,
                paths=snapshot.paths,
            ),
        )
        if observed.failure:
            return r[bool].from_failure(observed)
        actual = observed.value
        if actual.common_dir != snapshot.common_dir or actual.head != snapshot.head:
            return r[bool].fail("captured repository identity or HEAD does not match")
        return r[bool].ok(
            actual.index_entries == snapshot.index_entries
            and actual.files == snapshot.files,
        )


__all__: list[str] = ["FlextInfraUtilitiesGitStateSnapshotMixin"]
