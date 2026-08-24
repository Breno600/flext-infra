"""Finish retry behavior for interrupted canonical lane retirement."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from flext_infra import FlextInfraWorkService, c, m, u
from flext_tests import tm
from tests.unit.workspace.test_work_service import TestsFlextInfraWorkService


class TestsWorkFinishRecovery(TestsFlextInfraWorkService):
    @staticmethod
    def _finish(repository: Path, bead_id: str) -> str:
        return tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.FINISH,
                bead=bead_id,
                apply_changes=True,
            ).execute()
        )

    def _started_finish_lane(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bead_id: str
    ) -> tuple[Path, Path, str, str]:
        repository = self._repository(tmp_path)
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
                kind=c.Infra.WorkKind.BUGFIX,
                name=bead_id.removeprefix("mro-test-"),
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        record = self._record(tmp_path, bead_id)
        record["metadata"]["pr_number"] = "1"
        self._set_record(tmp_path, bead_id, record)
        return (
            repository,
            Path(record["metadata"]["worktree"]),
            record["metadata"]["branch"],
            record["metadata"]["head_oid"],
        )

    def test_finish_retry_reconciles_physical_removal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bead_id = "mro-test-recover-physical"
        repository, lane, branch, _head = self._started_finish_lane(
            tmp_path, monkeypatch, bead_id
        )
        tm.ok(u.Infra.git_remove_clean_worktree(repository, lane))

        receipt = self._finish(repository, bead_id)

        tm.that(receipt, has="receipt.operation=finish")
        assert self._metadata(tmp_path, bead_id)["worktree"] == "removed"
        assert (
            tm.ok(
                u.Infra.git_ref_exists(
                    m.Infra.GitRefRequest(
                        repo_root=repository, reference=f"refs/heads/{branch}"
                    )
                )
            ).value
            is False
        )

    def test_finish_retry_reconciles_branch_deletion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bead_id = "mro-test-recover-branch"
        repository, lane, branch, head = self._started_finish_lane(
            tmp_path, monkeypatch, bead_id
        )
        tm.ok(u.Infra.git_remove_clean_worktree(repository, lane))
        tm.ok(
            u.Infra.git_delete_ref(
                m.Infra.GitDeleteRefRequest(
                    repo_root=repository,
                    reference=f"refs/heads/{branch}",
                    expected_oid=head,
                )
            )
        )

        receipt = self._finish(repository, bead_id)

        tm.that(receipt, has="receipt.operation=finish")
        assert self._metadata(tmp_path, bead_id)["worktree"] == "removed"

    def test_finish_retry_accepts_completed_bead_update(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bead_id = "mro-test-recover-bead"
        repository, _lane, _branch, _head = self._started_finish_lane(
            tmp_path, monkeypatch, bead_id
        )
        first = self._finish(repository, bead_id)

        second = self._finish(repository, bead_id)

        tm.that(first, has="receipt.operation=finish")
        tm.that(second, has="receipt.operation=finish")
        tm.that(second, has="receipt.worktree=removed")


__all__: tuple[str, ...] = ("TestsWorkFinishRecovery",)
