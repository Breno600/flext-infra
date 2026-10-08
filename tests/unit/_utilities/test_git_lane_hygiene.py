"""Public lane hygiene census and ``workspace verify-lanes`` against real Git.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraGitService, c, m, main
from tests import u


class TestsFlextInfraGitLaneHygiene:
    """Prove the lane hygiene census through the public facade and CLI."""

    @staticmethod
    def _declared_base(tmp_path: Path) -> Path:
        """Seed a repository whose ``origin/HEAD`` names its integration branch.

        Returns:
            The repository root.

        """
        repository = u.Tests.git_repository(tmp_path)
        integration = u.Tests.integration_branch(repository)
        remotes = f"refs/remotes/{c.Infra.GIT_ORIGIN}"
        _ = u.Tests.git_run(
            repository,
            "symbolic-ref",
            f"{remotes}/{c.Infra.GIT_HEAD}",
            f"{remotes}/{integration}",
        )
        return repository

    def test_clean_repository_passes(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """No stash, merged branch or linked worktree yields an empty census."""
        repository = self._declared_base(tmp_path)
        request = m.Infra.GitStatusRequest(repo_root=repository)

        report = tm.ok(FlextInfraGitService.verify_lanes(request))

        tm.that(report.violations, eq=())
        tm.that(
            report.integration_base,
            eq=f"{c.Infra.GIT_ORIGIN}/{u.Tests.integration_branch(repository)}",
        )
        argv = ["workspace", "verify-lanes", "--repo-root", str(repository)]
        tm.that(main(argv), eq=0)
        _ = capsys.readouterr()

    @staticmethod
    def test_missing_integration_base_fails_loud(tmp_path: Path) -> None:
        """Without an ``origin/HEAD`` symbolic ref the census refuses to guess."""
        repository = u.Tests.git_repository(tmp_path)

        result = FlextInfraGitService.verify_lanes(
            m.Infra.GitStatusRequest(repo_root=repository),
        )

        tm.fail(result)
        tm.that(str(result.error), has="integration base unresolved")

    def test_every_violation_class_is_listed(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Stash, merged branch, temp, missing and merged worktrees all surface."""
        repository = self._declared_base(tmp_path / "primary")
        readme = repository / "README.md"
        readme.write_text("# Lane\n", encoding="utf-8")
        u.Tests.commit_git_changes(repository, "seed tracked file")
        _ = u.Tests.git_run(
            repository,
            "update-ref",
            f"refs/remotes/{c.Infra.GIT_ORIGIN}/"
            f"{u.Tests.integration_branch(repository)}",
            c.Infra.GIT_HEAD,
        )
        readme.write_text("# Hidden work\n", encoding="utf-8")
        stashed = u.Tests.git_capture(repository, "stash", "create").strip()
        _ = u.Tests.git_run(repository, "stash", "store", "-m", "fixture", stashed)
        readme.write_text("# Lane\n", encoding="utf-8")
        _ = u.Tests.git_run(repository, "branch", "merged-lane")
        lanes = tmp_path / "lanes"
        merged = u.Tests.git_linked_lane(lanes, repository, "merged-worktree").resolve()
        gone = u.Tests.git_linked_lane(lanes, repository, "gone-worktree").resolve()
        shutil.rmtree(gone)
        tm.that(merged.is_relative_to(Path(tempfile.gettempdir()).resolve()), eq=True)
        kind = c.Infra.LaneViolationKind

        census = tm.ok(
            u.Infra.git_lane_hygiene(m.Infra.GitStatusRequest(repo_root=repository)),
        )

        tm.that(
            {(violation.kind, violation.ref) for violation in census.violations},
            eq={
                (kind.STASH, "stash@{0}"),
                (kind.MERGED_BRANCH, "merged-lane"),
                (kind.TEMP_WORKTREE, str(merged)),
                (kind.MERGED_WORKTREE, str(merged)),
                (kind.MISSING_WORKTREE, str(gone)),
            },
        )
        argv = ["workspace", "verify-lanes", "--repo-root", str(repository)]
        tm.that(main(argv), eq=1)
        output = capsys.readouterr()
        for expected in ("stash@{0}", "merged-lane", str(merged), str(gone)):
            tm.that(output.out + output.err, has=expected)
