"""Public child LAND scenario against a live epic lane."""

from __future__ import annotations

from pathlib import Path

import pytest

from flext_infra import FlextInfraWorkService, c, m, u
from flext_tests import tm
from tests.unit.workspace.work_public_service_fixture import WorkPublicServiceFixture


def test_child_land_creates_pr_against_live_epic_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = WorkPublicServiceFixture.create(tmp_path, monkeypatch)
    epic_bead = "mro-land-epic"
    child_bead = "mro-land-child"
    fixture.add_issue(epic_bead, issue_type="epic")
    fixture.add_issue(child_bead, issue_type="task", parent=epic_bead)

    tm.ok(
        FlextInfraWorkService(
            workspace_root=fixture.repository,
            operation=c.Infra.WorkOperation.START,
            bead=epic_bead,
            name="live-epic",
            base="HEAD",
            apply_changes=True,
        ).execute()
    )
    tm.ok(
        FlextInfraWorkService(
            workspace_root=fixture.repository,
            operation=c.Infra.WorkOperation.START,
            bead=child_bead,
            name="land-child",
            epic=epic_bead,
            apply_changes=True,
        ).execute()
    )

    landed = tm.ok(
        FlextInfraWorkService(
            workspace_root=fixture.repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=child_bead,
            apply_changes=True,
        ).execute()
    )

    receipt = fixture.pr_create_receipt()
    assert receipt.base == "epic/live-epic"
    assert receipt.head == "feature/land-child"
    issue = fixture.issue(child_bead)
    metadata = issue.metadata
    assert isinstance(metadata, m.Infra.ReadyLaneMetadata)
    assert metadata.pr_number == "41"
    assert metadata.pr_url == "https://example.test/pr/41"
    assert metadata.integration_base == receipt.base
    assert (
        tm.ok(
            u.Infra.git_rev_parse(
                m.Infra.GitCommitishRequest(
                    repo_root=fixture.repository,
                    commitish=f"refs/remotes/origin/{receipt.head}",
                )
            )
        ).oid
        == metadata.head_oid
    )
    tm.that(landed, has=f"receipt.base={receipt.base}")


__all__: tuple[str, ...] = ()
