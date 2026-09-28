"""A selected census must never report success without selecting a project."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.gates.runtime_census import FlextInfraRuntimeCensusGate
from tests import m

if TYPE_CHECKING:
    from pathlib import Path


class TestRuntimeCensusSelection:
    """Empty discovery is a broken invocation, not evidence of conformance."""

    def test_empty_checkout_fails_the_gate(self, tmp_path: Path) -> None:
        context = m.Infra.GateContext(
            repository_root=tmp_path, reports_dir=tmp_path / ".reports"
        )
        gate = FlextInfraRuntimeCensusGate(repository_root=tmp_path)
        result = gate.check(tmp_path, context).result
        tm.that(result.passed, eq=False)
        tm.that(" | ".join(result.errors), has="no projects")
