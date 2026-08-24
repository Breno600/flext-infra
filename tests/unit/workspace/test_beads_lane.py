"""Verify Beads ledger ownership for workspace members."""

from __future__ import annotations

from pathlib import Path

import pytest

from flext_infra import c, m, u
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from flext_tests import tm
from tests import u as test_u


def _repository(root: Path, *, ledger_id: str) -> Path:
    root.mkdir()
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    repository = test_u.Tests.repository_ref(root.name).model_copy(
        update={"path": Path(), "package": False, "editable": False}
    )
    workspace = m.Infra.WorkspaceSpec(
        version=c.Infra.WORKSPACE_MANIFEST_VERSION,
        name=repository.distribution,
        repository=repository,
        ledger_id=ledger_id,
        # A tracker-owning manifest declares both identifiers (mro-cdzxf).
        ledger_prefix=ledger_id,
    )
    tm.ok(
        u.Cli.yaml_dump(
            root / "config" / "workspace.yaml",
            workspace.model_dump(mode="json", exclude_none=True),
        )
    )
    test_u.Tests.initialize_git_repo(root)
    return root


def test_submodule_routes_to_governing_workspace_ledger(tmp_path: Path) -> None:
    workspace = _repository(tmp_path / "workspace", ledger_id="workspace-ledger")
    member_source = _repository(tmp_path / "member-source", ledger_id="member-ledger")
    tm.ok(
        test_u.Cli.run_checked(
            [
                c.Infra.GIT,
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                str(member_source),
                "member",
            ],
            cwd=workspace,
        )
    )
    member = workspace / "member"
    member_beads = member / ".beads"
    member_beads.mkdir()
    declaration = m.Infra.BeadsTrackerDeclaration(issue_prefix="member-local")
    (member_beads / "config.yaml").write_text(
        f'issue-prefix: "{declaration.issue_prefix}"\n', encoding="utf-8"
    )

    resolved = tm.ok(u.Infra.beads_resolve_root(member))

    assert resolved == workspace.resolve()


def test_beads_root_resolution_is_cached_per_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Repeated resolution of one anchor does not repeat the workspace scan.

    Every ``bd`` invocation resolves the governing ledger first. Re-running the
    full detector plus workspace-spec load on each call made a single make-work
    saga pay it 199 times (19.34s of a 120s suite budget, cProfile mro-38p39).
    Workspace identity is immutable for the life of the process, so the second
    resolution of the same anchor must be served without re-scanning.
    """
    workspace = _repository(tmp_path / "workspace", ledger_id="workspace-ledger")

    first = tm.ok(u.Infra.beads_resolve_root(workspace))

    def _forbidden(_start: Path) -> object:
        message = "resolve_workspace_root re-scanned an already-resolved anchor"
        raise AssertionError(message)

    monkeypatch.setattr(
        FlextInfraWorkspaceDetector, "resolve_workspace_root", _forbidden
    )
    second = tm.ok(u.Infra.beads_resolve_root(workspace))

    assert second == first
