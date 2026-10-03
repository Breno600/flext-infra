"""Public u.Infra ref/ancestry owner semantics against a real repository.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c, m, u
from tests import u as test_u


class TestsFlextInfraGitRefsSemantics:
    """Prove the single canonical ref owner per fact through the public facade."""

    @staticmethod
    def _linked_lane(tmp_path: Path, repository: Path, branch: str) -> Path:
        """Register ``branch`` as a linked worktree lane beside the primary.

        Returns:
            The resulting ``Path``.

        """
        lane = tmp_path / branch
        _ = test_u.Tests.git_run(repository, "branch", branch)
        _ = test_u.Tests.git_run(repository, "worktree", "add", str(lane), branch)
        return lane

    @staticmethod
    def test_current_branch_reports_the_checked_out_branch(
        tmp_path: Path,
    ) -> None:
        """The single branch owner reads the branch the worktree is on."""
        repository = test_u.Tests.git_repository(tmp_path)

        branch = tm.ok(
            u.Infra.git_current_branch(m.Infra.GitRepoRequest(repo_root=repository)),
        )

        tm.that(branch.text, eq=c.Infra.GIT_MAIN)

    @staticmethod
    def test_current_branch_fails_loudly_on_a_detached_head(
        tmp_path: Path,
    ) -> None:
        """A detached HEAD has no branch; the owner fails instead of a sentinel."""
        repository = test_u.Tests.git_repository(tmp_path)
        _ = test_u.Tests.git_run(repository, "checkout", "--detach", c.Infra.GIT_HEAD)

        result = u.Infra.git_current_branch(
            m.Infra.GitRepoRequest(repo_root=repository),
        )

        assert result.failure
        assert result.error is not None

    @staticmethod
    def test_ref_exists_distinguishes_present_from_absent(tmp_path: Path) -> None:
        """The ref owner answers the exact-ref question, never raising on absence."""
        repository = test_u.Tests.git_repository(tmp_path)

        present = tm.ok(
            u.Infra.git_ref_exists(
                m.Infra.GitRefRequest(
                    repo_root=repository,
                    reference=f"refs/heads/{c.Infra.GIT_MAIN}",
                ),
            ),
        )
        absent = tm.ok(
            u.Infra.git_ref_exists(
                m.Infra.GitRefRequest(
                    repo_root=repository,
                    reference="refs/heads/does-not-exist",
                ),
            ),
        )

        tm.that(present.value, eq=True)
        tm.that(absent.value, eq=False)

    @staticmethod
    def test_check_branch_format_accepts_and_rejects(tmp_path: Path) -> None:
        """The branch-format owner answers from Git's own check-ref-format."""
        repository = test_u.Tests.git_repository(tmp_path)

        valid = tm.ok(
            u.Infra.git_check_branch_format(
                m.Infra.GitBranchRequest(repo_root=repository, branch="feature/ok"),
            ),
        )
        invalid = u.Infra.git_check_branch_format(
            m.Infra.GitBranchRequest(repo_root=repository, branch="bad name"),
        )

        tm.that(valid.value, eq=True)
        tm.that(invalid.failure, eq=True)
        tm.that(invalid.error, contains="not a valid branch name")

    @staticmethod
    def test_resolve_commit_and_rev_parse_agree_on_head(tmp_path: Path) -> None:
        """Both oid owners resolve the same HEAD to the same 40-hex oid."""
        repository = test_u.Tests.git_repository(tmp_path)

        resolved = tm.ok(
            u.Infra.git_resolve_commit(
                m.Infra.GitCommitishRequest(
                    repo_root=repository,
                    commitish=c.Infra.GIT_HEAD,
                ),
            ),
        )
        parsed = tm.ok(
            u.Infra.git_rev_parse(
                m.Infra.GitCommitishRequest(
                    repo_root=repository,
                    commitish=c.Infra.GIT_HEAD,
                ),
            ),
        )

        tm.that(resolved.oid, eq=parsed.oid)
        tm.that(len(resolved.oid), eq=40)

    @staticmethod
    def test_resolve_commit_fails_on_an_unknown_commitish(tmp_path: Path) -> None:
        """An unresolvable commit-ish is a failure, never an empty oid."""
        repository = test_u.Tests.git_repository(tmp_path)

        result = u.Infra.git_resolve_commit(
            m.Infra.GitCommitishRequest(
                repo_root=repository,
                commitish="no-such-commit-ish",
            ),
        )

        assert result.failure
        assert result.error is not None

    def test_show_toplevel_reports_the_current_worktree_root(
        self,
        tmp_path: Path,
    ) -> None:
        """The toplevel owner reports the worktree it was asked about, not the primary."""
        repository = test_u.Tests.git_repository(tmp_path)
        lane = self._linked_lane(tmp_path, repository, "toplevel-lane")

        primary_root = tm.ok(
            u.Infra.git_show_toplevel(m.Infra.GitRepoRequest(repo_root=repository)),
        )
        lane_root = tm.ok(
            u.Infra.git_show_toplevel(m.Infra.GitRepoRequest(repo_root=lane)),
        )

        tm.that(primary_root.repository_root, eq=repository.resolve())
        tm.that(lane_root.repository_root, eq=lane.resolve())

    def test_list_worktrees_reports_the_primary_and_the_linked_lane(
        self,
        tmp_path: Path,
    ) -> None:
        """The worktree-list owner reports every registered checkout of the repo."""
        repository = test_u.Tests.git_repository(tmp_path)
        lane = self._linked_lane(tmp_path, repository, "list-lane")

        listed = tm.ok(
            u.Infra.git_list_worktrees(m.Infra.GitRepoRequest(repo_root=repository)),
        )

        assert listed.root == repository.resolve()
        assert str(repository) in listed.porcelain
        assert str(lane) in listed.porcelain
        by_path = {entry.path: entry for entry in listed.entries}
        tm.that(by_path[repository.resolve()].branch, eq=c.Infra.GIT_MAIN)
        tm.that(by_path[lane.resolve()].branch, eq="list-lane")
