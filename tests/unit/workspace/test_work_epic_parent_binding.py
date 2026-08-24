"""Verify live epic and child parent authorization."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from flext_infra import FlextInfraWorkService, c
from flext_tests import tm
from tests.unit.workspace.test_work_service import (
    TestsFlextInfraWorkService as _WorkFixture,
)

type JsonObject = dict[str, JsonValue]
type JsonValue = str | int | bool | list[JsonValue] | JsonObject | None


def _store(tmp_path: Path) -> tuple[Path, JsonObject]:
    path = tmp_path / "beads-store.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def _issue(store: JsonObject, bead_id: str) -> JsonObject:
    issue = store[bead_id]
    assert isinstance(issue, dict)
    return issue


def _metadata(store: JsonObject, bead_id: str) -> JsonObject:
    metadata = _issue(store, bead_id)["metadata"]
    assert isinstance(metadata, dict)
    return metadata


def _write(path: Path, store: JsonObject) -> None:
    path.write_text(json.dumps(store), encoding="utf-8")


def _start_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, str, str, Path]:
    repository = _WorkFixture._repository(tmp_path)  # ruff: ignore[private-member-access]
    epic, child = "mro-real-epic", "mro-real-child"
    shim = _WorkFixture._install_bd_shim(  # ruff: ignore[private-member-access]
        tmp_path,
        epic,
        child,
        issue_types={epic: "epic", child: "task"},
        parents={child: epic},
    )
    _WorkFixture._install_gh_shim(tmp_path)  # ruff: ignore[private-member-access]
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ.get('PATH', '')}")
    tm.ok(
        FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=epic,
            name="real-epic",
            base="HEAD",
            apply_changes=True,
        ).execute()
    )
    tm.ok(
        FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=child,
            name="real-child",
            epic=epic,
            apply_changes=True,
        ).execute()
    )
    _, store = _store(tmp_path)
    worktree = _metadata(store, child)["worktree"]
    assert isinstance(worktree, str)
    return repository, epic, child, Path(worktree)


@pytest.mark.parametrize("parent", [None, "mro-other"])
def test_child_selector_rejects_missing_or_wrong_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parent: str | None
) -> None:
    repository = _WorkFixture._repository(tmp_path)  # ruff: ignore[private-member-access]
    epic, child = "mro-parent-epic", "mro-parent-child"
    parents = {} if parent is None else {child: parent}
    shim = _WorkFixture._install_bd_shim(  # ruff: ignore[private-member-access]
        tmp_path,
        epic,
        child,
        issue_types={epic: "epic", child: "task"},
        parents=parents,
    )
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ.get('PATH', '')}")
    tm.ok(
        FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=epic,
            name="parent-epic",
            base="HEAD",
            apply_changes=True,
        ).execute()
    )
    result = FlextInfraWorkService(
        workspace_root=repository,
        operation=c.Infra.WorkOperation.START,
        bead=child,
        name="child",
        epic=epic,
        apply_changes=True,
    ).execute()
    tm.fail(result, has="parent mismatch")


def test_epic_selector_rejects_non_epic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _WorkFixture._repository(tmp_path)  # ruff: ignore[private-member-access]
    epic, child = "mro-not-epic", "mro-wrong-parent"
    shim = _WorkFixture._install_bd_shim(  # ruff: ignore[private-member-access]
        tmp_path,
        epic,
        child,
        issue_types={epic: "task", child: "task"},
        parents={child: epic},
    )
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ.get('PATH', '')}")
    tm.ok(
        FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=epic,
            name="not-epic",
            base="HEAD",
            apply_changes=True,
        ).execute()
    )
    result = FlextInfraWorkService(
        workspace_root=repository,
        operation=c.Infra.WorkOperation.START,
        bead=child,
        name="child",
        epic=epic,
        apply_changes=True,
    ).execute()
    tm.fail(result, has="issue_type=epic")


def test_valid_direct_parent_starts_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, epic, _, child_lane = _start_pair(tmp_path, monkeypatch)
    assert child_lane.is_dir()
    assert child_lane.parent.parent.name == "real-epic"
    path, store = _store(tmp_path)
    assert _metadata(store, epic)["role"] == "epic"
    assert _metadata(store, epic)["branch"] == "epic/real-epic"
    assert path.is_file()


@pytest.mark.parametrize(
    "operation",
    [
        c.Infra.WorkOperation.STATUS,
        c.Infra.WorkOperation.LAND,
        c.Infra.WorkOperation.FINISH,
    ],
)
def test_reparented_child_refuses_every_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: c.Infra.WorkOperation
) -> None:
    repository, _, child, child_lane = _start_pair(tmp_path, monkeypatch)
    path, store = _store(tmp_path)
    _issue(store, child)["parent"] = "mro-other"
    _write(path, store)
    result = FlextInfraWorkService(
        workspace_root=repository, operation=operation, bead=child, apply_changes=True
    ).execute()
    tm.fail(result, has="parent")
    assert child_lane.is_dir()


@pytest.mark.parametrize(
    ("tamper", "value"),
    [
        ("issue_type", "task"),
        ("status", "closed"),
        ("role", "plain"),
        ("epic_bead", "mro-other"),
        ("branch", "epic/tampered"),
        ("worktree", "tampered"),
        ("provisioning", "pending"),
    ],
)
def test_tampered_epic_refuses_child_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tamper: str, value: str
) -> None:
    repository, epic, child, child_lane = _start_pair(tmp_path, monkeypatch)
    path, store = _store(tmp_path)
    target = (
        _metadata(store, epic)
        if tamper in {"role", "epic_bead", "branch", "worktree", "provisioning"}
        else _issue(store, epic)
    )
    target[tamper] = value
    _write(path, store)
    result = FlextInfraWorkService(
        workspace_root=repository,
        operation=c.Infra.WorkOperation.STATUS,
        bead=child,
        apply_changes=False,
    ).execute()
    tm.fail(result)
    assert child_lane.is_dir()


__all__: tuple[str, ...] = ()
