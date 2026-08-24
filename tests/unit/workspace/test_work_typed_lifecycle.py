"""Public work operations reject tampered typed lane state."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from flext_infra import FlextInfraWorkService, c
from flext_tests import tm
from tests.unit.workspace.test_work_service import (
    TestsFlextInfraWorkService as _WorkFixture,
)


def test_status_rejects_tampered_child_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _WorkFixture._repository(tmp_path)  # ruff: ignore[private-member-access]
    bead_id = "mro-test-tampered-child"
    shim_dir = _WorkFixture._install_bd_shim(  # ruff: ignore[private-member-access]
        tmp_path, bead_id
    )
    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    _WorkFixture._set_metadata(  # ruff: ignore[private-member-access]
        tmp_path,
        bead_id,
        {
            "branch": "feature/tampered-child",
            "namespace": "feature",
            "worktree": str(tmp_path / "tampered-child"),
            "kind": "feature",
            "slug": "tampered-child",
            "integration_base": "0.12.0-dev",
            "head_oid": "a" * 40,
            "provisioning": "ready",
            "role": "child",
            "epic_bead": "mro-epic",
        },
    )

    result = FlextInfraWorkService(
        workspace_root=repository,
        operation=c.Infra.WorkOperation.STATUS,
        bead=bead_id,
        apply_changes=False,
    ).execute()

    tm.fail(result, has="Beads issue validation failed")


__all__: tuple[str, ...] = ()
