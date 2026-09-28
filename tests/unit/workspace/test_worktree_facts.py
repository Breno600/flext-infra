"""Canonical worktree facts primitive parity fixtures."""

from __future__ import annotations

import os
import time
from pathlib import Path

from flext_tests import tm

from flext_infra import m
from tests import u


class TestsFlextInfraWorktreeFacts(u.Tests.WorktreeFixture):
    """Prove FS-only discovery, classification, staleness, and planning."""

    @staticmethod
    def _policy() -> m.Infra.WorktreeFactsPolicy:
        """Return the typed layout policy the fixtures exercise."""
        return m.Infra.WorktreeFactsPolicy(
            tool_internal=(".claude/worktrees",), deps_dirs=(".venv", "node_modules")
        )

    @classmethod
    def _query(cls, *repo_roots: Path, window: int = 90) -> m.Infra.WorktreeFactsQuery:
        """Build one facts query over the given repository roots."""
        return m.Infra.WorktreeFactsQuery(
            repo_roots=repo_roots,
            policy=cls._policy(),
            now=time.time(),
            activity_window_days=window,
        )

    @staticmethod
    def _register(repo: Path, name: str, worktree: Path, branch: str = "") -> None:
        """Register one worktree the way Git stores it on the filesystem."""
        registry = repo / ".git" / "worktrees" / name
        registry.mkdir(parents=True, exist_ok=True)
        (registry / "gitdir").write_text(f"{worktree / '.git'}\n", encoding="utf-8")
        head = f"ref: refs/heads/{branch}\n" if branch else f"{'0' * 40}\n"
        (registry / "HEAD").write_text(head, encoding="utf-8")
        worktree.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _touch(path: Path, size: int = 1, *, age_days: float = 0.0) -> None:
        """Write one file with a deterministic byte size and age."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
        stamp = time.time() - age_days * 86400.0
        os.utime(path, (stamp, stamp))

    def test_sibling_and_tool_internal(self, tmp_path: Path) -> None:
        """Classification follows the policy patterns, not a hardcoded list."""
        repo = tmp_path / "agents"
        sibling = tmp_path / "agents-worktrees" / "crg-skill"
        internal = repo / ".claude" / "worktrees" / "hook"
        self._register(repo, "crg-skill", sibling)
        self._register(repo, "hook", internal)
        self._touch(sibling / "file.py")
        self._touch(internal / "file.py")

        facts, actions = u.Infra.collect_worktree_facts(self._query(repo))

        tm.that(
            {fact.path.name: fact.kind for fact in facts},
            eq={"crg-skill": "sibling", "hook": "tool_internal"},
        )
        tm.that(actions, eq=())

    def test_stale_worktree_plans_deps_only(self, tmp_path: Path) -> None:
        """A stale worktree plans one contents-remove per real deps dir."""
        repo = tmp_path / "repo"
        stale = tmp_path / "repo-worktrees" / "old-lane"
        self._register(repo, "old-lane", stale, branch="feature/old")
        self._touch(stale / "src.py", age_days=120)
        self._touch(stale / ".venv" / "lib.py", size=8, age_days=120)

        facts, actions = u.Infra.collect_worktree_facts(self._query(repo))

        tm.that(len(facts), eq=1)
        tm.that(facts[0].stale_days > 90, eq=True)
        tm.that(facts[0].deps_bytes, eq=8)
        tm.that(facts[0].retire_candidate, eq=True)
        tm.that(facts[0].branch, eq="feature/old")
        tm.that([action.kind for action in actions], eq=["contents-remove"])
        tm.that(actions[0].owner, eq="worktrees")
        tm.that(actions[0].path, eq=stale / ".venv")
        tm.that(actions[0].reclaim_bytes, eq=8)
        tm.that(all("src.py" not in str(action.path) for action in actions), eq=True)

    def test_fresh_worktree_plans_nothing(self, tmp_path: Path) -> None:
        """A fresh worktree is a fact without any planned action."""
        repo = tmp_path / "repo"
        fresh = tmp_path / "repo-worktrees" / "lane"
        self._register(repo, "lane", fresh)
        self._touch(fresh / "src.py")
        self._touch(fresh / ".venv" / "lib.py", size=8)

        facts, actions = u.Infra.collect_worktree_facts(self._query(repo))

        tm.that(actions, eq=())
        tm.that(facts[0].retire_candidate, eq=False)

    def test_same_worktree_registered_twice_is_deduped(self, tmp_path: Path) -> None:
        """One physical worktree yields one fact across repositories."""
        repo_a = tmp_path / "a"
        repo_b = tmp_path / "b"
        shared = tmp_path / "shared-worktrees" / "lane"
        self._register(repo_a, "lane", shared)
        self._register(repo_b, "lane", shared)
        self._touch(shared / "f.py")

        facts, _actions = u.Infra.collect_worktree_facts(self._query(repo_a, repo_b))

        tm.that(len(facts), eq=1)

    def test_broken_gitdir_is_skipped(self, tmp_path: Path) -> None:
        """A registry entry pointing nowhere is a report cell, not an error."""
        repo = tmp_path / "repo"
        registry = repo / ".git" / "worktrees" / "ghost"
        registry.mkdir(parents=True)
        (registry / "gitdir").write_text("/nonexistent/wt/.git\n", encoding="utf-8")

        facts, actions = u.Infra.collect_worktree_facts(self._query(repo))

        tm.that(facts, eq=())
        tm.that(actions, eq=())

    def test_symlinked_deps_dir_is_skipped(self, tmp_path: Path) -> None:
        """A linked deps dir names an outside target and is never reclaimed."""
        repo = tmp_path / "repo"
        lane = tmp_path / "repo-worktrees" / "lane"
        external = tmp_path / "external-deps"
        external.mkdir(parents=True)
        (external / "lib.py").write_bytes(b"x" * 16)
        self._register(repo, "lane", lane)
        self._touch(lane / "src.py", age_days=120)
        (lane / ".venv").symlink_to(external, target_is_directory=True)

        facts, actions = u.Infra.collect_worktree_facts(self._query(repo))

        tm.that(facts[0].deps_bytes, eq=0)
        tm.that(actions, eq=())

    def test_registered_worktrees_are_deterministically_ordered(
        self, tmp_path: Path
    ) -> None:
        """Registry entries resolve in stable, sorted order."""
        repo = tmp_path / "repo"
        for name in ("zulu", "alpha"):
            lane = tmp_path / f"{name}-lane"
            self._register(repo, name, lane, branch=f"feature/{name}")
            self._touch(lane / "f.py")

        first = u.Infra.git_registered_worktrees_fs(repo)
        second = u.Infra.git_registered_worktrees_fs(repo)

        tm.that(first, eq=second)
        tm.that([root.name for root, _branch in first], eq=["alpha-lane", "zulu-lane"])
        tm.that(
            {root.name: branch for root, branch in first},
            eq={"alpha-lane": "feature/alpha", "zulu-lane": "feature/zulu"},
        )

    def test_detached_head_yields_empty_branch(self, tmp_path: Path) -> None:
        """A registry without a symbolic HEAD reports an empty branch."""
        repo = tmp_path / "repo"
        self._register(repo, "detached", tmp_path / "detached", branch="")

        entries = u.Infra.git_registered_worktrees_fs(repo)

        tm.that(len(entries), eq=1)
        tm.that(entries[0][1], eq="")

    def test_worktrees_report_carries_a_plan(self, tmp_path: Path) -> None:
        """The report wraps the facts and the plan-only stale-deps actions."""
        repo = tmp_path / "repo"
        stale = tmp_path / "repo-worktrees" / "old-lane"
        self._register(repo, "old-lane", stale)
        self._touch(stale / "src.py", age_days=120)
        self._touch(stale / ".venv" / "lib.py", size=8, age_days=120)

        report = u.Infra.worktrees_report(self._query(repo))
        plan = report.plan

        tm.that(len(report.facts), eq=1)
        assert plan is not None
        tm.that(plan.apply, eq=False)
        tm.that(plan.total_reclaim_bytes, eq=8)
        tm.that(len(plan.actions), eq=1)
