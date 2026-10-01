"""Canonical Git responsibility mixin for ``u.Infra``.

Bounded, symlink-free directory measurement used by the worktree facts
primitive. A bound being hit or one unreadable subtree degrades ``exact`` to
False; the walk never follows a symlink out of the tree.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from flext_infra import c, t

from .worktree_status import FlextInfraUtilitiesGitWorktreeStatusMixin


class FlextInfraUtilitiesGitWorktreeMeasureMixin(
    FlextInfraUtilitiesGitWorktreeStatusMixin
):
    """Own the bounded tree measurement for worktree facts."""

    @classmethod
    def _worktree_measure(cls, root: Path) -> t.Triple[int, float, bool]:
        """Measure one tree within the bounded, symlink-free walk."""
        started = time.monotonic()
        total_bytes = 0
        newest = 0.0
        exact = True
        seen = 0
        stack: list[Path] = [root]
        while stack:
            entries, readable = cls._worktree_scan_dir(stack.pop())
            if not readable:
                exact = False
                continue
            for entry in entries:
                seen += 1
                if seen > c.Infra.GIT_WORKTREE_SCAN_FILE_CAP or (
                    time.monotonic() - started > c.Infra.GIT_WORKTREE_SCAN_TIME_CAP_S
                ):
                    exact = False
                    stack.clear()
                    break
                descend, size, mtime = cls._worktree_entry_metrics(entry)
                if descend:
                    stack.append(Path(entry.path))
                    continue
                total_bytes += size
                newest = max(newest, mtime)
        return total_bytes, newest, exact

    @staticmethod
    def _worktree_scan_dir(
        directory: Path,
    ) -> t.Pair[t.VariadicTuple[os.DirEntry[str]], bool]:
        """List one directory paired with whether it was readable."""
        entries: t.VariadicTuple[os.DirEntry[str]] = ()
        readable = True
        try:
            with os.scandir(directory) as iterator:
                entries = tuple(iterator)
        except OSError:
            readable = False
        return entries, readable

    @classmethod
    def _worktree_entry_metrics(
        cls, entry: os.DirEntry[str]
    ) -> t.Triple[bool, int, float]:
        """Return ``(descend, bytes, mtime)`` for one entry, skipping symlinks."""
        descend = False
        size = 0
        mtime = 0.0
        try:
            descend = cls._worktree_entry_is_dir(entry)
            if not descend:
                size, mtime = cls._worktree_entry_file_metrics(entry)
        except OSError:
            size = 0
            mtime = 0.0
            descend = False
        return descend, size, mtime

    @staticmethod
    def _worktree_entry_is_dir(entry: os.DirEntry[str]) -> bool:
        """Return whether one entry is a real directory rather than a symlink."""
        return entry.is_dir(follow_symlinks=False) and not entry.is_symlink()

    @staticmethod
    def _worktree_entry_file_metrics(entry: os.DirEntry[str]) -> t.Pair[int, float]:
        """Return ``(bytes, mtime)`` for one regular entry, zero for a symlink."""
        if entry.is_symlink():
            return 0, 0.0
        stat = entry.stat(follow_symlinks=False)
        return stat.st_size, stat.st_mtime


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreeMeasureMixin"]
