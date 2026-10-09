"""Canonical Git responsibility mixin for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from stat import S_IMODE
from typing import TYPE_CHECKING

from flext_cli import u
from git import GitCommandError

from flext_infra import c, r, t
from flext_infra._utilities._git.worktree_discovery import (
    FlextInfraUtilitiesGitWorktreeDiscoveryMixin,
)
from flext_infra._utilities._git.worktree_io import FlextInfraUtilitiesGitWorktreeIO

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesGitWorktreeMaterializationMixin(
    FlextInfraUtilitiesGitWorktreeDiscoveryMixin,
):
    """Own worktree materialization operations."""

    @classmethod
    def git_add_detached_worktree(
        cls,
        source_root: Path,
        worktree_root: Path,
    ) -> p.Result[str]:
        """Create a detached worktree at the source repository HEAD.

        Returns:
            The resulting ``p.Result[str]``.

        """
        ensure_parent = u.Cli.ensure_dir(worktree_root.parent)
        if ensure_parent.failure:
            return r[str].from_failure(ensure_parent)
        if worktree_root.exists():
            try:
                worktree_root.rmdir()
            except OSError as exc:
                return r[str].fail(
                    f"worktree target is not empty: {exc}",
                    exception=exc,
                )
        head_result = cls._git_head_oid(source_root)
        if head_result.failure:
            return head_result
        # An isolated transaction is a generator-validation boundary, not a user
        # checkout. Host post-checkout hooks may depend on a toolchain which the
        # generated project is about to declare, so they cannot be its prerequisite.
        # Transaction validators still exercise the generated artifact explicitly.
        try:
            repo = cls._repo(source_root)
            repo.git.execute([
                c.Infra.GIT,
                "-c",
                "core.hooksPath=/dev/null",
                "worktree",
                "add",
                "--detach",
                str(worktree_root),
                head_result.value,
            ])
        except GitCommandError as exc:
            return r[str].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[str].fail(f"failed to add detached worktree: {exc}", exception=exc)
        return head_result

    @staticmethod
    def _git_path_is_excluded(path: Path, excluded: t.SequenceOf[Path]) -> bool:
        """Return whether a relative path belongs to an excluded subtree.

        Returns:
            Whether a relative path belongs to an excluded subtree.

        """
        return any(path == prefix or prefix in path.parents for prefix in excluded)

    @classmethod
    def _git_copy_untracked(
        cls,
        source_root: Path,
        worktree_root: Path,
        excluded: t.SequenceOf[Path],
    ) -> p.Result[bool]:
        """Copy non-ignored untracked files into an isolated worktree.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        try:
            repo = cls._repo(source_root)
            untracked = repo.git.ls_files("--others", "--exclude-standard", "-z")
        except GitCommandError as exc:
            return r[bool].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[bool].fail(f"failed to list untracked files: {exc}", exception=exc)
        for raw_path in untracked.split("\0"):
            if not raw_path:
                continue
            relative_path = Path(raw_path)
            if cls._git_path_is_excluded(relative_path, excluded):
                continue
            source_path = source_root / relative_path
            if source_path.is_dir() and not source_path.is_symlink():
                return r[bool].fail(
                    f"nested repository requires separate capture: {relative_path}",
                )
            destination_path = worktree_root / relative_path
            ensure_parent = u.Cli.ensure_dir(destination_path.parent)
            if ensure_parent.failure:
                return r[bool].from_failure(ensure_parent)
            if source_path.is_symlink():
                try:
                    destination_path.symlink_to(source_path.readlink())
                except OSError as exc:
                    return r[bool].fail(
                        f"failed to copy symlink {relative_path}: {exc}",
                    )
                continue
            copy_result = u.Cli.files_copy(source_path, destination_path)
            if copy_result.failure:
                return r[bool].from_failure(copy_result)
        return r[bool].ok(value=True)

    @classmethod
    def git_copy_worktree_state(
        cls,
        source_root: Path,
        worktree_root: Path,
        *,
        excluded: t.SequenceOf[Path] = (),
    ) -> p.Result[bool]:
        """Copy both Git layers to a pristine sibling worktree at the same HEAD.

        HEAD-to-worktree and HEAD-to-index patches are independent: applying the
        latter with ``--cached`` preserves partial staging without changing the
        copied working files. Both patches are checked before either is applied.
        Exclusions are literal repository-relative subtrees. Nested repositories
        retain their own worktree ownership and must be captured separately.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if any(path.is_absolute() or ".." in path.parts for path in excluded):
            return r[bool].fail("worktree exclusions must be repository-relative")
        pathspecs = tuple(
            f":(top,literal,exclude){path.as_posix()}" for path in excluded
        )
        try:
            return cls._git_copy_worktree_layers(
                source_root,
                worktree_root,
                excluded,
                pathspecs,
            )
        except GitCommandError as exc:
            return r[bool].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[bool].fail(f"failed to copy worktree state: {exc}", exception=exc)

    @classmethod
    def _git_copy_worktree_layers(
        cls,
        source_root: Path,
        worktree_root: Path,
        excluded: t.SequenceOf[Path],
        pathspecs: t.VariadicTuple[str],
    ) -> p.Result[bool]:
        repo = cls._repo(source_root)
        worktree_repo = cls._repo(worktree_root)
        if source_root.resolve() == worktree_root.resolve():
            return r[bool].fail("source and destination must be distinct worktrees")
        if any(
            Path(repository.working_tree_dir or "").resolve() != root.resolve()
            for repository, root in (
                (repo, source_root),
                (worktree_repo, worktree_root),
            )
        ):
            return r[bool].fail("state copy requires repository root paths")
        if Path(repo.common_dir).resolve() != Path(worktree_repo.common_dir).resolve():
            return r[bool].fail("state copy requires worktrees of the same repository")
        if repo.head.commit.hexsha != worktree_repo.head.commit.hexsha:
            return r[bool].fail("source and destination HEAD must match")
        if worktree_repo.git.status("--porcelain=v1", "--untracked-files=all"):
            return r[bool].fail("destination worktree must be clean")
        if repo.git.ls_files("--unmerged", "-z"):
            return r[bool].fail("source index has unresolved merge entries")
        patches = tuple(
            repo.git.diff(
                *layer,
                "--binary",
                "--full-index",
                "--no-ext-diff",
                "--no-textconv",
                "--no-renames",
                c.Infra.GIT_HEAD,
                "--",
                ".",
                *pathspecs,
                strip_newline_in_stdout=False,
            ).encode(c.Cli.ENCODING_DEFAULT, errors="surrogateescape")
            for layer in ((), ("--cached",))
        )
        deleted = {
            Path(name)
            for name in repo.git.diff(
                "--name-only",
                "--diff-filter=D",
                "-z",
                c.Infra.GIT_HEAD,
                "--",
                ".",
                *pathspecs,
            ).split("\0")
            if name
        }
        for raw_path in repo.git.ls_files("--others", "--exclude-standard", "-z").split(
            "\0",
        ):
            relative = Path(raw_path)
            if not raw_path or cls._git_path_is_excluded(relative, excluded):
                continue
            source_path = source_root / relative
            if source_path.is_dir() and not source_path.is_symlink():
                return r[bool].fail(
                    f"nested repository requires separate capture: {relative}",
                )
            destination = worktree_root / relative
            if (
                destination.exists() or destination.is_symlink()
            ) and relative not in deleted:
                return r[bool].fail(f"untracked destination already exists: {relative}")
            for parent in relative.parents:
                candidate = worktree_root / parent
                if parent not in deleted and (
                    candidate.is_symlink()
                    or (candidate.exists() and not candidate.is_dir())
                ):
                    return r[bool].fail(
                        f"unsafe untracked destination parent: {parent}",
                    )
        for check in (True, False):
            for patch_bytes, layer in zip(patches, ((), ("--cached",)), strict=True):
                if not patch_bytes:
                    continue
                with FlextInfraUtilitiesGitWorktreeIO.git_stdin(patch_bytes) as istream:
                    worktree_repo.git.apply(
                        *layer,
                        *(("--check",) if check else ()),
                        "-",
                        istream=istream,
                    )
        # Git records only executable bits; apply creates files through the
        # process umask. Preserve the physical source permissions separately.
        for raw_path in repo.git.ls_files("-z", strip_newline_in_stdout=False).split(
            "\0",
        ):
            relative = Path(raw_path)
            if not raw_path or cls._git_path_is_excluded(relative, excluded):
                continue
            source_path = source_root / relative
            if source_path.is_file() and not source_path.is_symlink():
                (worktree_root / relative).chmod(S_IMODE(source_path.stat().st_mode))
        return cls._git_copy_untracked(source_root, worktree_root, tuple(excluded))


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreeMaterializationMixin"]
