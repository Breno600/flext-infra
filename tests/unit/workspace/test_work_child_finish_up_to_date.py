"""Public child FINISH scenario when the epic is already current."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_infra import FlextInfraWorkService, FlextInfraWorktreeService, c
from flext_tests import tm

from tests.unit import WorkPublicFinishFixture

# Why (suite budget): full child FINISH saga over real epic/child worktrees
# with subprocess git and beads calls; the per-case wall only holds idle.
pytestmark = pytest.mark.slow


def test_child_finish_retires_without_redundant_epic_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = WorkPublicFinishFixture.create(tmp_path, monkeypatch)
    state = fixture.start_and_land()
    epic_oid = fixture.advance_remote_epic_with_child(state)
    fixture.fast_forward_local_epic(state, epic_oid)
    fixture.mark_pr_merged(state)

    tm.ok(
        FlextInfraWorkService(
            workspace_root=fixture.repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=state.child_bead,
            apply_changes=True,
        ).execute()
    )

    epic = fixture.ready_metadata(state.epic_bead)
    child = fixture.ready_metadata(state.child_bead)
    assert fixture.oid(state.epic_lane, "HEAD") == epic_oid
    assert fixture.parent_count(state.epic_lane, epic_oid) == 1
    assert epic.head_oid == epic_oid
    assert child.worktree == Path("removed")
    assert fixture.epic_update_precedes_child_retirement(state)
    assert (
        tm.ok(
            FlextInfraWorktreeService.registered_lane(
                fixture.repository, state.epic_branch
            )
        )
        == state.epic_lane
    )


__all__: tuple[str, ...] = ()
