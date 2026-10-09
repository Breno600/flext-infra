"""Canonical Git responsibility mixin for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from git import GitCommandError

from flext_infra import m, r
from flext_infra._utilities._git.worktree_facts import (
    FlextInfraUtilitiesGitWorktreeFactsMixin,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesGitWorktreeRootsMixin(
    FlextInfraUtilitiesGitWorktreeFactsMixin,
):
    """Own worktree roots operations."""

    @classmethod
    def git_repository_root(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitRootReport]:
        """Resolve the superproject root or the repository's own top level.

        Returns:
            The resulting ``p.Result[m.Infra.GitRootReport]``.

        """
        root = cls._git_repository_root_path(request.repo_root)
        if root.failure:
            return r[m.Infra.GitRootReport].from_failure(root)
        return r[m.Infra.GitRootReport].ok(
            m.Infra.GitRootReport(repository_root=root.value),
        )

    @classmethod
    def git_primary_worktree_root(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitPrimaryRootReport]:
        """Resolve the primary worktree from Git's canonical storage topology.

        Returns:
            The resulting ``p.Result[m.Infra.GitPrimaryRootReport]``.

        """
        primary = cls._git_primary_worktree_root_path(request.repo_root)
        if primary.failure:
            return r[m.Infra.GitPrimaryRootReport].from_failure(primary)
        return r[m.Infra.GitPrimaryRootReport].ok(
            m.Infra.GitPrimaryRootReport(primary_root=primary.value),
        )

    @classmethod
    def _git_repository_root_path(cls, repository_path: Path) -> p.Result[Path]:
        """Private Path-based workspace/superproject resolver.

        ``rev-parse --show-superproject-working-tree`` exits 0 and prints
        nothing when the checkout is not a submodule; that empty answer selects
        the checkout's own top level. Every Git failure is a failure.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        try:
            repo = cls._repo(repository_path)
            superproject = repo.git.rev_parse(
                "--show-superproject-working-tree",
            ).strip()
            root = superproject or repo.git.rev_parse("--show-toplevel").strip()
        except (GitCommandError, OSError, ValueError) as exc:
            return r[Path].fail(
                f"failed to resolve repository root: {exc}",
                exception=exc,
            )
        return r[Path].ok(Path(root).resolve())


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreeRootsMixin"]
