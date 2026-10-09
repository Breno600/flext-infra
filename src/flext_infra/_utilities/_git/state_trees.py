"""Isolated-index tree operations for scoped durable Git captures.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from flext_infra import m, t
from flext_infra._utilities._git.state_snapshot import (
    FlextInfraUtilitiesGitStateSnapshotMixin,
)
from flext_infra._utilities._git.worktree_io import FlextInfraUtilitiesGitWorktreeIO


class FlextInfraUtilitiesGitStateTreesMixin(FlextInfraUtilitiesGitStateSnapshotMixin):
    """Read and assemble checkpoint trees without touching a real index."""

    @classmethod
    def _state_tree_entries(
        cls,
        root: Path,
        commit: str,
        paths: t.SequenceOf[Path],
    ) -> t.VariadicTuple[m.Infra.GitWorktreeIndexEntry]:
        if not paths:
            return ()
        repo = cls._repo(root)
        with (
            tempfile.TemporaryDirectory(dir=repo.common_dir) as staging,
            repo.git.custom_environment(GIT_INDEX_FILE=str(Path(staging) / "index")),
        ):
            repo.git.read_tree(commit)
            raw = repo.git.ls_files("--stage", "-z", "--", *cls._state_pathspecs(paths))
        entries: list[m.Infra.GitWorktreeIndexEntry] = []
        for row in raw.split("\0"):
            if row:
                metadata, path = row.split("\t", 1)
                mode, oid, _stage = metadata.split()
                entries.append(
                    m.Infra.GitWorktreeIndexEntry(path=Path(path), mode=mode, oid=oid),
                )
        return tuple(entries)

    @classmethod
    def _state_index_update(
        cls,
        root: Path,
        removed: t.SequenceOf[Path],
        entries: t.SequenceOf[m.Infra.GitWorktreeIndexEntry],
        *,
        index_file: Path | None = None,
    ) -> None:
        repo = cls._repo(root)
        with repo.git.custom_environment(
            GIT_INDEX_FILE=str(index_file) if index_file else None,
        ):
            if removed or entries:
                absent_oid = "0" * len(repo.head.commit.hexsha)
                removals = "".join(
                    f"0 {absent_oid}\t{path.as_posix()}\0" for path in removed
                )
                additions = "".join(
                    f"{entry.mode} {entry.oid}\t{entry.path.as_posix()}\0"
                    for entry in entries
                )
                payload = (removals + additions).encode("utf-8", "surrogateescape")
                with FlextInfraUtilitiesGitWorktreeIO.git_stdin(payload) as stream:
                    repo.git.update_index("-z", "--index-info", istream=stream)

    @classmethod
    def _state_tree(
        cls,
        snapshot: m.Infra.GitWorktreeStateSnapshot,
        entries: t.SequenceOf[m.Infra.GitWorktreeIndexEntry],
    ) -> str:
        repo = cls._repo(snapshot.repo_root)
        with tempfile.TemporaryDirectory(dir=repo.common_dir) as staging:
            index_path = str(Path(staging) / "index")
            with repo.git.custom_environment(GIT_INDEX_FILE=index_path):
                repo.git.read_tree(snapshot.head)
                removed = (
                    tuple(
                        Path(path)
                        for path in repo.git.ls_files(
                            "-z",
                            "--",
                            *cls._state_pathspecs(snapshot.paths),
                        ).split("\0")
                        if path
                    )
                    if snapshot.paths
                    else ()
                )
                cls._state_index_update(
                    snapshot.repo_root,
                    removed,
                    entries,
                    index_file=Path(index_path),
                )
                return repo.git.write_tree()

    @classmethod
    def _state_working_entries(
        cls,
        snapshot: m.Infra.GitWorktreeStateSnapshot,
    ) -> t.VariadicTuple[m.Infra.GitWorktreeIndexEntry]:
        return tuple(
            m.Infra.GitWorktreeIndexEntry(path=file.path, mode=file.mode, oid=file.oid)
            for file in snapshot.files
        )

    @classmethod
    def _state_validate_checkpoint(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
    ) -> None:
        snapshot = checkpoint.snapshot
        repo = cls._repo(snapshot.repo_root)
        if Path(repo.common_dir).resolve() != snapshot.common_dir:
            msg = "checkpoint repository identity changed"
            raise ValueError(msg)
        if (
            repo.git.rev_parse("--verify", checkpoint.checkpoint_ref)
            != checkpoint.worktree_commit
        ):
            msg = "checkpoint reference does not point at the recorded commit"
            raise ValueError(msg)
        commit = repo.commit(checkpoint.worktree_commit)
        if tuple(parent.hexsha for parent in commit.parents) != (
            snapshot.head,
            checkpoint.index_commit,
            *snapshot.retained_commits,
        ):
            msg = "checkpoint parents do not preserve both recorded layers"
            raise ValueError(msg)
        recorded = m.Infra.GitWorktreeStateSnapshot.model_validate_json(commit.message)
        if recorded != snapshot:
            msg = "checkpoint metadata does not match its snapshot"
            raise ValueError(msg)
        for oid, expected in (
            (checkpoint.index_commit, snapshot.index_entries),
            (checkpoint.worktree_commit, cls._state_working_entries(snapshot)),
        ):
            if (
                cls._state_tree_entries(snapshot.repo_root, oid, snapshot.paths)
                != expected
            ):
                msg = "checkpoint tree does not match its captured entries"
                raise ValueError(msg)


__all__: list[str] = ["FlextInfraUtilitiesGitStateTreesMixin"]
