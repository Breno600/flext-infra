"""Shared fixture input for workspace work-saga tests."""

from __future__ import annotations

from pathlib import Path


def declare_workspace_ledger(repository: Path) -> None:
    """Install the canonical Beads fixture owned by this test package."""
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "workspace-beads.yaml"
    target = repository / "config" / "beads.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(fixture.read_bytes())


__all__: list[str] = ["declare_workspace_ledger"]
