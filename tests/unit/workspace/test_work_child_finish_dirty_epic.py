"""Public FINISH refuses dirty epic state before remote mutation."""

from pathlib import Path

import pytest
from flext_tests import tm

from tests.unit import WorkAdversarialFixture

# Why (suite budget): full child FINISH saga over real epic/child worktrees
# with subprocess git and beads calls; the per-case wall only holds idle.
pytestmark = pytest.mark.slow


def test_child_finish_dirty_epic_preserves_all_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = WorkAdversarialFixture.create(tmp_path, monkeypatch)
    state = fixture.divergent_finish_state()
    before = fixture.metadata_snapshot(state)
    remote_before = fixture.remote_epic_oid(state)
    fixture.dirty_epic(state)

    result = fixture.finish_child(state)

    tm.fail(result, has="epic lane is dirty")
    assert fixture.metadata_snapshot(state) == before
    assert fixture.remote_epic_oid(state) == remote_before
    assert fixture.both_lanes_registered(state)


__all__: tuple[str, ...] = ()
