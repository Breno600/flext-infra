"""Canonical Git responsibility mixin for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from git import GitCommandError

from flext_infra import c, m, p, r, t
from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeIO
from flext_infra._utilities._git.worktree_checkpoint import (
    FlextInfraUtilitiesGitWorktreeCheckpointMixin,
)


class FlextInfraUtilitiesGitWorktreePatchMixin(
    FlextInfraUtilitiesGitWorktreeCheckpointMixin,
):
    """Own worktree patch operations."""

    @classmethod
    def _git_check_patch_at(
        cls,
        repository_root: Path,
        patch: bytes,
        *,
        reverse: bool,
    ) -> p.Result[bool]:
        """Check one patch direction against an explicit repository root.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if not patch:
            return r[bool].ok(value=True)
        direction: list[str] = ["--reverse"] if reverse else []
        try:
            repo = cls._repo(repository_root)
            with FlextInfraUtilitiesGitWorktreeIO.git_stdin(patch) as istream:
                repo.git.apply("--check", "--binary", *direction, "-", istream=istream)
        except GitCommandError as exc:
            return r[bool].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[bool].fail(f"git apply --check failed: {exc}", exception=exc)
        return r[bool].ok(value=True)

    @classmethod
    def git_check_patch(cls, delta: m.Infra.RepositoryDelta) -> p.Result[bool]:
        """Forward-check one operation patch against the live source worktree.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return cls._git_check_patch_at(delta.source_root, delta.patch, reverse=False)

    @classmethod
    def git_check_isolated_patch(cls, delta: m.Infra.RepositoryDelta) -> p.Result[bool]:
        """Reverse-check that the isolated worktree contains the patch target.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return cls._git_check_patch_at(delta.worktree_root, delta.patch, reverse=True)

    @classmethod
    def _git_source_has_patch(cls, delta: m.Infra.RepositoryDelta) -> p.Result[bool]:
        """Return success when the live source already contains the patch target.

        Returns:
            Success when the live source already contains the patch target.

        """
        return cls._git_check_patch_at(delta.source_root, delta.patch, reverse=True)

    @staticmethod
    def _git_patch_added_paths(patch: bytes) -> t.VariadicTuple[Path]:
        """Return paths declared as new files by one binary Git patch.

        Returns:
            Paths declared as new files by one binary Git patch.

        """
        added: list[Path] = []
        current: Path | None = None
        for raw_line in patch.splitlines():
            if raw_line.startswith(b"diff --git a/"):
                _, _, _source, target = raw_line.split(maxsplit=3)
                current = Path(target.removeprefix(b"b/").decode())
                continue
            if raw_line.startswith(b"new file mode ") and current is not None:
                added.append(current)
        return tuple(added)

    @classmethod
    def _git_apply_gitlinks(cls, repository_root: Path, patch: bytes) -> p.Result[bool]:
        """Apply submodule entries that have no working-tree file representation.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        current: Path | None = None
        gitlink = False
        gitlink_mode = c.Infra.GIT_GITLINK_MODE_TEXT.encode()
        for raw_line in patch.splitlines():
            if raw_line.startswith(b"diff --git a/"):
                _, _, _source, target = raw_line.split(maxsplit=3)
                current = Path(target.removeprefix(b"b/").decode())
                gitlink = False
                continue
            if raw_line == b"new file mode " + gitlink_mode or (
                raw_line.startswith(b"index ")
                and raw_line.endswith(b" " + gitlink_mode)
            ):
                gitlink = True
                continue
            if (
                gitlink
                and current is not None
                and raw_line.startswith(b"+Subproject commit ")
            ):
                commit = raw_line.removeprefix(b"+Subproject commit ").decode()
                try:
                    repo = cls._repo(repository_root)
                    repo.git.update_index(
                        "--add",
                        "--cacheinfo",
                        c.Infra.GIT_GITLINK_MODE_TEXT,
                        commit,
                        current.as_posix(),
                    )
                except (GitCommandError, OSError, ValueError) as exc:
                    return r[bool].fail(
                        f"failed to apply gitlink: {current}: {exc}",
                        exception=exc,
                    )
        return r[bool].ok(value=True)

    @classmethod
    def _git_apply_with_ignored_additions(
        cls,
        delta: m.Infra.RepositoryDelta,
    ) -> p.Result[bool]:
        """Apply additions over existing ignored projections with rollback.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        collisions = tuple(
            path
            for path in cls._git_patch_added_paths(delta.patch)
            if (delta.source_root / path).is_file()
        )
        if not collisions:
            return r[bool].fail("patch has no existing ignored additions")
        original = {
            path: (delta.source_root / path).read_bytes() for path in collisions
        }
        try:
            for path in collisions:
                (delta.source_root / path).unlink()
            repo = cls._repo(delta.source_root)
            with FlextInfraUtilitiesGitWorktreeIO.git_stdin(delta.patch) as istream:
                repo.git.apply("--binary", "-", istream=istream)
        except (GitCommandError, OSError, ValueError) as exc:
            # Rollback restores the ignored files this invocation removed; the
            # apply failure stays the reported cause.
            for path, content in original.items():
                target = delta.source_root / path
                target.unlink(missing_ok=True)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            return r[bool].fail(
                f"git apply failed on ignored additions: {exc}",
                exception=exc,
            )
        return r[bool].ok(value=True)

    @classmethod
    def git_apply_patch(cls, delta: m.Infra.RepositoryDelta) -> p.Result[bool]:
        """Forward-check and idempotently converge one source operation patch.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if not delta.patch:
            return r[bool].ok(value=True)
        check_result = cls.git_check_patch(delta)
        if check_result.failure:
            converged_result = cls._git_source_has_patch(delta)
            if converged_result.success:
                return cls._git_apply_gitlinks(delta.source_root, delta.patch)
            collision_result = cls._git_apply_with_ignored_additions(delta)
            if collision_result.success:
                return cls._git_apply_gitlinks(delta.source_root, delta.patch)
            return r[bool].from_failure(check_result)
        try:
            repo = cls._repo(delta.source_root)
            with FlextInfraUtilitiesGitWorktreeIO.git_stdin(delta.patch) as istream:
                repo.git.apply("--binary", "-", istream=istream)
        except (GitCommandError, OSError, ValueError) as exc:
            return r[bool].fail(f"git apply failed: {exc}", exception=exc)
        return cls._git_apply_gitlinks(delta.source_root, delta.patch)


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreePatchMixin"]
