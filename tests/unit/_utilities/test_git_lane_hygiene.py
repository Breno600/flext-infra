"""Native lane facts and the one public evaluator against real local Git.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraGitService, c, config, m, main
from tests import u


class TestsFlextInfraGitLaneHygiene:
    """Preserve incoming census intents under the canonical fresh-base contract."""

    @staticmethod
    def _declared_base(tmp_path: Path) -> m.Infra.GitLaneVerificationRequest:
        """Create a real remote whose integration is available and demonstrably live.

        Returns:
            The typed request with a fixture-owned integration declaration.

        """
        repository = u.Tests.git_repository(tmp_path)
        integration = u.Tests.integration_branch(repository)
        u.Tests.git_run(repository, "branch", "-m", integration)
        remote = tmp_path / "integration.git"
        u.Tests.git_bootstrap(tmp_path, ("init", "--bare", str(remote)))
        policy = config.Infra.codegen.branch_policy
        action = "set-url" if policy.lane_remote == c.Infra.GIT_ORIGIN else "add"
        u.Tests.git_run(repository, "remote", action, policy.lane_remote, str(remote))
        u.Tests.git_run(repository, "push", "-u", policy.lane_remote, integration)
        return m.Infra.GitLaneVerificationRequest(
            repo_root=repository,
            declared=integration,
        )

    @classmethod
    def test_clean_repository_passes(
        cls,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Only the declared integration remains; dormant sources are not probed."""
        request = cls._declared_base(tmp_path)
        facts = tm.ok(u.Infra.git_lane_facts(request))
        tm.that(facts.stash_oids, eq=())
        tm.that(facts.read_errors, eq=())
        report = tm.ok(FlextInfraGitService.verify_lanes(request))
        tm.that(report.violations, eq=())
        tm.that(report.findings, eq=())
        tm.that(report.integration_branch, eq=request.declared)
        tm.that(
            main([
                "workspace",
                "verify-lanes",
                "--repo-root",
                str(request.repo_root),
                "--declared",
                str(request.declared),
            ]),
            eq=0,
        )
        _ = capsys.readouterr()

    @classmethod
    def test_missing_integration_base_fails_loud(cls, tmp_path: Path) -> None:
        """An explicit missing authority cannot silently choose a healthy branch."""
        request = cls._declared_base(tmp_path)
        missing = request.model_copy(update={"declared": "fixture/missing-authority"})
        result = FlextInfraGitService.verify_lanes(missing)
        tm.fail(result)
        tm.that(str(result.error), has="integration branch is absent remotely")

    @classmethod
    def test_every_violation_class_is_listed(
        cls,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Stashes, all merged refs, orphans and clean linked lanes surface."""
        request = cls._declared_base(tmp_path / "primary")
        repository = request.repo_root
        (repository / "README.md").write_text("# Lane\n", encoding="utf-8")
        u.Tests.commit_git_changes(repository, "seed tracked file")
        policy = config.Infra.codegen.branch_policy
        u.Tests.git_run(repository, "push", policy.lane_remote)
        head = u.Tests.git_capture(repository, "rev-parse", "HEAD")
        u.Tests.git_run(
            repository,
            "update-ref",
            "--create-reflog",
            "-m",
            "recovery fixture",
            "refs/stash",
            head,
        )
        u.Tests.git_run(repository, "branch", "merged-lane")
        merged = u.Tests.git_linked_lane(
            tmp_path / "lanes", repository, "merged-worktree"
        )
        gone = u.Tests.git_linked_lane(tmp_path / "lanes", repository, "gone-worktree")
        gone.rename(tmp_path / "preserved-worktree")
        facts = tm.ok(u.Infra.git_lane_facts(request))
        tm.that(facts.stash_oids, eq=(head,))
        result = FlextInfraGitService.verify_lanes(request)
        tm.fail(result)
        report = m.Infra.GitLaneReport.model_validate_json(tm.not_none(result.error))
        kind = c.Infra.LaneViolationKind
        expected = {
            (kind.STASH, head),
            (kind.MERGED_BRANCH, "refs/heads/merged-lane"),
            (kind.MERGED_BRANCH, "refs/heads/merged-worktree"),
            (kind.MERGED_BRANCH, "refs/heads/gone-worktree"),
            (kind.MERGED_WORKTREE, str(merged)),
            (kind.MISSING_WORKTREE, str(gone)),
        }
        if any(merged.is_relative_to(root) for root in policy.lane_temporary_roots):
            expected.add((kind.TEMP_WORKTREE, str(merged)))
        tm.that({(entry.kind, entry.ref) for entry in report.violations}, eq=expected)
        tm.that(
            main([
                "workspace",
                "verify-lanes",
                "--repo-root",
                str(repository),
                "--declared",
                str(request.declared),
            ]),
            eq=1,
        )
        output = capsys.readouterr()
        for ref in (head, "refs/heads/merged-lane", str(merged), str(gone)):
            tm.that(output.out + output.err, has=ref)
