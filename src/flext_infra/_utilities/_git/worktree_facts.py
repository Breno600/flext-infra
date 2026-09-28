"""Canonical Git responsibility mixin for ``u.Infra``.

Filesystem-only worktree facts: registered worktrees come straight from
``.git/worktrees/<entry>/gitdir`` with no Git subprocess, staleness is the
bounded newest mtime, and the layout/dependency vocabulary arrives as typed
policy. Retirement is never executed here: a stale worktree only yields
``contents-remove`` plans for its rebuildable dependency directories.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from flext_infra import c, m, t

from .worktree_measure import FlextInfraUtilitiesGitWorktreeMeasureMixin


class FlextInfraUtilitiesGitWorktreeFactsMixin(
    FlextInfraUtilitiesGitWorktreeMeasureMixin
):
    """Own FS-only worktree facts discovery and stale-deps planning."""

    @classmethod
    def git_registered_worktrees_fs(
        cls, repository_root: Path
    ) -> t.VariadicTuple[t.Pair[Path, str]]:
        """Resolve registered worktrees from ``.git/worktrees`` without Git.

        The ``gitdir`` pointer names the worktree's own ``.git`` file, so the
        worktree root is its parent. Branch text comes from the registry HEAD;
        detached entries yield an empty branch. Broken or unreadable entries
        are report cells, not failures, skipped silently in stable sorted
        order.
        """
        registry = (
            repository_root.expanduser()
            / c.Infra.GIT_DIR
            / c.Infra.GIT_WORKTREES_DIRNAME
        )
        if not registry.is_dir():
            return ()
        resolved: list[t.Pair[Path, str]] = []
        for entry in sorted(registry.iterdir()):
            pointer = cls._worktree_gitdir_pointer(entry)
            if pointer is None:
                continue
            worktree_root = pointer.parent
            if not worktree_root.is_dir():
                continue
            resolved.append((worktree_root, cls._worktree_registry_branch(entry)))
        return tuple(resolved)

    @classmethod
    def collect_worktree_facts(
        cls, query: m.Infra.WorktreeFactsQuery
    ) -> t.Pair[
        t.VariadicTuple[m.Infra.WorktreeFact], t.VariadicTuple[m.Infra.PruneAction]
    ]:
        """Measure every registered worktree and plan stale-deps pruning.

        Correlation is optional and degrades to empty. A stale worktree is
        flagged ``retire_candidate`` and each non-symlinked deps directory
        becomes one ``contents-remove`` action owned by ``worktrees``.
        Nothing is executed here.
        """
        facts: list[m.Infra.WorktreeFact] = []
        actions: list[m.Infra.PruneAction] = []
        seen: set[Path] = set()
        for repo_root in sorted(query.repo_roots, key=lambda path: path.as_posix()):
            for worktree_root, branch in cls.git_registered_worktrees_fs(repo_root):
                if worktree_root in seen:
                    continue
                seen.add(worktree_root)
                facts.append(
                    cls._worktree_fact(
                        m.Infra.WorktreeCandidate(
                            path=worktree_root, repo=repo_root, branch=branch
                        ),
                        query,
                        actions,
                    )
                )
        return tuple(facts), tuple(actions)

    @classmethod
    def worktrees_report(
        cls,
        query: m.Infra.WorktreeFactsQuery,
        *,
        mode: str = "manual",
        apply: bool = False,
    ) -> m.Infra.WorktreesReport:
        """Assemble the facts report and its plan-only stale-deps actions."""
        facts, actions = cls.collect_worktree_facts(query)
        return m.Infra.WorktreesReport(
            facts=facts,
            plan=m.Infra.PrunePlan(
                generated_at=datetime.fromtimestamp(query.now, tz=UTC),
                mode=mode,
                apply=apply,
                actions=actions,
                total_reclaim_bytes=sum(action.reclaim_bytes for action in actions),
            ),
        )

    @classmethod
    def _worktree_fact(
        cls,
        candidate: m.Infra.WorktreeCandidate,
        query: m.Infra.WorktreeFactsQuery,
        actions: list[m.Infra.PruneAction],
    ) -> m.Infra.WorktreeFact:
        """Build one fact and append its planned stale-deps actions."""
        worktree_root = candidate.path
        total_bytes, newest_mtime, exact = cls._worktree_measure(worktree_root)
        deps: list[t.Pair[Path, int]] = []
        for deps_dir in query.policy.deps_dirs:
            deps_path = worktree_root / deps_dir
            if deps_path.is_dir() and not deps_path.is_symlink():
                deps.append((deps_path, cls._worktree_measure(deps_path)[0]))
        stale_days = max(0.0, (query.now - newest_mtime) / c.Infra.SECONDS_PER_DAY)
        stale = stale_days > query.activity_window_days
        fact = m.Infra.WorktreeFact(
            name=worktree_root.name,
            path=worktree_root,
            repo=candidate.repo,
            kind=cls._worktree_kind(worktree_root, query.policy),
            bytes=total_bytes,
            deps_bytes=sum(size for _path, size in deps),
            stale_days=stale_days,
            exact=exact,
            retire_candidate=stale,
        )
        correlated = cls._worktree_correlate(fact, candidate, query)
        if stale:
            for deps_path, size in deps:
                actions.append(
                    m.Infra.PruneAction(
                        kind="contents-remove",
                        path=deps_path,
                        reason=(
                            f"STO-WT-STALE-DEPS: {worktree_root.name} idle "
                            f"{stale_days:.1f}d > {query.activity_window_days}d"
                        ),
                        owner="worktrees",
                        reclaim_bytes=size,
                    )
                )
        return correlated

    @staticmethod
    def _worktree_gitdir_pointer(entry: Path) -> Path | None:
        """Read one registry ``gitdir`` pointer, or ``None`` when unreadable."""
        text = ""
        try:
            text = (entry / "gitdir").read_text(encoding=c.Cli.ENCODING_DEFAULT).strip()
        except (OSError, ValueError):
            text = ""
        return Path(text) if text else None

    @staticmethod
    def _worktree_registry_branch(entry: Path) -> str:
        """Read the checked-out branch from a registry HEAD, else empty text."""
        head = ""
        try:
            head = (entry / "HEAD").read_text(encoding=c.Cli.ENCODING_DEFAULT).strip()
        except OSError:
            head = ""
        prefix = f"ref: {c.Infra.GIT_REFS_HEADS}"
        return head.removeprefix(prefix) if head.startswith(prefix) else ""

    @staticmethod
    def _worktree_kind(
        worktree_root: Path, policy: m.Infra.WorktreeFactsPolicy
    ) -> Literal["sibling", "tool_internal"]:
        """Classify a worktree as tool-internal or sibling from policy patterns."""
        text = f"{worktree_root}/"
        internal = any(
            str(worktree_root).endswith(pattern) or f"/{pattern}/" in text
            for pattern in policy.tool_internal
        )
        return "tool_internal" if internal else "sibling"

    @classmethod
    def _worktree_bead_index(
        cls, rows: t.VariadicTuple[t.JsonMapping]
    ) -> t.MappingKV[str, t.MappingKV[str, t.JsonMapping]]:
        """Index optional bead rows by work dir and branch for correlation."""
        by_dir: MutableMapping[str, t.JsonMapping] = {}
        by_branch: MutableMapping[str, t.JsonMapping] = {}
        for row in rows:
            metadata = row.get("metadata")
            if not isinstance(metadata, Mapping):
                continue
            work_dir = str(
                metadata.get("gc.work_dir") or metadata.get("work_dir") or ""
            )
            if work_dir:
                by_dir.setdefault(work_dir, row)
            branch = str(metadata.get("branch") or metadata.get("gc.work_branch") or "")
            if branch:
                by_branch.setdefault(branch, row)
        return {"by_dir": by_dir, "by_branch": by_branch}

    @classmethod
    def _worktree_correlate(
        cls,
        fact: m.Infra.WorktreeFact,
        candidate: m.Infra.WorktreeCandidate,
        query: m.Infra.WorktreeFactsQuery,
    ) -> m.Infra.WorktreeFact:
        """Attach optional bead/PR/actor evidence to one fact."""
        index = cls._worktree_bead_index(query.bead_rows)
        row = (
            index.get("by_branch", {}).get(candidate.branch)
            if candidate.branch
            else None
        )
        if row is None:
            row = index.get("by_dir", {}).get(str(fact.path))
        if row is None and candidate.branch.startswith("polecat/"):
            row = {"id": candidate.branch.removeprefix("polecat/")}
        evidence = (query.actor_evidence or {}).get(str(fact.path), ("", ""))
        pr = row.get("pr_number") if row else None
        return fact.model_copy(
            update={
                "branch": candidate.branch,
                "bead": str(row.get("id", "")) if row else "",
                "pr_number": pr if isinstance(pr, int) else None,
                "actor": evidence[0],
                "session_id": evidence[1],
            }
        )


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreeFactsMixin"]
