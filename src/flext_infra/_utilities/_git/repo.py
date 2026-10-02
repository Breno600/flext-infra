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
from typing import TYPE_CHECKING

from git import (
    Git,
    GitCommandError,
    GitCommandNotFound,
    InvalidGitRepositoryError,
    NoSuchPathError,
    Repo,
)

from flext_core import r
from flext_infra import c, m

if TYPE_CHECKING:
    from flext_infra import p, t


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
    def refresh_binary(cls) -> p.Result[bool]:
        """Point GitPython at the absolute path of the canonical git binary.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        # Git.refresh resolves relative names against cwd; always pass an absolute path.
        resolved = shutil.which(c.Infra.GIT)
        if resolved is None:
            return r[bool].fail(f"git executable not found on PATH: {c.Infra.GIT}")
        # GitPython's documented executable attribute already names this
        # binary: re-pointing it would only respawn ``git version``.
        if resolved == Git.GIT_PYTHON_GIT_EXECUTABLE:
            return r[bool].ok(True)
        try:
            Git.refresh(resolved)
        except (FileNotFoundError, OSError) as exc:
            return r[bool].fail(f"git binary refresh failed: {exc}", exception=exc)
        return r[bool].ok(True)

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
    def _git_primary_worktree_root_path(cls, repository_path: Path) -> p.Result[Path]:
        """Resolve the primary worktree from Git's shared storage topology.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        try:
            repo = cls._repo(repository_path)
            common_dir = Path(
                repo.git.rev_parse(
                    "--path-format=absolute",
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
            configured = Path(configured_output)
            primary_root = (
                configured if configured.is_absolute() else common_dir / configured
            ).resolve()
        elif common_dir.name == c.Infra.GIT_DIR:
            primary_root = common_dir.parent
        else:
            try:
                git_dir = Path(
                    repo.git.rev_parse("--path-format=absolute", "--git-dir").strip(),
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
            # Git lists the main worktree first. Bare shared storage, or a main
            # entry that is the common git dir itself (a submodule module dir
            # without core.worktree), has no main checkout, so each registered
            # worktree is its own primary.
            if git_dir == common_dir:
                primary_root = caller_root
            elif not entries:
                return r[Path].fail(
                    f"Git worktree registry is empty for {repository_path}",
                )
            elif not entries[0].bare and entries[0].path != common_dir:
                primary_root = entries[0].path
            elif caller_root in {entry.path for entry in entries}:
                primary_root = caller_root
            else:
                return r[Path].fail(
                    "current worktree is absent from Git's canonical registry: "
                    f"{caller_root}",
                )

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


__all__: list[str] = ["FlextInfraUtilitiesGitRepo"]
