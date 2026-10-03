"""Canonical Git responsibility mixin for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from git import BadName, GitCommandError

from flext_core import r
from flext_infra import c, m
from flext_infra._utilities._git.worktree import FlextInfraUtilitiesGitWorktreeMixin

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesGitSemanticRefsMixin(FlextInfraUtilitiesGitWorktreeMixin):
    """Own semantic refs operations."""

    @classmethod
    def git_list_worktrees(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitWorktreeListReport]:
        """Read Git's canonical worktree registry, parsed once for every consumer.

        Returns:
            The resulting ``p.Result[m.Infra.GitWorktreeListReport]``.

        """
        repo_root = request.repo_root.expanduser().resolve()
        try:
            repo = cls._repo(repo_root)
            porcelain = repo.git.worktree("list", "--porcelain")
        except GitCommandError as exc:
            return r[m.Infra.GitWorktreeListReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitWorktreeListReport].fail(
                f"failed to list Git worktrees: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitWorktreeListReport].ok(
            m.Infra.GitWorktreeListReport(
                root=repo_root,
                entries=cls._registered_worktree_entries(porcelain),
                porcelain=porcelain,
            ),
        )

    @classmethod
    def git_check_branch_format(
        cls,
        request: m.Infra.GitBranchRequest,
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Validate a branch name with ``git check-ref-format --branch``.

        Returns:
            The resulting ``p.Result[m.Infra.GitBoolReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            repo.git.check_ref_format("--branch", request.branch)
        except GitCommandError as exc:
            # check-ref-format documents exit 1 for an invalid name; any other
            # status is a real failure.
            if exc.status == c.Infra.GIT_EXIT_NEGATIVE:
                return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=False))
            return r[m.Infra.GitBoolReport].fail(
                f"failed to validate branch name: {exc}",
                exception=exc,
            )
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"failed to validate branch name: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def git_ref_exists(
        cls,
        request: m.Infra.GitRefRequest,
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Return whether an exact Git ref exists (exit 0/1 only).

        Returns:
            Whether an exact Git ref exists (exit 0/1 only).

        """
        try:
            repo = cls._repo(request.repo_root)
            repo.git.show_ref("--verify", "--quiet", request.reference)
        except GitCommandError as exc:
            # show-ref documents exit 1 for a missing ref; any other status is
            # a real failure.
            if exc.status == c.Infra.GIT_EXIT_NEGATIVE:
                return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=False))
            return r[m.Infra.GitBoolReport].fail(
                f"failed to inspect Git ref: {exc}",
                exception=exc,
            )
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"failed to inspect Git ref: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def git_superproject_working_tree(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitTextReport]:
        """Capture ``rev-parse --show-superproject-working-tree`` stdout.

        Returns:
            The resulting ``p.Result[m.Infra.GitTextReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            text = repo.git.rev_parse("--show-superproject-working-tree")
        except GitCommandError as exc:
            return r[m.Infra.GitTextReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitTextReport].fail(
                f"failed to resolve superproject working tree: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitTextReport].ok(m.Infra.GitTextReport(text=text))

    @classmethod
    def git_show_toplevel(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitRootReport]:
        """Report the resolved top-level directory of the request's worktree.

        Returns:
            The resulting ``p.Result[m.Infra.GitRootReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            root = (
                Path(repo.working_tree_dir).resolve() if repo.working_tree_dir else None
            )
            if root is None:
                return r[m.Infra.GitRootReport].fail(
                    "failed to resolve Git top level: working tree is None",
                )
        except GitCommandError as exc:
            return r[m.Infra.GitRootReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitRootReport].fail(
                f"failed to resolve Git top level: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitRootReport].ok(m.Infra.GitRootReport(repository_root=root))

    @classmethod
    def git_current_branch(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitTextReport]:
        """Resolve the current non-detached branch name.

        Returns:
            The resulting ``p.Result[m.Infra.GitTextReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            branch = repo.active_branch.name
        except GitCommandError as exc:
            return r[m.Infra.GitTextReport].fail(str(exc), exception=exc)
        except (TypeError, OSError, ValueError) as exc:
            # active_branch raises TypeError on detached HEAD.
            return r[m.Infra.GitTextReport].fail(
                f"head branch is required from a detached HEAD: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitTextReport].ok(m.Infra.GitTextReport(text=branch))

    @classmethod
    def git_resolve_commit(
        cls,
        request: m.Infra.GitCommitishRequest,
    ) -> p.Result[m.Infra.GitOidReport]:
        """Resolve a commit-ish to its commit oid, failing on a non-commit name.

        Returns:
            The resulting ``p.Result[m.Infra.GitOidReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            oid = repo.commit(request.commitish).hexsha
        except (BadName, GitCommandError) as exc:
            return r[m.Infra.GitOidReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitOidReport].fail(
                f"cannot resolve commitish: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitOidReport].ok(m.Infra.GitOidReport(oid=oid))

    @classmethod
    def git_is_ancestor(
        cls,
        request: m.Infra.GitAncestryRequest,
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Return whether ``ancestor`` is an ancestor of ``descendant``.

        One owner proves ancestry for any pair. ``descendant`` defaults to
        ``HEAD``, so the HEAD-bound proof existing consumers relied on is a
        use of this verb, not a separate one.

        Returns:
            Whether ``ancestor`` is an ancestor of ``descendant``.

        """
        try:
            repo = cls._repo(request.repo_root)
            result = repo.is_ancestor(
                repo.commit(request.ancestor),
                repo.commit(request.descendant),
            )
        except (BadName, GitCommandError) as exc:
            return r[m.Infra.GitBoolReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"failed to inspect ancestry: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=result))

    @classmethod
    def git_rev_parse(
        cls,
        request: m.Infra.GitCommitishRequest,
    ) -> p.Result[m.Infra.GitOidReport]:
        """Resolve an arbitrary rev-parse argument to stripped text oid.

        Returns:
            The resulting ``p.Result[m.Infra.GitOidReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            oid = repo.git.rev_parse(request.commitish).strip()
        except GitCommandError as exc:
            return r[m.Infra.GitOidReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitOidReport].fail(
                f"rev-parse failed for {request.commitish}: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitOidReport].ok(m.Infra.GitOidReport(oid=oid))

    @classmethod
    def git_ref_heads(
        cls,
        request: m.Infra.GitRefHeadsRequest,
    ) -> p.Result[m.Infra.GitRefHeadsReport]:
        """Map every ref below ``namespace`` to its tip oid.

        Names are relative to the namespace; the symbolic remote ``HEAD`` is
        an alias of another listed ref and is left out.

        Returns:
            The resulting ``p.Result[m.Infra.GitRefHeadsReport]``.

        """
        prefix = f"{request.namespace.rstrip('/')}/"
        try:
            repo = cls._repo(request.repo_root)
            text = repo.git.for_each_ref("--format=%(refname)%00%(objectname)", prefix)
        except GitCommandError as exc:
            return r[m.Infra.GitRefHeadsReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitRefHeadsReport].fail(
                f"failed to list refs below {request.namespace}: {exc}",
                exception=exc,
            )
        heads = {
            name.removeprefix(prefix): oid
            for name, _, oid in (line.partition("\0") for line in text.splitlines())
            if name.removeprefix(prefix) != c.Infra.GIT_HEAD
        }
        return r[m.Infra.GitRefHeadsReport].ok(m.Infra.GitRefHeadsReport(heads=heads))

    @classmethod
    def git_stash_oids(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitOidListReport]:
        """List the stash commits, newest (``stash@{0}``) first.

        Returns:
            The resulting ``p.Result[m.Infra.GitOidListReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            text = repo.git.stash("list", "--format=%H")
        except GitCommandError as exc:
            return r[m.Infra.GitOidListReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitOidListReport].fail(
                f"failed to list stash entries: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitOidListReport].ok(
            m.Infra.GitOidListReport(oids=tuple(text.split()))
        )

    @classmethod
    def git_remote_branch_oid(
        cls,
        request: m.Infra.GitRemoteBranchRequest,
    ) -> p.Result[m.Infra.GitTextReport]:
        """Ask the remote itself for one branch tip; empty text means absent.

        Unlike a remote-tracking ref this is the live remote state, so it
        proves a publication rather than remembering one.

        Returns:
            The resulting ``p.Result[m.Infra.GitTextReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            text = repo.git.ls_remote(
                "--heads", request.remote, f"refs/heads/{request.branch}"
            )
        except GitCommandError as exc:
            return r[m.Infra.GitTextReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitTextReport].fail(
                f"failed to query {request.remote} for {request.branch}: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitTextReport].ok(
            m.Infra.GitTextReport(text=text.partition("\t")[0].strip())
        )

    @classmethod
    def git_merge_is_noop(
        cls,
        request: m.Infra.GitMergeProbeRequest,
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Whether merging ``commitish`` into ``base`` leaves its tree unchanged.

        This proves a squash- or rebase-merged branch is already contained in
        ``base`` without touching the index or worktree; a conflicting merge
        is not a no-op.

        Returns:
            The resulting ``p.Result[m.Infra.GitBoolReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            merged = repo.git.merge_tree(
                "--write-tree", request.base, request.commitish
            ).splitlines()[0]
            base_tree = repo.git.rev_parse(f"{request.base}^{{tree}}").strip()
        except GitCommandError as exc:
            if exc.status == c.Infra.GIT_EXIT_NEGATIVE:
                return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=False))
            return r[m.Infra.GitBoolReport].fail(str(exc), exception=exc)
        except (OSError, ValueError, IndexError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"merge probe failed for {request.commitish}: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitBoolReport].ok(
            m.Infra.GitBoolReport(value=merged.strip() == base_tree)
        )

    @classmethod
    def git_last_activity(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitTimestampReport]:
        """Newest of the HEAD commit time and this worktree's last HEAD move.

        The HEAD reflog is per worktree, so checkouts, commits, resets and
        rebases in one linked worktree never age or refresh another.

        Returns:
            The resulting ``p.Result[m.Infra.GitTimestampReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            committed = int(repo.git.log("-1", "--format=%ct", "HEAD").strip())
            moved = repo.git.log(
                "--walk-reflogs", "-1", "--date=unix", "--format=%gd", "HEAD"
            ).strip()
        except GitCommandError as exc:
            return r[m.Infra.GitTimestampReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitTimestampReport].fail(
                f"failed to read last activity: {exc}",
                exception=exc,
            )
        stamp = moved.partition("@{")[2].rstrip("}")
        latest = max(committed, int(stamp)) if stamp.isdigit() else committed
        return r[m.Infra.GitTimestampReport].ok(
            m.Infra.GitTimestampReport(epoch_seconds=latest)
        )


__all__: list[str] = ["FlextInfraUtilitiesGitSemanticRefsMixin"]
