"""Strict worktree versus physical file-scope classification for writers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from git import GitError, Repo
from git.repo.fun import is_git_dir

from flext_infra import c, m, r

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesGitMutationScopeMixin:
    """Classify absent Git ownership before opening any declared Git marker."""

    @staticmethod
    def _git_mutation_scope(root: Path) -> m.Infra.GitMutationScope:
        resolved = root.resolve(strict=True)
        if not resolved.is_dir():
            msg = f"mutation scope is not a physical directory: {root}"
            raise ValueError(msg)
        for candidate in (resolved, *resolved.parents):
            marker = candidate / c.Infra.GIT_DIR
            if marker.exists() or marker.is_symlink():
                with Repo(candidate, search_parent_directories=False) as repo:
                    if (
                        repo.bare
                        or repo.working_tree_dir is None
                        or Path(repo.working_tree_dir).resolve() != candidate
                    ):
                        msg = (
                            f"declared Git marker does not own this worktree: "
                            f"{candidate}"
                        )
                        raise ValueError(msg)
                    return m.Infra.GitMutationScope(
                        root=resolved,
                        git_dir=Path(repo.git_dir).resolve(),
                    )
            if is_git_dir(candidate):
                msg = (
                    f"mutation scope belongs to Git storage rather than a "
                    f"worktree: {root}"
                )
                raise ValueError(msg)
        return m.Infra.GitMutationScope(root=resolved, git_dir=None)

    @classmethod
    def git_mutation_scope(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitMutationScope]:
        """Reject malformed declared Git roots; marker-free roots remain file scopes.

        Returns:
            The resulting ``p.Result[m.Infra.GitMutationScope]``.

        """
        try:
            scope = cls._git_mutation_scope(request.repo_root)
        except (GitError, OSError, ValueError) as exc:
            return r[m.Infra.GitMutationScope].fail(str(exc), exception=exc)
        return r[m.Infra.GitMutationScope].ok(scope)


__all__: list[str] = ["FlextInfraUtilitiesGitMutationScopeMixin"]
