"""Canonical Git responsibility mixin for ``u.Infra``.

Lane hygiene census: stashes, merged-but-alive branches and orphan or merged
linked worktrees, judged offline against the local ``origin/HEAD`` integration
base exactly as the refs stand.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from git import BadName, GitCommandError, Repo

from flext_core import r
from flext_infra import c, m, p, t
from flext_infra._utilities._git.worktree_status import FlextInfraUtilitiesGitWorktreeStatusMixin


class FlextInfraUtilitiesGitLaneHygieneMixin(
    FlextInfraUtilitiesGitWorktreeStatusMixin,
):
    """Own the lane accumulation census of one repository."""

    @classmethod
    def git_lane_hygiene(
        cls,
        request: m.Infra.GitStatusRequest,
    ) -> p.Result[m.Infra.GitLaneHygieneReport]:
        """Census every stash, merged branch and orphan or merged linked worktree.

        The integration base is the local ``refs/remotes/origin/HEAD`` symbolic
        ref; its absence is a failure, never a guessed branch. Nothing is
        fetched: the census judges the local refs as they are.

        Returns:
            The resulting ``p.Result[m.Infra.GitLaneHygieneReport]``.

        """
        repo_path = request.repo_root.expanduser().resolve()
        opened = cls._open_repo(repo_path)
        if opened.failure:
            return r[m.Infra.GitLaneHygieneReport].from_failure(opened)
        base = cls._lane_integration_base(opened.value, repo_path)
        if base.failure:
            return r[m.Infra.GitLaneHygieneReport].from_failure(base)
        refs = cls._lane_refs(opened.value, base.value)
        if refs.failure:
            return r[m.Infra.GitLaneHygieneReport].from_failure(refs)
        stashes, merged_branches, entries = refs.value
        worktrees = cls._lane_worktree_violations(
            opened.value,
            repo_path,
            base.value,
            entries[1:],
        )
        if worktrees.failure:
            return r[m.Infra.GitLaneHygieneReport].from_failure(worktrees)
        kind = c.Infra.LaneViolationKind
        return r[m.Infra.GitLaneHygieneReport].ok(
            m.Infra.GitLaneHygieneReport(
                repo_root=repo_path,
                integration_base=base.value,
                violations=(
                    *(cls._lane_violation(kind.STASH, ref) for ref in stashes),
                    *(
                        cls._lane_violation(kind.MERGED_BRANCH, ref)
                        for ref in merged_branches
                    ),
                    *worktrees.value,
                ),
            ),
        )

    @staticmethod
    def _lane_violation(
        kind: c.Infra.LaneViolationKind,
        ref: str,
    ) -> m.Infra.GitLaneViolation:
        """Bind one offender to its class and the canonical fix instruction.

        Returns:
            The resulting ``m.Infra.GitLaneViolation``.

        """
        return m.Infra.GitLaneViolation(
            kind=kind,
            ref=ref,
            detail=c.Infra.GIT_LANE_VIOLATION_REMEDY[kind].format(ref=ref),
        )

    @staticmethod
    def _lane_integration_base(repo: Repo, repo_path: Path) -> p.Result[str]:
        """Resolve ``origin/HEAD`` to its short remote branch, never guessing.

        ``symbolic-ref --quiet`` exits non-zero without output when the ref is
        absent or not symbolic; that documented absence is the failure.

        Returns:
            The resulting ``p.Result[str]``.

        """
        origin_head = (
            f"{c.Infra.GIT_REFS_REMOTES}{c.Infra.GIT_ORIGIN}/{c.Infra.GIT_HEAD}"
        )
        try:
            status, symbolic, _err = repo.git.symbolic_ref(
                "--quiet",
                "--short",
                origin_head,
                with_extended_output=True,
                with_exceptions=False,
            )
        except (GitCommandError, OSError, ValueError) as exc:
            return r[str].fail(f"cannot read {origin_head}: {exc}", exception=exc)
        if status != 0 or not symbolic.strip():
            return r[str].fail(
                f"integration base unresolved: {origin_head} is not a symbolic"
                f" ref in {repo_path}; declare it with"
                f" git remote set-head {c.Infra.GIT_ORIGIN} <integration-branch>",
            )
        return r[str].ok(symbolic.strip())

    @classmethod
    def _lane_refs(
        cls,
        repo: Repo,
        base: str,
    ) -> p.Result[
        t.Triple[
            t.StrSequence,
            t.StrSequence,
            t.VariadicTuple[m.Infra.GitWorktreeEntry],
        ]
    ]:
        """Collect stash entries, merged idle branches and the worktree registry.

        A branch is idle when it is neither the integration branch nor checked
        out by any registered worktree.

        Returns:
            Stash selectors, merged idle branch names and worktree entries.

        """
        result_type = r[
            t.Triple[
                t.StrSequence,
                t.StrSequence,
                t.VariadicTuple[m.Infra.GitWorktreeEntry],
            ]
        ]
        base_branch = base.removeprefix(f"{c.Infra.GIT_ORIGIN}/")
        try:
            base_commit = repo.commit(base)
            stashes = tuple(repo.git.stash("list", "--format=%gd").split())
            entries = cls._registered_worktree_entries(
                repo.git.worktree("list", "--porcelain"),
            )
            busy = {base_branch, *(entry.branch for entry in entries if entry.branch)}
            merged = tuple(
                head.name
                for head in repo.heads
                if head.name not in busy and repo.is_ancestor(head.commit, base_commit)
            )
        except (BadName, GitCommandError) as exc:
            return result_type.fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return result_type.fail(f"git lane refs failed: {exc}", exception=exc)
        return result_type.ok((stashes, merged, entries))

    @classmethod
    def _lane_worktree_violations(
        cls,
        repo: Repo,
        repo_path: Path,
        base: str,
        linked: t.VariadicTuple[m.Infra.GitWorktreeEntry],
    ) -> p.Result[t.VariadicTuple[m.Infra.GitLaneViolation]]:
        """Classify every linked worktree as missing, temporary or merged.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.GitLaneViolation]]``.

        """
        kind = c.Infra.LaneViolationKind
        temp_root = Path(tempfile.gettempdir()).resolve()
        base_branch = base.removeprefix(f"{c.Infra.GIT_ORIGIN}/")
        violations: list[m.Infra.GitLaneViolation] = []
        for entry in linked:
            if not entry.path.exists():
                violations.append(
                    cls._lane_violation(kind.MISSING_WORKTREE, str(entry.path)),
                )
                continue
            if entry.path.is_relative_to(temp_root):
                violations.append(
                    cls._lane_violation(kind.TEMP_WORKTREE, str(entry.path)),
                )
            if entry.head is None or entry.branch in {None, base_branch}:
                continue
            if entry.path == repo_path:
                continue
            merged = cls._lane_merged_and_clean(repo, entry.path, entry.head, base)
            if merged.failure:
                return r[t.VariadicTuple[m.Infra.GitLaneViolation]].from_failure(
                    merged,
                )
            if merged.value:
                violations.append(
                    cls._lane_violation(kind.MERGED_WORKTREE, str(entry.path)),
                )
        return r[t.VariadicTuple[m.Infra.GitLaneViolation]].ok(tuple(violations))

    @classmethod
    def _lane_merged_and_clean(
        cls,
        repo: Repo,
        path: Path,
        head: str,
        base: str,
    ) -> p.Result[bool]:
        """Return whether a linked worktree's HEAD is integrated and its tree clean.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        try:
            merged = repo.is_ancestor(repo.commit(head), repo.commit(base))
        except (BadName, GitCommandError) as exc:
            return r[bool].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[bool].fail(f"git lane ancestry failed: {exc}", exception=exc)
        if not merged:
            return r[bool].ok(value=False)
        status = cls.git_status(m.Infra.GitStatusRequest(repo_root=path))
        if status.failure:
            return r[bool].from_failure(status)
        return r[bool].ok(value=not status.value.dirty)


__all__: list[str] = ["FlextInfraUtilitiesGitLaneHygieneMixin"]
