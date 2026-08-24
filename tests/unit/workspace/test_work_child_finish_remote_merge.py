"""Public child FINISH scenario with a remotely advanced epic."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_infra import FlextInfraWorkService, FlextInfraWorktreeService
from flext_tests import tm

from tests import c, m, u
from tests.unit import WorkPublicFinishFixture

# Why (suite budget): full child FINISH saga over real epic/child worktrees
# with subprocess git and beads calls; the per-case wall only holds idle.
pytestmark = pytest.mark.slow


def test_child_finish_merges_remote_epic_before_retirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = WorkPublicFinishFixture.create(tmp_path, monkeypatch)
    state = fixture.start_and_land()
    remote_epic_oid = fixture.advance_remote_epic_with_child(state)
    fixture.advance_local_epic(state)
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
    epic_oid = fixture.oid(state.epic_lane, "HEAD")
    assert fixture.parent_count(state.epic_lane, epic_oid) == 2
    assert fixture.is_ancestor(state.epic_lane, state.child_oid, epic_oid)
    assert fixture.is_ancestor(state.epic_lane, remote_epic_oid, epic_oid)
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
    assert tm.ok(
        u.Infra.git_ref_exists(
            m.Infra.GitRefRequest(
                repo_root=fixture.repository,
                reference=f"refs/heads/{state.epic_branch}",
            )
        )
    ).value


__all__: tuple[str, ...] = ()
