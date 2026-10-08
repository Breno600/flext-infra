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

from flext_infra import c, p, r, t
from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeIO
from flext_infra._utilities._git.worktree_discovery import (
    FlextInfraUtilitiesGitWorktreeDiscoveryMixin,
)

if TYPE_CHECKING:
    from git import Repo


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
    def _git_copy_untracked_file(
        cls,
        source_root: Path,
        worktree_root: Path,
        relative_path: Path,
    ) -> p.Result[bool]:
        """Copy one untracked file or symlink into the worktree.

        Returns:
            The resulting ``p.Result[bool]``.

        """
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
            return r[bool].ok(value=True)
        copy_result = u.Cli.files_copy(source_path, destination_path)
        if copy_result.failure:
            return r[bool].from_failure(copy_result)
        return r[bool].ok(value=True)

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
            copied = cls._git_copy_untracked_file(
                source_root,
                worktree_root,
                relative_path,
            )
            if copied.failure:
                return copied
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
    def _verified_worktree_pair(
        cls,
        repo: Repo,
        worktree_repo: Repo,
        source_root: Path,
        worktree_root: Path,
    ) -> p.Result[bool]:
        """Require two distinct clean worktrees of one repository at one HEAD.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        conflict = cls._worktree_pair_conflict(
            repo,
            worktree_repo,
            source_root,
            worktree_root,
        )
        if conflict is not None:
            return r[bool].fail(conflict)
        if worktree_repo.git.status("--porcelain=v1", "--untracked-files=all"):
            return r[bool].fail("destination worktree must be clean")
        if repo.git.ls_files("--unmerged", "-z"):
            return r[bool].fail("source index has unresolved merge entries")
        return r[bool].ok(value=True)

    @staticmethod
    def _worktree_pair_conflict(
        repo: Repo,
        worktree_repo: Repo,
        source_root: Path,
        worktree_root: Path,
    ) -> str | None:
        """Return the first structural conflict between the two worktrees.

        Returns:
            The resulting ``str | None``.

        """
        if source_root.resolve() == worktree_root.resolve():
            return "source and destination must be distinct worktrees"
        if any(
            Path(repository.working_tree_dir or "").resolve() != root.resolve()
            for repository, root in (
                (repo, source_root),
                (worktree_repo, worktree_root),
            )
        ):
            return "state copy requires repository root paths"
        if Path(repo.common_dir).resolve() != Path(worktree_repo.common_dir).resolve():
            return "state copy requires worktrees of the same repository"
        if repo.head.commit.hexsha != worktree_repo.head.commit.hexsha:
            return "source and destination HEAD must match"
        return None

    @staticmethod
    def _worktree_layer_patches(
        repo: Repo,
        pathspecs: t.VariadicTuple[str],
    ) -> t.Pair[t.VariadicTuple[bytes], frozenset[Path]]:
        """Build both layer patches and the HEAD-deleted path set.

        Returns:
            The resulting ``(patches, deleted paths)`` pair.

        """
        patches: t.VariadicTuple[bytes] = tuple(
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
        deleted = frozenset(
            {
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
            },
        )
        return patches, deleted

    @staticmethod
    def _unsafe_untracked_parent(
        worktree_root: Path,
        relative: Path,
        deleted: frozenset[Path],
    ) -> Path | None:
        """Return the first unsafe ancestor of one untracked destination.

        Returns:
            The resulting ``Path | None``.

        """
        for parent in relative.parents:
            candidate = worktree_root / parent
            if parent not in deleted and (
                candidate.is_symlink()
                or (candidate.exists() and not candidate.is_dir())
            ):
                return parent
        return None

    @classmethod
    def _verify_untracked_destinations(
        cls,
        source_root: Path,
        worktree_root: Path,
        excluded: t.SequenceOf[Path],
        deleted: frozenset[Path],
        untracked_listing: str,
    ) -> p.Result[bool]:
        """Require every untracked destination to be absent and safely nested.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for raw_path in untracked_listing.split("\0"):
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
            unsafe = cls._unsafe_untracked_parent(worktree_root, relative, deleted)
            if unsafe is not None:
                return r[bool].fail(f"unsafe untracked destination parent: {unsafe}")
        return r[bool].ok(value=True)

    @classmethod
    def _apply_layer_patches(
        cls,
        worktree_repo: Repo,
        patches: t.VariadicTuple[bytes],
    ) -> None:
        """Verify then apply both layer patches through one stdin stream each."""
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

    @classmethod
    def _preserve_source_modes(
        cls,
        repo: Repo,
        source_root: Path,
        worktree_root: Path,
        excluded: t.SequenceOf[Path],
    ) -> None:
        """Copy physical file permissions Git's apply does not record."""
        for raw_path in repo.git.ls_files(
            "-z",
            strip_newline_in_stdout=False,
        ).split("\0"):
            relative = Path(raw_path)
            if not raw_path or cls._git_path_is_excluded(relative, excluded):
                continue
            source_path = source_root / relative
            if source_path.is_file() and not source_path.is_symlink():
                (worktree_root / relative).chmod(S_IMODE(source_path.stat().st_mode))

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
        verified = cls._verified_worktree_pair(
            repo,
            worktree_repo,
            source_root,
            worktree_root,
        )
        if verified.failure:
            return verified
        patches, deleted = cls._worktree_layer_patches(repo, pathspecs)
        destinations = cls._verify_untracked_destinations(
            source_root,
            worktree_root,
            excluded,
            deleted,
            repo.git.ls_files("--others", "--exclude-standard", "-z"),
        )
        if destinations.failure:
            return destinations
        cls._apply_layer_patches(worktree_repo, patches)
        # Git records only executable bits; apply creates files through the
        # process umask. Preserve the physical source permissions separately.
        cls._preserve_source_modes(repo, source_root, worktree_root, excluded)
        return cls._git_copy_untracked(source_root, worktree_root, tuple(excluded))


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreeMaterializationMixin"]
