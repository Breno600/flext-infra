"""Canonical Git responsibility mixin for ``u.Infra``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from git import GitCommandError, InvalidGitRepositoryError, Repo

from flext_core import r
from flext_infra import m

from .semantic_publish import FlextInfraUtilitiesGitSemanticPublishMixin

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesGitSemanticPathsMixin(
    FlextInfraUtilitiesGitSemanticPublishMixin
):
    """Own semantic paths operations."""

    @classmethod
    def git_init(
        cls, request: m.Infra.GitRepoRequest
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Initialize a new Git repository at ``repo_root``."""
        try:
            Repo.init(request.repo_root).close()
        except (OSError, ValueError, InvalidGitRepositoryError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"git init failed: {exc}", exception=exc
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def git_checkout_restore(
        cls, request: m.Infra.GitRepoRequest
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Restore tracked paths via ``git checkout -- .``."""
        try:
            repo = cls._repo(request.repo_root)
            repo.git.checkout("--", ".")
        except GitCommandError as exc:
            return r[m.Infra.GitBoolReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"git checkout restore failed: {exc}", exception=exc
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def git_mv_path(
        cls, request: m.Infra.GitPathPairRequest
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Move a tracked path with ``git mv``."""
        try:
            repo = cls._repo(request.repo_root)
            repo.index.move([request.source, request.target])
        except GitCommandError as exc:
            return r[m.Infra.GitBoolReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(f"git mv failed: {exc}", exception=exc)
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def git_rm_cached(
        cls, request: m.Infra.GitRelativePathRequest
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Untrack a path with ``git rm --cached``."""
        try:
            repo = cls._repo(request.repo_root)
            repo.index.remove([request.relative_path], cached=True, r=True, f=True)
        except GitCommandError as exc:
            return r[m.Infra.GitBoolReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"git rm --cached failed: {exc}", exception=exc
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def git_rm_path(
        cls, request: m.Infra.GitRelativePathRequest
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Remove a tracked path with ``git rm``."""
        try:
            repo = cls._repo(request.repo_root)
            repo.index.remove([request.relative_path], cached=False, r=True, f=True)
        except GitCommandError as exc:
            return r[m.Infra.GitBoolReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(f"git rm failed: {exc}", exception=exc)
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def git_is_tracked(
        cls, request: m.Infra.GitRelativePathRequest
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Return whether a relative path is git-tracked."""
        try:
            repo = cls._repo(request.repo_root)
            listed = repo.git.ls_files("-z", "--", request.relative_path)
        except GitCommandError:
            return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=False))
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"failed to check tracked status: {exc}", exception=exc
            )
        return r[m.Infra.GitBoolReport].ok(
            m.Infra.GitBoolReport(value=bool(listed.strip()))
        )

    @classmethod
    def git_add_paths(
        cls, request: m.Infra.GitPathsRequest
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Stage multiple paths via ``git add --force``.

        The sole caller is the release stamp stage: it stages exactly the
        paths the preceding ``git status --porcelain`` listed (the preflight
        proved the checkout clean, so every listed path was produced by the
        stamp). ``--force`` is required because generated release artifacts
        may also match ``.gitignore`` projections; ignore rules must never
        silently drop a proven produced path from the release commit.
        """
        try:
            repo = cls._repo(request.repo_root)
            repo.git.add("--force", "--", *request.paths)
        except GitCommandError as exc:
            return r[m.Infra.GitBoolReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"git add failed: {exc}", exception=exc
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def git_restore_paths(
        cls, request: m.Infra.GitCheckoutPathsRequest
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Restore tracked paths via ``git checkout --``."""
        try:
            repo = cls._repo(request.repo_root)
            if request.paths:
                repo.index.checkout(paths=list(request.paths), force=True)
            else:
                repo.git.checkout("--", ".")
        except GitCommandError as exc:
            return r[m.Infra.GitBoolReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"git restore failed: {exc}", exception=exc
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def git_commit(
        cls, request: m.Infra.GitCommitRequest
    ) -> p.Result[m.Infra.GitOidReport]:
        """Create a commit with the staged tree via ``git commit``."""
        try:
            repo = cls._repo(request.repo_root)
            commit = repo.index.commit(request.message)
        except GitCommandError as exc:
            return r[m.Infra.GitOidReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitOidReport].fail(
                f"git commit failed: {exc}", exception=exc
            )
        return r[m.Infra.GitOidReport].ok(m.Infra.GitOidReport(oid=commit.hexsha))


__all__: list[str] = ["FlextInfraUtilitiesGitSemanticPathsMixin"]
