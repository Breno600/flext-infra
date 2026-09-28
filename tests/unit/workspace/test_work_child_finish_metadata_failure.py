"""Public FINISH preserves lanes after epic metadata failure."""

from pathlib import Path

import pytest
from flext_tests import tm

from tests.unit import WorkAdversarialFixture

# Why (suite budget): full child FINISH saga over real epic/child worktrees
# with subprocess git and beads calls; the per-case wall only holds idle.
pytestmark = pytest.mark.slow


def test_child_finish_epic_metadata_failure_preserves_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = WorkAdversarialFixture.create(tmp_path, monkeypatch)
    state = fixture.divergent_finish_state()
    old_epic_oid = fixture.finish.ready_metadata(state.epic_bead).head_oid
    fixture.fail_updates_for(state.epic_bead)

    result = fixture.finish_child(state)

    tm.fail(result, has="selected bd update refused")
    new_epic_oid = fixture.finish.oid(state.epic_lane, "HEAD")
    assert new_epic_oid != old_epic_oid
    assert fixture.finish.parent_count(state.epic_lane, new_epic_oid) == 2
    assert fixture.finish.ready_metadata(state.epic_bead).head_oid == old_epic_oid
    assert fixture.both_lanes_registered(state)


__all__: tuple[str, ...] = ()
