"""Parent LAND is contained by child retirement."""

from pathlib import Path

import pytest
from flext_tests import tm

from tests.unit import WorkAdversarialFixture


# Why (suite budget): parent LAND saga over real epic/child worktrees with
# subprocess git and gh calls; the per-case wall only holds idle.
@pytest.mark.slow
def test_parent_land_refuses_registered_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = WorkAdversarialFixture.create(tmp_path, monkeypatch)
    state = fixture.finish.start_and_land()

    tm.fail(fixture.land_parent(state), has="children are registered")
    assert fixture.both_lanes_registered(state)


# Why (suite budget): full child finish + parent land saga over real epic and
# child worktrees with remote merges; the per-case wall only holds idle.
@pytest.mark.slow
def test_parent_land_after_child_finish_contains_child_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = WorkAdversarialFixture.create(tmp_path, monkeypatch)
    state = fixture.divergent_finish_state()
    tm.ok(fixture.finish_child(state))

    tm.ok(fixture.land_parent(state))

    receipt = fixture.finish.boundary.pr_create_receipt()
    assert receipt.base == "0.12.0-dev"
    assert receipt.head == state.epic_branch
    assert fixture.remote_parent_contains_child(state)
    assert fixture.registered_children(state) == ()


__all__: tuple[str, ...] = ()
