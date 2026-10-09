"""Canonical Git responsibility mixin for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from git import GitCommandError, Repo

from flext_core import r
from flext_infra._utilities._git.worktree_patch import (
    FlextInfraUtilitiesGitWorktreePatchMixin,
)

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraUtilitiesGitWorktreeRemovalMixin(
    FlextInfraUtilitiesGitWorktreePatchMixin,
):
    """Own worktree removal operations."""

    @staticmethod
    def _nested_submodule_changes(repo: Repo) -> t.VariadicTuple[str]:
        nested = repo.git.submodule(
            "foreach",
            "--recursive",
            "git status --porcelain --untracked-files=all",
            with_exceptions=False,
        )
        return tuple(
            line
            for line in nested.splitlines()
            if line and not line.startswith("Entering '")
        )

    @classmethod
    def _preflight_clean_worktree(
        cls,
        source_root: Path,
        worktree_root: Path,
    ) -> p.Result[Repo]:
        try:
            repo = cls._repo(source_root)
            entry = next(
                (
                    item
                    for item in cls._registered_worktree_entries(
                        repo.git.worktree("list", "--porcelain"),
                    )
                    if item.path == worktree_root.resolve()
                ),
                None,
            )
            worktree_repo = cls._repo(worktree_root)
            dirty = cls._nested_submodule_changes(worktree_repo)
            porcelain = worktree_repo.git.status("--porcelain", "--untracked-files=all")
        except GitCommandError as exc:
            return r[Repo].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[Repo].fail(
                f"failed to inspect clean worktree: {exc}",
                exception=exc,
            )
        if entry is not None and entry.locked:
            return r[Repo].fail(f"locked worktree: {worktree_root}")
        if dirty:
            return r[Repo].fail(
                f"dirty nested submodule in {worktree_root}: {'; '.join(dirty)}",
            )
        if porcelain.strip():
            return r[Repo].fail(f"dirty worktree: {worktree_root}")
        return r[Repo].ok(repo)

    @classmethod
    def git_remove_clean_worktree(
        cls,
        source_root: Path,
        worktree_root: Path,
    ) -> p.Result[bool]:
        """Remove an explicitly selected clean worktree and prune metadata.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        preflight = cls._preflight_clean_worktree(source_root, worktree_root)
        if preflight.failure:
            return r[bool].from_failure(preflight)
        try:
            preflight.value.git.worktree("remove", "--force", str(worktree_root))
            preflight.value.git.worktree("prune")
        except GitCommandError as exc:
            return r[bool].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[bool].fail(
                f"failed to remove clean worktree: {exc}",
                exception=exc,
            )
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreeRemovalMixin"]
