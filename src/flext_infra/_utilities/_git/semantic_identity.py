"""Canonical Git responsibility mixin for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from git import (
    GitCommandError,
    GitCommandNotFound,
    InvalidGitRepositoryError,
    NoSuchPathError,
    Repo,
)

from flext_infra import c, m, p, r, t
from flext_infra._utilities import (
    FlextInfraUtilitiesGitRemote,
    FlextInfraUtilitiesGitRepo,
)
from flext_infra._utilities._git.semantic_lane import (
    FlextInfraUtilitiesGitSemanticLaneMixin,
)


class FlextInfraUtilitiesGitSemanticIdentityMixin(
    FlextInfraUtilitiesGitSemanticLaneMixin,
):
    """Own semantic identity operations."""

    @classmethod
    def git_identity(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitIdentityReport]:
        """Return consolidated Git identity for one repository path.

        One call replaces 6+ separate queries. Implemented over GitPython
        native OO API.

        Returns:
            Consolidated Git identity for one repository path.

        """
        try:
            repo = cls._repo(request.repo_root)
            if cls._git_head_is_unborn(repo):
                return r[m.Infra.GitIdentityReport].fail(
                    f"Git repository has no committed HEAD: "
                    f"{request.repo_root.resolve()}",
                    error_code=c.Infra.GIT_UNBORN_HEAD_ERROR_CODE,
                )
            primary = cls._git_primary_worktree_root_path(request.repo_root)
            if primary.failure:
                return r[m.Infra.GitIdentityReport].from_failure(primary)
            report = cls._collect_identity_facts(
                repo,
                primary_root=primary.value,
                requested_path=request.repo_root,
            )
        except GitCommandError as exc:
            return r[m.Infra.GitIdentityReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitIdentityReport].fail(
                f"failed to resolve Git identity: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitIdentityReport].ok(report)

    @staticmethod
    def _git_head_is_unborn(repo: Repo) -> bool:
        """Distinguish an absent symbolic branch from broken refs or objects.

        Returns:
            The resulting ``bool``.

        Raises:
            GitCommandError: If ``status``.
            TypeError: If symbolic-ref returned a non-text reference.

        """
        if repo.head.is_valid():
            return False
        branch_ref = repo.git.symbolic_ref("--quiet", "HEAD")
        if not isinstance(branch_ref, str):
            msg = "symbolic-ref returned a non-text reference"
            raise TypeError(msg)
        status, stdout, stderr = repo.git.show_ref(
            "--exists",
            branch_ref,
            with_extended_output=True,
            with_exceptions=False,
        )
        if status == c.Infra.GIT_REF_MISSING_EXIT_CODE:
            return branch_ref.startswith(c.Infra.GIT_REFS_HEADS)
        if status:
            raise GitCommandError(
                ["git", "show-ref", "--exists", branch_ref],
                status,
                stderr=stderr,
                stdout=stdout,
            )
        return False

    @classmethod
    def exact_worktree_root(
        cls,
        requested: Path,
    ) -> p.Result[m.Infra.GitIdentityReport]:
        """Reject Git parent discovery and unregistered nesting under a root.

        Promoted from the Mise workspace planner (`flext-infra` `init` needed
        the identical exact-root contract): the requested path must be the
        resolved repository root itself, and — unless it is a genuine linked
        worktree or a real Git submodule — no ancestor directory may itself be
        a separate Git repository. An unregistered nested ``.git`` (a plain
        ``git init`` under an existing checkout) satisfies "requested == root"
        on its own but is never the exact worktree root callers intend.

        Returns:
            The resulting ``p.Result[m.Infra.GitIdentityReport]``.

        """
        identity = cls.git_identity(m.Infra.GitRepoRequest(repo_root=requested))
        if identity.failure:
            return r[m.Infra.GitIdentityReport].from_failure(identity)
        if identity.value.repo_root != requested:
            return r[m.Infra.GitIdentityReport].fail(
                "Git request is not the exact Git worktree root: "
                f"requested={requested} resolved={identity.value.repo_root}",
            )
        if identity.value.is_submodule or identity.value.is_worktree:
            return identity
        parent = requested.parent
        if parent != requested:
            outer = cls.git_identity(m.Infra.GitRepoRequest(repo_root=parent))
            if outer.success:
                return r[m.Infra.GitIdentityReport].fail(
                    "Git request is nested inside another Git repository and is "
                    "not a registered submodule or linked worktree: "
                    f"requested={requested} outer={outer.value.repo_root}",
                )
        return identity

    @classmethod
    def git_is_inside_work_tree(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Return whether ``repo_root`` sits inside a Git work tree.

        Three-way contract mirroring ``rev-parse --is-inside-work-tree``:
        ``ok(False)`` when no repository owns the path (the expected
        non-error case), ``fail`` only on genuine probe errors.

        Returns:
            Whether ``repo_root`` sits inside a Git work tree.

        """
        refreshed = FlextInfraUtilitiesGitRepo.refresh_binary()
        if refreshed.failure:
            return r[m.Infra.GitBoolReport].from_failure(refreshed)
        resolved = request.repo_root.expanduser().resolve()
        try:
            # Why: same nested-path contract as git_open_repo.
            repo = Repo(resolved, search_parent_directories=True)
        except InvalidGitRepositoryError:
            return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=False))
        except NoSuchPathError:
            return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=False))
        except (GitCommandNotFound, OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"failed to probe Git work tree: {exc}",
                exception=exc,
            )
        # GitPython pins a `git cat-file` child per open handle: the probe owns
        # its handle, so it is released before the report leaves the boundary.
        try:
            return r[m.Infra.GitBoolReport].ok(
                m.Infra.GitBoolReport(
                    value=not repo.bare and repo.working_tree_dir is not None,
                ),
            )
        finally:
            repo.close()

    @classmethod
    def _redacted_remotes(cls, repo: Repo) -> t.Pair[str | None, str | None]:
        """Return the redacted origin and upstream remote URLs.

        Returns:
            The resulting ``(origin, upstream)`` redacted remote URL pair.

        """
        remotes = {remote.name: remote.url for remote in repo.remotes}
        origin = remotes.get("origin")
        upstream = remotes.get("upstream")
        return (
            FlextInfraUtilitiesGitRemote.redact_origin_remote(origin)
            if origin
            else None,
            FlextInfraUtilitiesGitRemote.redact_origin_remote(upstream)
            if upstream
            else None,
        )

    @classmethod
    def _superproject_root(
        cls,
        repo: Repo,
        *,
        primary_root: Path,
        working_tree: Path,
    ) -> Path | None:
        """Resolve the superproject working tree, probing the primary handle.

        Returns:
            The resulting ``Path | None``.

        """
        raw_super = repo.git.rev_parse("--show-superproject-working-tree").strip()
        if not raw_super and primary_root != working_tree:
            primary_repo = cls._repo(primary_root)
            try:
                raw_super = primary_repo.git.rev_parse(
                    "--show-superproject-working-tree",
                ).strip()
            finally:
                # The secondary handle is only opened for this one probe; every
                # open GitPython handle pins a `git cat-file` child.
                primary_repo.close()
        return Path(raw_super).resolve() if raw_super else None

    @staticmethod
    def _has_gitlink_stages(repo: Repo) -> bool:
        """Report whether the index stages any gitlink (submodule) entry.

        Returns:
            The resulting ``bool``.

        """
        staged_entries = repo.git.ls_files("--stage")
        return any(
            line.startswith(f"{c.Infra.GIT_GITLINK_MODE_TEXT} ")
            for line in staged_entries.splitlines()
        )

    @classmethod
    def _collect_identity_facts(
        cls,
        repo: Repo,
        *,
        primary_root: Path,
        requested_path: Path | None = None,
    ) -> m.Infra.GitIdentityReport:
        """Collect GitPython-native identity facts into one report.

        Returns:
            The resulting ``m.Infra.GitIdentityReport``.

        """
        head_oid = repo.head.commit.hexsha
        working_tree = Path(repo.working_tree_dir or str(repo.working_dir)).resolve()
        git_dir = Path(repo.git_dir).resolve()
        common_dir = Path(repo.common_dir).resolve()
        porcelain = repo.git.status("--porcelain", "--untracked-files=all")
        branch = None if repo.head.is_detached else repo.active_branch.name
        origin_remote, upstream_remote = cls._redacted_remotes(repo)
        superproject = cls._superproject_root(
            repo,
            primary_root=primary_root,
            working_tree=working_tree,
        )

        is_worktree = git_dir != common_dir
        # Gitlink modes live in the index, never in `status --porcelain` (which
        # emits XY status codes and paths, never file modes). Reading them from
        # the porcelain text made has_submodules unconditionally False, so a
        # real submodule superproject was never recognized as one.
        has_submodules = cls._has_gitlink_stages(repo)
        # Why: git rev-parse --show-superproject-
        # working-tree already means "this working tree is a submodule".
        # Requiring .git to be a gitfile excluded absorbed/converted submodules
        # whose .git is a real directory, so is_submodule stayed False and
        # consumers demoted them to unmanaged.
        is_submodule = superproject is not None
        is_attached_submodule = (
            superproject is not None and working_tree.is_relative_to(superproject)
        )

        return m.Infra.GitIdentityReport(
            repo_root=working_tree,
            primary_root=primary_root,
            head_oid=head_oid,
            porcelain=porcelain,
            dirty=bool(porcelain.strip()),
            git_dir=git_dir,
            common_dir=common_dir,
            branch=branch,
            origin_remote=origin_remote,
            upstream_remote=upstream_remote,
            is_inside_work_tree=True,
            superproject_root=superproject,
            requested_path=requested_path,
            is_worktree=is_worktree,
            is_submodule=is_submodule,
            is_attached_submodule=is_attached_submodule,
            has_submodules=has_submodules,
        )


__all__: list[str] = ["FlextInfraUtilitiesGitSemanticIdentityMixin"]
