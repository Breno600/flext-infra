"""Public u.Infra branch, stash, remote and merge-probe owners against real Git.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c, m
from tests import u


class TestsFlextInfraGitSweepSemantics:
    """Prove the preservation primitives through the public facade."""

    @staticmethod
    def _published(tmp_path: Path) -> tuple[Path, str]:
        """Seed a repository whose integration branch is published to a bare origin.

        Returns:
            The repository root and its integration branch.

        """
        repository = u.Tests.git_repository(tmp_path)
        _ = u.Tests.configure_local_origin(repository, tmp_path / "remote")
        integration = u.Tests.integration_branch(repository)
        _ = u.Tests.git_run(repository, "switch", integration)
        return repository, integration

    @staticmethod
    def _commit_file(repository: Path, name: str, text: str) -> str:
        """Commit one file and return the new HEAD oid.

        Returns:
            The resulting ``str``.

        """
        (repository / name).write_text(text, encoding="utf-8")
        u.Tests.commit_git_changes(repository, f"add {name}")
        return u.Tests.git_capture(repository, "rev-parse", c.Infra.GIT_HEAD)

    def test_ref_heads_lists_local_and_remote_tracking_tips(
        self,
        tmp_path: Path,
    ) -> None:
        """Local and remote-tracking namespaces map names to tips, without HEAD."""
        repository, integration = self._published(tmp_path)
        tm.ok(u.Infra.git_fetch_remote(m.Infra.GitRemoteRequest(repo_root=repository)))
        head = u.Tests.git_capture(repository, "rev-parse", c.Infra.GIT_HEAD)

        local = tm.ok(
            u.Infra.git_ref_heads(
                m.Infra.GitRefHeadsRequest(
                    repo_root=repository,
                    namespace="refs/heads",
                ),
            ),
        )
        remote = tm.ok(
            u.Infra.git_ref_heads(
                m.Infra.GitRefHeadsRequest(
                    repo_root=repository,
                    namespace=f"refs/remotes/{c.Infra.GIT_ORIGIN}",
                ),
            ),
        )

        tm.that(local.heads[integration], eq=head)
        tm.that(remote.heads[integration], eq=head)
        tm.that(c.Infra.GIT_HEAD in remote.heads, eq=False)

    def test_stash_drop_removes_exactly_the_named_entry(self, tmp_path: Path) -> None:
        """Dropping by commit oid keeps every other stash entry intact."""
        repository = u.Tests.git_repository(tmp_path)
        _ = self._commit_file(repository, "tracked.txt", "base\n")
        tracked = repository / "tracked.txt"
        for text in ("first\n", "second\n"):
            tracked.write_text(text, encoding="utf-8")
            _ = u.Tests.git_run(repository, "stash", "push", "--message", text)
        request = m.Infra.GitRepoRequest(repo_root=repository)
        newest, oldest = tm.ok(u.Infra.git_stash_oids(request)).oids

        tm.ok(
            u.Infra.git_stash_drop(
                m.Infra.GitStashDropRequest(repo_root=repository, oid=oldest),
            ),
        )
        missing = u.Infra.git_stash_drop(
            m.Infra.GitStashDropRequest(repo_root=repository, oid=oldest),
        )

        tm.that(tuple(tm.ok(u.Infra.git_stash_oids(request)).oids), eq=(newest,))
        tm.that(missing.failure, eq=True)

    @staticmethod
    def test_create_branch_switch_carries_changes_and_refuses_duplicates(
        tmp_path: Path,
    ) -> None:
        """A switched new branch keeps the dirty tree; an existing name fails."""
        repository = u.Tests.git_repository(tmp_path)
        (repository / "dirty.txt").write_text("kept\n", encoding="utf-8")

        tm.ok(
            u.Infra.git_create_branch(
                m.Infra.GitBranchCreateRequest(
                    repo_root=repository,
                    branch="preserve",
                    switch=True,
                ),
            ),
        )
        duplicate = u.Infra.git_create_branch(
            m.Infra.GitBranchCreateRequest(repo_root=repository, branch="preserve"),
        )
        branch = tm.ok(
            u.Infra.git_current_branch(m.Infra.GitRepoRequest(repo_root=repository)),
        )

        tm.that(branch.text, eq="preserve")
        tm.that((repository / "dirty.txt").read_text(encoding="utf-8"), eq="kept\n")
        tm.that(duplicate.failure, eq=True)

    @staticmethod
    def test_switch_branch_moves_to_an_existing_branch(tmp_path: Path) -> None:
        """Switching lands on an existing branch; an unknown one fails."""
        repository = u.Tests.git_repository(tmp_path)
        _ = u.Tests.git_run(repository, "branch", "existing")

        tm.ok(
            u.Infra.git_switch_branch(
                m.Infra.GitBranchRequest(repo_root=repository, branch="existing"),
            ),
        )
        unknown = u.Infra.git_switch_branch(
            m.Infra.GitBranchRequest(repo_root=repository, branch="unknown"),
        )
        branch = tm.ok(
            u.Infra.git_current_branch(m.Infra.GitRepoRequest(repo_root=repository)),
        )

        tm.that(branch.text, eq="existing")
        tm.that(unknown.failure, eq=True)

    def test_push_source_is_proven_by_the_live_remote_and_deleted_on_lease(
        self,
        tmp_path: Path,
    ) -> None:
        """A pushed branch is visible remotely; a stale lease cannot delete it."""
        repository, _ = self._published(tmp_path)
        tm.ok(
            u.Infra.git_create_branch(
                m.Infra.GitBranchCreateRequest(repo_root=repository, branch="lane"),
            ),
        )
        oid = u.Tests.git_capture(repository, "rev-parse", "refs/heads/lane")
        remote = m.Infra.GitRemoteBranchRequest(repo_root=repository, branch="lane")

        absent = tm.ok(u.Infra.git_remote_branch_oid(remote))
        tm.ok(
            u.Infra.git_push_upstream(
                m.Infra.GitPushRequest(
                    repo_root=repository,
                    branch="lane",
                    source="refs/heads/lane",
                ),
            ),
        )
        published = tm.ok(u.Infra.git_remote_branch_oid(remote))
        stale = u.Infra.git_delete_remote_branch(
            remote.model_copy(update={"expected_oid": "0" * 40}),
        )
        tm.ok(
            u.Infra.git_delete_remote_branch(
                remote.model_copy(update={"expected_oid": oid}),
            ),
        )
        deleted = tm.ok(u.Infra.git_remote_branch_oid(remote))

        tm.that(absent.text, eq="")
        tm.that(published.text, eq=oid)
        tm.that(stale.failure, eq=True)
        tm.that(deleted.text, eq="")

    def test_merge_probe_detects_squash_merged_and_pending_work(
        self,
        tmp_path: Path,
    ) -> None:
        """A squash-merged branch is a no-op merge; new work is not."""
        repository, integration = self._published(tmp_path)
        _ = u.Tests.git_run(repository, "switch", "--create", "squashed")
        _ = self._commit_file(repository, "feature.txt", "feature\n")
        _ = u.Tests.git_run(repository, "switch", integration)
        _ = u.Tests.git_run(repository, "merge", "--squash", "squashed")
        u.Tests.commit_git_changes(repository, "squash feature")
        _ = u.Tests.git_run(repository, "switch", "--create", "pending")
        _ = self._commit_file(repository, "pending.txt", "pending\n")

        squashed = tm.ok(
            u.Infra.git_merge_is_noop(
                m.Infra.GitMergeProbeRequest(
                    repo_root=repository,
                    base=integration,
                    commitish="squashed",
                ),
            ),
        )
        pending = tm.ok(
            u.Infra.git_merge_is_noop(
                m.Infra.GitMergeProbeRequest(
                    repo_root=repository,
                    base=integration,
                    commitish="pending",
                ),
            ),
        )

        tm.that(squashed.value, eq=True)
        tm.that(pending.value, eq=False)

    def test_merge_ff_only_advances_and_refuses_divergence(
        self,
        tmp_path: Path,
    ) -> None:
        """Fast-forward succeeds on a descendant and fails on a diverged line."""
        repository, integration = self._published(tmp_path)
        _ = u.Tests.git_run(repository, "switch", "--create", "ahead")
        ahead = self._commit_file(repository, "ahead.txt", "ahead\n")
        _ = u.Tests.git_run(repository, "switch", integration)

        tm.ok(
            u.Infra.git_merge_ff_only(
                m.Infra.GitCommitishRequest(repo_root=repository, commitish="ahead"),
            ),
        )
        head = u.Tests.git_capture(repository, "rev-parse", c.Infra.GIT_HEAD)
        _ = self._commit_file(repository, "local.txt", "local\n")
        _ = u.Tests.git_run(repository, "switch", "ahead")
        _ = self._commit_file(repository, "other.txt", "other\n")
        _ = u.Tests.git_run(repository, "switch", integration)
        diverged = u.Infra.git_merge_ff_only(
            m.Infra.GitCommitishRequest(repo_root=repository, commitish="ahead"),
        )

        tm.that(head, eq=ahead)
        tm.that(diverged.failure, eq=True)

    @staticmethod
    def test_last_activity_is_not_older_than_the_head_commit(tmp_path: Path) -> None:
        """Last activity covers at least the HEAD commit time."""
        repository = u.Tests.git_repository(tmp_path)
        committed = int(
            u.Tests.git_capture(repository, "log", "-1", "--format=%ct"),
        )

        activity = tm.ok(
            u.Infra.git_last_activity(m.Infra.GitRepoRequest(repo_root=repository)),
        )

        tm.that(activity.epoch_seconds >= committed, eq=True)

    @staticmethod
    def test_commit_rejected_by_a_hook_is_a_failure(tmp_path: Path) -> None:
        """A rejecting pre-commit hook yields a failed result, never an exception."""
        repository = u.Tests.git_repository(tmp_path)
        hook = repository / ".git" / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        (repository / "gated.txt").write_text("gated\n", encoding="utf-8")
        _ = u.Tests.git_run(repository, "add", "gated.txt")
        head = u.Tests.git_capture(repository, "rev-parse", c.Infra.GIT_HEAD)

        gated = u.Infra.git_commit(
            m.Infra.GitCommitRequest(repo_root=repository, message="gated"),
        )

        tm.that(gated.failure, eq=True)
        tm.that(
            u.Tests.git_capture(repository, "rev-parse", c.Infra.GIT_HEAD),
            eq=head,
        )
