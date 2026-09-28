"""Public FINISH preserves real merge-conflict state."""

from pathlib import Path

import pytest
from flext_tests import tm

from tests.unit import WorkAdversarialFixture

# Why (suite budget): full child FINISH saga over real epic/child worktrees
# with subprocess git and beads calls; the per-case wall only holds idle.
pytestmark = pytest.mark.slow


def test_child_finish_conflict_preserves_both_lanes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = WorkAdversarialFixture.create(tmp_path, monkeypatch)
    state = fixture.conflicting_finish_state()
    before = fixture.metadata_snapshot(state)

    result = fixture.finish_child(state)

    tm.fail(result, has="merge-forward failed")
    tm.fail(result, has="CONFLICT")
    assert fixture.both_lanes_registered(state)
    assert fixture.metadata_snapshot(state) == before
    assert fixture.has_unmerged_paths(state.epic_lane)


__all__: tuple[str, ...] = ()
