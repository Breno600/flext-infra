"""Canonical Git responsibility mixin for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from git import GitCommandError

from flext_infra import c, m, p, r, t
from flext_infra._utilities._git.worktree_materialization import (
    FlextInfraUtilitiesGitWorktreeMaterializationMixin,
)


class FlextInfraUtilitiesGitWorktreeCheckpointMixin(
    FlextInfraUtilitiesGitWorktreeMaterializationMixin,
):
    """Own worktree checkpoint operations."""

    @staticmethod
    def _transaction_exclusion_pathspecs() -> t.VariadicTuple[str]:
        """Pathspecs that exclude tool-cache directories from operation deltas.

        Returns:
            The resulting ``t.VariadicTuple[str]``.

        """
        return tuple(
            f":(exclude){name}"
            for name in sorted(c.Infra.WORKTREE_TRANSACTION_EXCLUDED_DIRS)
        )

    @classmethod
    def git_repository_delta(
        cls,
        repository: m.Infra.RepositoryWorktree,
        *,
        source_gitlinks: t.MappingKV[str, str] | None = None,
    ) -> p.Result[m.Infra.RepositoryDelta]:
        """Stage and capture the operation-only patch after a checkpoint.

        Returns:
            The resulting ``p.Result[m.Infra.RepositoryDelta]``.

        """
        head_result = cls._git_head_oid(repository.worktree_root)
        if head_result.failure or head_result.value != repository.checkpoint_sha:
            return r[m.Infra.RepositoryDelta].fail(
                head_result.error
                if head_result.failure
                else "isolated command moved repository HEAD",
            )
        exclusions = cls._transaction_exclusion_pathspecs()
        try:
            repo = cls._repo(repository.worktree_root)
            repo.git.add("-A", "-f", *exclusions)
            for path, source_head in (source_gitlinks or {}).items():
                repo.git.update_index(
                    "--add",
                    "--cacheinfo",
                    c.Infra.GIT_GITLINK_MODE_TEXT,
                    source_head,
                    path,
                )
            # Gitlinks are owned by `make setup`, which fast-forwards each
            # declared submodule to its branch tip. Including them here made
            # every verb that runs after setup report "pending changes" for
            # pointers it never touched, so `gen` aborted before applying.
            names_output = repo.git.diff(
                "--cached",
                "--name-only",
                "-z",
                "--ignore-submodules=all",
                repository.checkpoint_sha,
                "--",
                *exclusions,
            )
            patch_bytes = repo.git.diff(
                "--cached",
                "--binary",
                "--ignore-submodules=all",
                repository.checkpoint_sha,
                "--",
                *exclusions,
            ).encode(c.Cli.ENCODING_DEFAULT)
        except GitCommandError as exc:
            return r[m.Infra.RepositoryDelta].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.RepositoryDelta].fail(
                f"failed to capture operation patch: {exc}",
                exception=exc,
            )
        # git apply rejects a patch whose final line has no terminating newline
        # ("corrupt patch"). `git diff --binary` can emit exactly that when the
        # last hunk ends on a context line, so restore the single trailing
        # newline the patch format requires before the delta is applied.
        if patch_bytes and not patch_bytes.endswith(b"\n"):
            patch_bytes += b"\n"
        return r[m.Infra.RepositoryDelta].ok(
            m.Infra.RepositoryDelta(
                relative_path=repository.relative_path,
                source_root=repository.source_root,
                worktree_root=repository.worktree_root,
                checkpoint_sha=repository.checkpoint_sha,
                changed_files=tuple(name for name in names_output.split("\0") if name),
                patch=patch_bytes,
            ),
        )


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreeCheckpointMixin"]
