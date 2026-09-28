"""Public work operations enforce unique live Beads reservation ownership."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraWorkService, FlextInfraWorktreeService, c
from tests import t, u
from tests.unit.workspace.work_service_fixture import WorkServiceFixture as _WorkFixture


def _record(tmp_path: Path, bead_id: str, metadata: dict[str, str]) -> None:
    store_path = tmp_path / "beads-store.json"
    store = t.json_dict_adapter().validate_python(
        u.Cli.json_loads(store_path.read_text(encoding="utf-8")).unwrap()
    )
    store[bead_id] = {
        "id": bead_id,
        "status": "open",
        "issue_type": "feature",
        "parent": None,
        "metadata": t.json_value_adapter().validate_python(metadata),
        "labels": [],
    }
    store_path.write_text(u.Cli.json_dumps(store).unwrap(), encoding="utf-8")


def test_foreign_bead_cannot_start_reserved_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _WorkFixture._repository(tmp_path)  # ruff: ignore[private-member-access]
    bead_a, bead_b = "mro-owner-a", "mro-owner-b"
    shim = _WorkFixture._install_bd_shim(  # ruff: ignore[private-member-access]
        tmp_path, bead_a, bead_b
    )
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ.get('PATH', '')}")
    branch = "feature/reserved"
    path = tm.ok(FlextInfraWorktreeService.canonical_lane_path(repository, branch))
    _record(
        tmp_path,
        bead_a,
        {
            "branch": branch,
            "namespace": "feature",
            "worktree": str(path),
            "kind": "feature",
            "slug": "reserved",
            "integration_base": "HEAD",
            "provisioning": "pending",
            "role": "plain",
        },
    )

    result = FlextInfraWorkService(
        workspace_root=repository,
        operation=c.Infra.WorkOperation.START,
        bead=bead_b,
        kind=c.Infra.WorkKind.FEATURE,
        name="reserved",
        base="HEAD",
        apply_changes=True,
    ).execute()

    tm.fail(result, has=f"foreign bead {bead_a}")
    assert not path.exists()


def test_closed_reservation_does_not_block_new_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _WorkFixture._repository(tmp_path)  # ruff: ignore[private-member-access]
    bead_a, bead_b = "mro-history-a", "mro-history-b"
    shim = _WorkFixture._install_bd_shim(  # ruff: ignore[private-member-access]
        tmp_path, bead_a, bead_b
    )
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ.get('PATH', '')}")
    branch = "feature/history"
    path = tm.ok(FlextInfraWorktreeService.canonical_lane_path(repository, branch))
    _record(
        tmp_path,
        bead_a,
        {
            "branch": branch,
            "namespace": "feature",
            "worktree": str(path),
            "kind": "feature",
            "slug": "history",
            "integration_base": "HEAD",
            "provisioning": "ready",
            "head_oid": "a" * 40,
            "role": "plain",
        },
    )
    store_path = tmp_path / "beads-store.json"
    store = t.json_dict_adapter().validate_python(
        u.Cli.json_loads(store_path.read_text(encoding="utf-8")).unwrap()
    )
    issue = t.json_dict_adapter().validate_python(store[bead_a])
    issue["status"] = "closed"
    store[bead_a] = issue
    store_path.write_text(u.Cli.json_dumps(store).unwrap(), encoding="utf-8")

    result = FlextInfraWorkService(
        workspace_root=repository,
        operation=c.Infra.WorkOperation.START,
        bead=bead_b,
        kind=c.Infra.WorkKind.FEATURE,
        name="history",
        base="HEAD",
        apply_changes=True,
    ).execute()

    tm.that(tm.ok(result), has=f"BRANCH={branch}")


@pytest.mark.parametrize(
    "operation", [c.Infra.WorkOperation.LAND, c.Infra.WorkOperation.FINISH]
)
def test_poisoned_foreign_metadata_cannot_mutate_owner_lane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: c.Infra.WorkOperation
) -> None:
    repository = _WorkFixture._repository(tmp_path)  # ruff: ignore[private-member-access]
    bead_a, bead_b = "mro-protected-a", "mro-poison-b"
    shim = _WorkFixture._install_bd_shim(  # ruff: ignore[private-member-access]
        tmp_path, bead_a, bead_b
    )
    _WorkFixture._install_gh_shim(tmp_path)  # ruff: ignore[private-member-access]
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ.get('PATH', '')}")
    tm.ok(
        FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=bead_a,
            kind=c.Infra.WorkKind.FEATURE,
            name="protected",
            base="HEAD",
            apply_changes=True,
        ).execute()
    )
    store_path = tmp_path / "beads-store.json"
    store = t.json_dict_adapter().validate_python(
        u.Cli.json_loads(store_path.read_text(encoding="utf-8")).unwrap()
    )
    foreign_issue = t.json_dict_adapter().validate_python(store[bead_b])
    owner_issue = t.json_dict_adapter().validate_python(store[bead_a])
    foreign_issue["metadata"] = t.json_dict_adapter().validate_python(
        owner_issue["metadata"]
    )
    store[bead_b] = foreign_issue
    store_path.write_text(u.Cli.json_dumps(store).unwrap(), encoding="utf-8")
    owner_metadata = t.json_dict_adapter().validate_python(owner_issue["metadata"])
    owner_path = Path(u.Cli.json_pick_str(owner_metadata, "worktree"))

    result = FlextInfraWorkService(
        workspace_root=repository, operation=operation, bead=bead_b, apply_changes=True
    ).execute()

    tm.fail(result, has=f"owners={bead_a},{bead_b}")
    assert owner_path.is_dir()


__all__: tuple[str, ...] = ()
