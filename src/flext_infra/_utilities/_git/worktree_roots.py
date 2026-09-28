"""Canonical Git responsibility mixin for ``u.Infra``."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from git import GitCommandError

from flext_core import r
from flext_infra import m

from .worktree_facts import FlextInfraUtilitiesGitWorktreeFactsMixin

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesGitWorktreeRootsMixin(
    FlextInfraUtilitiesGitWorktreeFactsMixin
):
    """Own worktree roots operations."""

    @classmethod
    def git_repository_root(
        cls, request: m.Infra.GitRepoRequest
    ) -> p.Result[m.Infra.GitRootReport]:
        """Resolve the superproject root or the repository's own top level."""
        root = cls._git_repository_root_path(request.repo_root)
        if root.failure:
            return r[m.Infra.GitRootReport].from_failure(root)
        return r[m.Infra.GitRootReport].ok(
            m.Infra.GitRootReport(repository_root=root.value)
        )

    @classmethod
    def git_primary_worktree_root(
        cls, request: m.Infra.GitRepoRequest
    ) -> p.Result[m.Infra.GitPrimaryRootReport]:
        """Resolve the primary worktree from Git's canonical storage topology."""
        primary = cls._git_primary_worktree_root_path(request.repo_root)
        if primary.failure:
            return r[m.Infra.GitPrimaryRootReport].from_failure(primary)
        return r[m.Infra.GitPrimaryRootReport].ok(
            m.Infra.GitPrimaryRootReport(primary_root=primary.value)
        )

    @classmethod
    def _git_repository_root_path(cls, repository_path: Path) -> p.Result[Path]:
        """Private Path-based workspace/superproject resolver."""
        try:
            repo = cls._repo(repository_path)
            superproject = repo.git.rev_parse(
                "--show-superproject-working-tree"
            ).strip()
        except GitCommandError:
            # Not inside any superproject — check if we're in a worktree at all.
            try:
                fallback_repo = cls._repo(repository_path)
                inside = fallback_repo.git.rev_parse("--is-inside-work-tree").strip()
            except GitCommandError:
                return r[Path].ok(repository_path.expanduser().resolve())
            if inside != "true":
                return r[Path].ok(repository_path.expanduser().resolve())
            return r[Path].fail("failed to resolve Git superproject")
        except (OSError, ValueError) as exc:
            return r[Path].fail(
                f"failed to resolve repository root: {exc}", exception=exc
            )
        if superproject:
            return r[Path].ok(Path(superproject).resolve())
        try:
            top_level = repo.git.rev_parse("--show-toplevel").strip()
        except GitCommandError as exc:
            return r[Path].fail(str(exc), exception=exc)
        return r[Path].ok(Path(top_level).resolve())


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreeRootsMixin"]
