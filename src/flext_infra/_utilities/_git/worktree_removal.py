"""Canonical Git responsibility mixin for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from git import GitCommandError, Repo

from flext_infra import m, p, r, t
from flext_infra._utilities import FlextInfraUtilitiesGitSemanticRefsMixin


class FlextInfraUtilitiesGitWorktreeRemovalMixin(
    FlextInfraUtilitiesGitSemanticRefsMixin,
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
        except GitCommandError as exc:
            return r[Repo].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[Repo].fail(
                f"failed to inspect clean worktree: {exc}",
                exception=exc,
            )
        if entry is None or entry.locked:
            reason = "unregistered" if entry is None else "locked"
            return r[Repo].fail(f"{reason} worktree: {worktree_root}")
        clean = cls._verify_worktree_clean(worktree_root)
        if clean.failure:
            return r[Repo].from_failure(clean)
        return r[Repo].ok(repo)

    @classmethod
    def _verify_worktree_clean(cls, worktree_root: Path) -> p.Result[bool]:
        """Inspect working bytes and nested repositories without index refresh.

        Returns:
            Cleanliness or the original inspection diagnostic.

        """
        try:
            worktree_repo = cls._repo(worktree_root)
            with worktree_repo.git.custom_environment(GIT_OPTIONAL_LOCKS="0"):
                dirty = cls._nested_submodule_changes(worktree_repo)
                porcelain = worktree_repo.git.status(
                    "--porcelain",
                    "--untracked-files=all",
                )
        except GitCommandError as exc:
            return r[bool].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[bool].fail(
                f"failed to inspect clean worktree: {exc}",
                exception=exc,
            )
        if dirty:
            return r[bool].fail(
                f"dirty nested submodule in {worktree_root}: {'; '.join(dirty)}",
            )
        if porcelain.strip():
            return r[bool].fail(f"dirty worktree: {worktree_root}")
        return r[bool].ok(value=True)

    @classmethod
    def git_remove_clean_worktree(
        cls,
        source_root: Path,
        worktree_root: Path,
    ) -> p.Result[bool]:
        """Retire only the selected worktree after its shared admission proof.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        preflight = cls._preflight_clean_worktree(source_root, worktree_root)
        if preflight.failure:
            return r[bool].from_failure(preflight)
        admitted = cls.git_verify_lane(
            m.Infra.GitLaneVerificationRequest(
                repo_root=worktree_root,
                operation="retire",
            ),
        )
        if admitted.failure:
            return r[bool].from_failure(admitted)
        try:
            preflight.value.git.worktree("remove", str(worktree_root))
        except GitCommandError as exc:
            return r[bool].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[bool].fail(
                f"failed to remove clean worktree: {exc}",
                exception=exc,
            )
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreeRemovalMixin"]
