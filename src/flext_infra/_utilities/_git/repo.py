"""GitPython repository helpers for the private git facet.

Only ``FlextInfraUtilitiesGitRepo`` lives here. Semantic operations use
GitPython's object-oriented API (``Repo``, ``IndexFile``, ``Remote``,
``BaseIndexEntry``) or the ``repo.git.<cmd>(args)`` proxy directly;
``Git(path).execute(tuple)`` with manual cast/protocol is eliminated.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shutil
from pathlib import Path

from git import (
    Git,
    GitCommandError,
    GitCommandNotFound,
    InvalidGitRepositoryError,
    NoSuchPathError,
    Repo,
)

from flext_infra import c, m, p, r, t


class FlextInfraUtilitiesGitRepo:
    """Git repository opener with GitPython native OO API."""

    @staticmethod
    def _registered_worktree_entries(
        porcelain: str,
    ) -> t.VariadicTuple[m.Infra.GitWorktreeEntry]:
        """Parse one ``worktree list --porcelain`` document into typed entries.

        Returns:
            The resulting ``t.VariadicTuple[m.Infra.GitWorktreeEntry]``.

        """
        entries: list[m.Infra.GitWorktreeEntry] = []
        path: Path | None = None
        head: str | None = None
        branch: str | None = None
        detached = False
        bare = False
        locked = False
        for line in (*porcelain.splitlines(), ""):
            if line.startswith("worktree "):
                path = (
                    Path(line.removeprefix("worktree ").strip()).expanduser().resolve()
                )
            elif line.startswith("HEAD "):
                head = line.removeprefix("HEAD ").strip() or None
            elif line.startswith("branch refs/heads/"):
                branch = line.removeprefix("branch refs/heads/").strip() or None
            elif line == "detached":
                detached = True
            elif line == "bare":
                bare = True
            elif line.startswith("locked"):
                locked = True
            elif not line and path is not None:
                entries.append(
                    m.Infra.GitWorktreeEntry(
                        path=path,
                        head=head,
                        branch=branch,
                        detached=detached,
                        bare=bare,
                        locked=locked,
                    ),
                )
                path = None
                head = None
                branch = None
                detached = False
                bare = False
                locked = False
        return tuple(entries)

    @classmethod
    def _worktree_registry(
        cls,
        repo: Repo,
        porcelain: str,
    ) -> t.VariadicTuple[m.Infra.GitWorktreeEntry]:
        """Bind a storage-only primary row to Git-proven checkout identity.

        Returns:
            Typed registry entries with the primary checkout authenticated by Git.

        Raises:
            ValueError: If shared storage cannot be bound to a real primary checkout.

        """
        entries = cls._registered_worktree_entries(porcelain)
        common_dir = Path(
            repo.git.rev_parse(
                c.Infra.GIT_REV_PARSE_ABSOLUTE_PATHS,
                "--git-common-dir",
            ).strip(),
        ).resolve()
        if not entries:
            msg = "Git worktree registry is empty"
            raise ValueError(msg)
        if entries[0].bare or entries[0].path != common_dir:
            return entries
        git_dir = Path(
            repo.git.rev_parse(
                c.Infra.GIT_REV_PARSE_ABSOLUTE_PATHS,
                "--git-dir",
            ).strip(),
        ).resolve()
        if git_dir != common_dir:
            msg = (
                "primary checkout is unproven for storage-only registry row: "
                f"{common_dir}"
            )
            raise ValueError(msg)
        checkout = Path(repo.git.rev_parse("--show-toplevel").strip()).resolve()
        if (
            repo.working_tree_dir is None
            or checkout == common_dir
            or Path(repo.working_tree_dir).resolve() != checkout
            or repo.git.rev_parse("--is-inside-work-tree").strip() != "true"
        ):
            msg = f"Git checkout identity disagrees with shared storage: {common_dir}"
            raise ValueError(msg)
        return (entries[0].model_copy(update={"path": checkout}), *entries[1:])

    @classmethod
    def refresh_binary(cls) -> p.Result[bool]:
        """Point GitPython at the absolute path of the canonical git binary.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        # Git.refresh resolves relative names against cwd; always pass an absolute path.
        resolved = shutil.which(c.Infra.GIT)
        if resolved is None:
            return r[bool].fail(f"git executable not found on PATH: {c.Infra.GIT}")
        try:
            Git.refresh(resolved)
        except (FileNotFoundError, OSError) as exc:
            return r[bool].fail(f"git binary refresh failed: {exc}", exception=exc)
        return r[bool].ok(value=True)

    @classmethod
    def _open_repo(cls, repo_root: Path) -> p.Result[Repo]:
        """Open the non-bare worktree repository containing ``repo_root``.

        The path may name the checkout root, a directory inside it, or a file
        inside it; the repository is the one that contains it. Callers depend
        on that -- ``git_is_work_tree`` and ``git_semantic_identity`` already
        open with the same contract, and one of them documents it as "the same
        nested-path contract as git_open_repo" -- but this opener had lost it,
        so every nested path failed with "cannot open git repository".

        Returns:
            The resulting ``p.Result[Repo]``.

        """
        resolved = repo_root.expanduser().resolve()
        try:
            refreshed = cls.refresh_binary()
            if refreshed.failure:
                return r[Repo].from_failure(refreshed)
            repo = Repo(resolved, search_parent_directories=True)
        except (
            GitCommandNotFound,
            ImportError,
            InvalidGitRepositoryError,
            NoSuchPathError,
            OSError,
            ValueError,
        ) as exc:
            return r[Repo].fail(f"cannot open git repository at {resolved}: {exc}")
        if repo.bare or repo.working_tree_dir is None:
            return r[Repo].fail(f"bare or worktree-less repository at {resolved}")
        return r[Repo].ok(repo)

    @classmethod
    def _repo(cls, repo_root: Path) -> Repo:
        """Open a repo and unwrap, raising on failure.

        This is the canonical helper for semantic methods that prefer
        try/except → ``r[...].fail()`` over ``Result`` chaining.

        Returns:
            The resulting ``Repo``.

        Raises:
            OSError: If ``opened.failure``.

        """
        opened = cls._open_repo(repo_root)
        if opened.failure:
            raise OSError(opened.error or "failed to open git repository")
        return opened.value

    @classmethod
    def _primary_from_config(
        cls,
        common_dir: Path,
        configured_output: str,
    ) -> p.Result[Path]:
        """Resolve the primary root from an explicit ``core.worktree`` setting.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        configured = Path(configured_output)
        primary_root = (
            configured if configured.is_absolute() else common_dir / configured
        ).resolve()
        return r[Path].ok(primary_root)

    @classmethod
    def _primary_from_registry(
        cls,
        repo: Repo,
        common_dir: Path,
        repository_path: Path,
    ) -> p.Result[Path]:
        """Resolve the primary root from Git's worktree registry for shared storage.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        try:
            git_dir = Path(
                repo.git.rev_parse(
                    c.Infra.GIT_REV_PARSE_ABSOLUTE_PATHS, "--git-dir"
                ).strip(),
            ).resolve()
            caller_root = Path(
                repo.git.rev_parse("--show-toplevel").strip(),
            ).resolve()
            entries = (
                ()
                if git_dir == common_dir
                else cls._registered_worktree_entries(
                    repo.git.worktree("list", "--porcelain"),
                )
            )
        except GitCommandError as exc:
            return r[Path].fail(str(exc), exception=exc)
        # Git lists the main worktree first. Bare shared storage has no main
        # checkout, so each registered worktree is its own primary.
        # A composed submodule with core.worktree unset makes Git record
        # the shared module storage (.git/modules/<name>) as the main
        # entry's path — that directory is not a checkout, so it is
        # bare-equivalent and a registered caller is its own primary.
        if git_dir == common_dir:
            return r[Path].ok(caller_root)
        if not entries:
            return r[Path].fail(
                f"Git worktree registry is empty for {repository_path}",
            )
        if not entries[0].bare and not entries[0].path.is_relative_to(common_dir):
            return r[Path].ok(entries[0].path)
        if caller_root in {entry.path for entry in entries}:
            return r[Path].ok(caller_root)
        return r[Path].fail(
            f"current worktree is absent from Git's canonical registry: {caller_root}",
        )

    @classmethod
    def _validated_primary_root(
        cls,
        primary_root: Path,
    ) -> p.Result[Path]:
        """Prove the resolved primary root is a real Git checkout.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        primary_repo = cls._open_repo(primary_root)
        if primary_repo.failure:
            return r[Path].fail(
                f"invalid primary worktree: {primary_root}: {primary_repo.error}",
            )
        try:
            resolved_top = Path(
                primary_repo.value.git.rev_parse("--show-toplevel").strip(),
            ).resolve()
        except GitCommandError as exc:
            return r[Path].fail(
                f"invalid primary worktree: {primary_root}: {exc}",
                exception=exc,
            )
        if resolved_top != primary_root:
            return r[Path].fail(
                f"Git primary worktree mismatch: {primary_root} != {resolved_top}",
            )
        return r[Path].ok(primary_root)

    @classmethod
    def _git_primary_worktree_root_path(cls, repository_path: Path) -> p.Result[Path]:
        """Resolve the primary worktree from Git's shared storage topology.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        try:
            repo = cls._repo(repository_path)
            common_dir = Path(
                repo.git.rev_parse(
                    c.Infra.GIT_REV_PARSE_ABSOLUTE_PATHS,
                    "--git-common-dir",
                ).strip(),
            ).resolve()
            configured_output = repo.git.config(
                "--path",
                "--get",
                "core.worktree",
                with_exceptions=False,
            ).strip()
        except GitCommandError as exc:
            return r[Path].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[Path].fail(
                f"failed to resolve primary worktree: {exc}",
                exception=exc,
            )

        if configured_output:
            primary = cls._primary_from_config(common_dir, configured_output)
        elif common_dir.name == c.Infra.GIT_DIR:
            primary = r[Path].ok(common_dir.parent)
        else:
            primary = cls._primary_from_registry(repo, common_dir, repository_path)
        if primary.failure:
            return primary
        return cls._validated_primary_root(primary.value)


__all__: list[str] = ["FlextInfraUtilitiesGitRepo"]
