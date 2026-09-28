"""Real Git + shim bd behavior for make work saga."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraWorkService, FlextInfraWorktreeService
from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path as PathType


from tests.unit.workspace.work_service_fixture import WorkServiceFixture


class TestsWorkServiceLifecycle(WorkServiceFixture):
    """Exercise the public work service lifecycle through real Git."""

    def test_start_recovers_existing_lane_without_metadata(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A lane registered by an interrupted start is adopted, not rejected."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-start-recover"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        orphan = tm.ok(
            FlextInfraWorktreeService(
                repository_root=repository,
                operation=c.Infra.WorktreeOperation.ADD,
                branch="feature/recover-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        assert self._metadata(tmp_path, bead_id) == {}
        started = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="recover-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.that(started, has=f"receipt.worktree={orphan}")
        tm.that(started, has="receipt.branch=feature/recover-lane")
        assert self._metadata(tmp_path, bead_id)["worktree"] == orphan

    def test_start_rolls_back_lane_when_beads_update_fails(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A lane the saga cannot register on its bead must not survive."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-start-rollback"
        shim_dir = self._install_bd_shim(tmp_path, bead_id, update_fails=True)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            kind=c.Infra.WorkKind.FEATURE,
            name="rollback-lane",
            base="HEAD",
            apply_changes=True,
        ).execute()
        tm.fail(result, has="bd update refused")
        tm.fail(result, has="rolled back")
        orphaned = FlextInfraWorktreeService.registered_lane(
            repository, "feature/rollback-lane"
        )
        tm.fail(orphaned, has="is not registered")

    def test_land_happy_path_push_and_pr_updates_metadata(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Land pushes the lane, records the PR, and emits a land receipt."""
        repository = self._repository(tmp_path)
        self._attach_bare_origin(tmp_path, repository)
        bead_id = "mro-test-land-happy"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(
            tmp_path, pr_list='[{"number": "7", "url": "https://example.test/pr/7"}]'
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="land-happy",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        landed = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.LAND,
                bead=bead_id,
                apply_changes=True,
            ).execute()
        )
        metadata = self._metadata(tmp_path, bead_id)
        tm.that(landed, has="receipt.operation=land")
        tm.that(landed, has="receipt.pr=7")
        tm.that(landed, has="receipt.base=main")
        tm.that(landed, has=f"receipt.head_oid={metadata['head_oid']}")
        assert metadata["pr_number"] == "7"
        assert metadata["pr_url"] == "https://example.test/pr/7"
        pushed = tm.ok(
            u.Infra.git_rev_parse(
                m.Infra.GitCommitishRequest(
                    repo_root=repository,
                    commitish="refs/remotes/origin/feature/land-happy",
                )
            )
        ).oid
        assert pushed == metadata["head_oid"]

    def test_land_allows_ancestor_cas(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lane commits made after start are a fast-forward, not a CAS conflict."""
        repository = self._repository(tmp_path)
        self._attach_bare_origin(tmp_path, repository)
        bead_id = "mro-test-land-ancestor"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(
            tmp_path, pr_list='[{"number": "3", "url": "https://example.test/pr/3"}]'
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="land-ancestor",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        recorded = self._metadata(tmp_path, bead_id)["head_oid"]
        lane = Path(self._metadata(tmp_path, bead_id)["worktree"])
        self._commit_in(lane, "lane advance")
        landed = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.LAND,
                bead=bead_id,
                apply_changes=True,
            ).execute()
        )
        advanced = self._metadata(tmp_path, bead_id)["head_oid"]
        assert advanced != recorded
        tm.that(landed, has=f"receipt.head_oid={advanced}")

    def test_land_push_rejection_reports_shas(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rejected push names both SHAs so the operator can judge divergence."""
        repository = self._repository(tmp_path)
        self._attach_bare_origin(tmp_path, repository)
        bead_id = "mro-test-land-reject"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="land-reject",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        lane = Path(self._metadata(tmp_path, bead_id)["worktree"])
        self._commit_in(repository, "remote advance")
        remote_oid = tm.ok(
            u.Infra.git_repository_head(m.Infra.GitRepoRequest(repo_root=repository))
        ).oid
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "push", "origin", "HEAD:refs/heads/feature/land-reject"],
                cwd=repository,
            )
        )
        tm.ok(u.Cli.run_checked([c.Infra.GIT, "fetch", "origin"], cwd=lane))
        self._commit_in(lane, "lane diverge")
        local_oid = tm.ok(
            u.Infra.git_repository_head(m.Infra.GitRepoRequest(repo_root=lane))
        ).oid
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has=f"local={local_oid.strip()}")
        tm.fail(result, has=f"remote={remote_oid.strip()}")

    def test_finish_refuses_open_pr_state(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An open PR still owns the lane, so finish must refuse to retire it."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-open"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(
            tmp_path, pr_view='{"state": "OPEN", "mergedAt": null, "headRefName": ""}'
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-open",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        self._update_root_matrix_entry(tmp_path, bead_id, pr_number="5")
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="requires merged PR #5; state=OPEN")

    def test_finish_refuses_closed_unmerged_pr(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A closed-without-merge PR abandoned the work; the lane stays."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-closed"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(
            tmp_path, pr_view='{"state": "CLOSED", "mergedAt": null, "headRefName": ""}'
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-closed",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        self._update_root_matrix_entry(tmp_path, bead_id, pr_number="6")
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="requires merged PR #6; state=CLOSED")
        assert self._metadata(tmp_path, bead_id)["worktree"] != "removed"

    def test_finish_refuses_open_pr_without_pr_number(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without a recorded PR the branch query is the only merge evidence."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-open-query"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path, pr_list='[{"number": "8"}]')
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-open-query",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="refuses open PR on bugfix/finish-open-query")

    def test_start_status_land_finish_idempotent_status_twice(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The full lane lifecycle runs once, and status never mutates it."""
        repository = self._repository(tmp_path)
        self._attach_bare_origin(tmp_path, repository)
        bead_id = "mro-test-lifecycle"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(
            tmp_path, pr_list='[{"number": "9", "url": "https://example.test/pr/9"}]'
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        started = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="lifecycle-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.that(started, has="receipt.operation=start")
        status_service = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.STATUS,
            bead=bead_id,
            apply_changes=False,
        )
        first_status = tm.ok(status_service.execute())
        second_status = tm.ok(status_service.execute())
        assert first_status == second_status
        landed = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.LAND,
                bead=bead_id,
                apply_changes=True,
            ).execute()
        )
        tm.that(landed, has="receipt.operation=land")
        finished = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.FINISH,
                bead=bead_id,
                apply_changes=True,
            ).execute()
        )
        tm.that(finished, has="receipt.operation=finish")
        tm.that(finished, has="receipt.pr=9")
        tm.that(finished, has="receipt.branch=feature/lifecycle-lane")
        assert self._metadata(tmp_path, bead_id)["worktree"] == "removed"
