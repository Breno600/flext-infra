"""Canonical Git responsibility mixin for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from git import GitCommandError, Repo

from flext_infra import c, m, r, t
from flext_infra._utilities._git.repo import FlextInfraUtilitiesGitRepo

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesGitWorktreeStatusMixin(FlextInfraUtilitiesGitRepo):
    """Own worktree status operations."""

    @classmethod
    def _lifecycle_porcelain(cls, repo: Repo, repo_path: Path, porcelain: str) -> str:
        registered = {
            entry.path
            for entry in cls._registered_worktree_entries(
                repo.git.worktree("list", "--porcelain"),
            )
        }
        administrative = {
            path.relative_to(repo_path).as_posix().rstrip("/")
            for path in registered
            if path != repo_path and path.is_relative_to(repo_path)
        }
        retained: list[str] = []
        for line in porcelain.splitlines():
            candidate = (
                line[c.Infra.GIT_PORCELAIN_PATH_OFFSET :].rstrip("/")
                if len(line) > c.Infra.GIT_PORCELAIN_PATH_OFFSET
                else ""
            )
            if line.startswith("?? ") and candidate in administrative:
                continue
            retained.append(line)
        return "\n".join(retained)

    @classmethod
    def git_status(
        cls,
        request: m.Infra.GitStatusRequest,
    ) -> p.Result[m.Infra.GitStatusReport]:
        """Capture porcelain status for one repository.

        The report carries the lifecycle porcelain (registered nested worktrees
        excluded) so ``dirty`` and every consumer reading ``porcelain`` grade
        the same lines; administrative worktrees are never repository change.

        Returns:
            The resulting ``p.Result[m.Infra.GitStatusReport]``.

        """
        repo_path = request.repo_root.expanduser().resolve()
        try:
            repo = cls._repo(repo_path)
            lifecycle = cls._lifecycle_porcelain(
                repo,
                repo_path,
                repo.git.status("--porcelain", "--untracked-files=all"),
            )
        except GitCommandError as exc:
            return r[m.Infra.GitStatusReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitStatusReport].fail(
                f"git status failed: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitStatusReport].ok(
            m.Infra.GitStatusReport(
                repo_root=repo_path,
                porcelain=lifecycle,
                dirty=bool(lifecycle.strip()),
            ),
        )

    @classmethod
    def git_repository_head(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitOidReport]:
        """Capture the current repository HEAD as a typed oid report.

        Returns:
            The resulting ``p.Result[m.Infra.GitOidReport]``.

        """
        oid = cls._git_head_oid(request.repo_root)
        if oid.failure:
            return r[m.Infra.GitOidReport].from_failure(oid)
        return r[m.Infra.GitOidReport].ok(m.Infra.GitOidReport(oid=oid.value))

    @classmethod
    def git_changed_paths(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[t.SequenceOf[Path]]:
        """Return every existing staged, unstaged, or untracked path in one repo.

        Returns:
            Every existing staged, unstaged, or untracked path in one repo.

        """
        repo_path = request.repo_root.expanduser().resolve()
        try:
            repo = cls._repo(repo_path)
            changed = tuple(
                name
                for name in repo.git.diff("--name-only", "-z", "HEAD", "--").split("\0")
                if name
            )
            relative_paths = tuple(dict.fromkeys((*changed, *repo.untracked_files)))
        except GitCommandError as exc:
            return r[t.SequenceOf[Path]].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[t.SequenceOf[Path]].fail(
                f"git changed paths failed: {exc}",
                exception=exc,
            )
        return r[t.SequenceOf[Path]].ok(
            tuple(
                path
                for relative_path in relative_paths
                if (path := (repo_path / relative_path).resolve()).is_file()
            ),
        )

    @classmethod
    def _git_head_oid(cls, repo_root: Path) -> p.Result[str]:
        """Private Path-based HEAD oid resolver for facet-internal callers.

        Returns:
            The resulting ``p.Result[str]``.

        """
        opened = cls._open_repo(repo_root)
        if opened.failure:
            return r[str].from_failure(opened)
        try:
            return r[str].ok(opened.value.head.commit.hexsha)
        except (ValueError, TypeError, OSError) as exc:
            return r[str].fail(f"failed to resolve HEAD: {exc}", exception=exc)

    @classmethod
    def git_has_staged_changes(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Return whether the index carries changes staged for the next commit.

        ``git diff --cached --quiet`` exits 0 with nothing staged and 1 with a
        staged delta; every other exit is the failure it is. Callers that must
        choose between committing and a NOOP consume this instead of probing
        the raw command themselves.

        Returns:
            Whether the index carries changes staged for the next commit.

        """
        repo_path = request.repo_root.expanduser().resolve()
        try:
            repo = cls._repo(repo_path)
            status, _out, _err = repo.git.diff(
                "--cached",
                "--quiet",
                with_extended_output=True,
                with_exceptions=False,
            )
        except GitCommandError as exc:
            return r[m.Infra.GitBoolReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"failed to inspect staged state: {exc}",
                exception=exc,
            )
        if status == 0:
            return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=False))
        if status == 1:
            return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))
        return r[m.Infra.GitBoolReport].fail(
            f"git diff --cached --quiet exited {status}: {repo_path}",
        )


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreeStatusMixin"]
