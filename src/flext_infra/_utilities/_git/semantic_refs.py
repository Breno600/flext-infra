"""Canonical Git responsibility mixin for ``u.Infra``."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from git import BadName, GitCommandError

from flext_core import r
from flext_infra import c, m

from .worktree import FlextInfraUtilitiesGitWorktreeMixin

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesGitSemanticRefsMixin(FlextInfraUtilitiesGitWorktreeMixin):
    """Own semantic refs operations."""

    @classmethod
    def git_list_worktrees(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitWorktreeListReport]:
        """Read Git's canonical worktree registry, parsed once for every consumer."""
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
        """Validate a branch name with ``git check-ref-format --branch``."""
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
        """Return whether an exact Git ref exists (exit 0/1 only)."""
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
        """Capture ``rev-parse --show-superproject-working-tree`` stdout."""
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
        """Report the resolved top-level directory of the request's worktree."""
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
        """Resolve the current non-detached branch name."""
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
        """Resolve a commit-ish to its commit oid, failing on a non-commit name."""
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
        """Resolve an arbitrary rev-parse argument to stripped text oid."""
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


__all__: list[str] = ["FlextInfraUtilitiesGitSemanticRefsMixin"]
