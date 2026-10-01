"""Canonical publication lane for ``u.Infra``: produced paths to one pull request."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_cli import u

from flext_core import r
from flext_infra import c, m

from .semantic_worktree import FlextInfraUtilitiesGitSemanticWorktreeMixin

if TYPE_CHECKING:
    from collections.abc import Callable

    from flext_infra import p


class FlextInfraUtilitiesGitSemanticLaneMixin(
    FlextInfraUtilitiesGitSemanticWorktreeMixin
):
    """Own the lane every repository publication shares (release, propagation)."""

    @classmethod
    def git_publish_lane(
        cls, request: m.Infra.GitLaneRequest, produce: Callable[[], p.Result[bool]]
    ) -> p.Result[bool]:
        """Carry what ``produce`` writes from ``base`` to a pull request on ``branch``.

        The checkout must be clean on ``base``, so every path the status lists
        after ``produce`` was produced by it; exactly those paths are committed
        under ``subject``, the lane is pushed, and its pull request is opened or
        updated. A rerun continues the open lane (local or remote), merges
        ``base`` in, reproduces identical bytes and commits nothing. A lane
        that carries nothing beyond ``base`` publishes nothing: the checkout
        returns to ``base``, the empty lane branch is removed, and the result
        is ``False``.
        """
        root = request.repo_root
        status = cls.git_status(m.Infra.GitStatusRequest(repo_root=root))
        if status.failure:
            return r[bool].from_failure(status)
        if status.value.dirty:
            return r[bool].fail(
                f"lane {request.branch} requires a clean checkout: {root}\n"
                f"{status.value.porcelain}"
            )
        current = cls.git_current_branch(m.Infra.GitRepoRequest(repo_root=root))
        if current.failure:
            return r[bool].from_failure(current)
        if current.value.text != request.base:
            return r[bool].fail(
                f"lane {request.branch} starts from {request.base}, "
                f"not {current.value.text}"
            )
        for step in (
            lambda: cls._git_enter_lane(request),
            produce,
            lambda: cls._git_commit_produced(request),
        ):
            outcome = step()
            if outcome.failure:
                return outcome
        ahead = u.Cli.capture(
            [c.Infra.GIT, "rev-list", "--count", f"{request.base}..{request.branch}"],
            cwd=root,
        )
        if ahead.failure:
            return r[bool].from_failure(ahead)
        if ahead.value.strip() == "0":
            return cls._git_discard_empty_lane(request)
        return cls._git_open_pull_request(request)

    @classmethod
    def _git_discard_empty_lane(cls, request: m.Infra.GitLaneRequest) -> p.Result[bool]:
        """Return to ``base`` and remove the lane branch that carries nothing."""
        root = request.repo_root
        for command in (
            [c.Infra.GIT, "switch", request.base],
            [c.Infra.GIT, "branch", "--delete", request.branch],
        ):
            outcome = u.Cli.run_checked(command, cwd=root)
            if outcome.failure:
                return outcome
        return r[bool].ok(False)

    @classmethod
    def _git_enter_lane(cls, request: m.Infra.GitLaneRequest) -> p.Result[bool]:
        """Continue the lane where it exists (local, then remote), else start it at HEAD."""
        root, branch = request.repo_root, request.branch
        local = u.Cli.capture(
            [c.Infra.GIT, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=root,
        )
        fetched = u.Cli.run_checked(
            [c.Infra.GIT, "fetch", c.Infra.GIT_ORIGIN, branch], cwd=root
        )
        if local.success:
            switched = u.Cli.run_checked([c.Infra.GIT, "switch", branch], cwd=root)
        elif fetched.success:
            switched = u.Cli.run_checked(
                [
                    c.Infra.GIT,
                    "switch",
                    "--create",
                    branch,
                    f"refs/remotes/{c.Infra.GIT_ORIGIN}/{branch}",
                ],
                cwd=root,
            )
        else:
            return u.Cli.run_checked(
                [c.Infra.GIT, "switch", "--create", branch], cwd=root
            )
        if switched.failure:
            return switched
        return cls.git_merge_no_edit(
            m.Infra.GitCommitishRequest(repo_root=root, commitish=request.base)
        ).map(lambda _report: True)

    @classmethod
    def _git_commit_produced(cls, request: m.Infra.GitLaneRequest) -> p.Result[bool]:
        """Commit exactly the paths the status lists; nothing produced commits nothing."""
        root = request.repo_root
        status = cls.git_status(m.Infra.GitStatusRequest(repo_root=root))
        if status.failure:
            return r[bool].from_failure(status)
        # The status code and the path are whitespace-separated; the first
        # line arrives without its leading status padding.
        produced = tuple(
            line.split(maxsplit=1)[1]
            for line in status.value.porcelain.splitlines()
            if line.strip()
        )
        if not produced:
            return r[bool].ok(True)
        staged = cls.git_add_paths(
            m.Infra.GitPathsRequest(repo_root=root, paths=produced)
        )
        if staged.failure:
            return r[bool].from_failure(staged)
        return cls.git_commit(
            m.Infra.GitCommitRequest(repo_root=root, message=request.subject)
        ).map(lambda _report: True)

    @classmethod
    def _git_open_pull_request(cls, request: m.Infra.GitLaneRequest) -> p.Result[bool]:
        """Push the lane, then open its pull request or refresh the open one."""
        root, branch = request.repo_root, request.branch
        pushed = cls.git_push_upstream(
            m.Infra.GitPushRequest(repo_root=root, branch=branch)
        )
        if pushed.failure:
            return r[bool].from_failure(pushed)
        exists = u.Cli.capture(
            [c.Infra.GH, "pr", "view", branch, "--json", "number"], cwd=root
        )
        command = (
            [c.Infra.GH, "pr", "edit", branch]
            if exists.success
            else [c.Infra.GH, "pr", "create", "--base", request.base, "--head", branch]
        )
        return u.Cli.run_checked(
            [
                *command,
                "--title",
                request.subject,
                "--body-file",
                str(request.body_file),
            ],
            cwd=root,
        )


__all__: list[str] = ["FlextInfraUtilitiesGitSemanticLaneMixin"]
