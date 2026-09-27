"""A selected census must never report success without selecting a project."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.gates.runtime_census import FlextInfraRuntimeCensusGate
from flext_infra.validate.runtime_census import FlextInfraRuntimeCensusValidator
from tests import m, u

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

    def test_gate_preserves_every_census_finding(self, tmp_path: Path) -> None:
        root, package = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-census-findings",
            package_name="flext_census_findings",
        )
        (package / "constants.py").write_text(
            "from flext_core import FlextConstants\n"
            "class FlextCensusConstants(FlextConstants):\n    pass\n"
            "c = FlextCensusConstants\n"
            "__all__ = ['FlextCensusConstants', 'c']\n",
            encoding="utf-8",
        )
        context = m.Infra.GateContext(
            repository_root=root, reports_dir=root / "reports"
        )
        with tm.scope(python_paths=[str(package.parent)]):
            report = tm.ok(
                FlextInfraRuntimeCensusValidator(repository_root=root).build_report()
            )
            execution = FlextInfraRuntimeCensusGate(repository_root=root).check(
                root, context
            )
        tm.that(bool(report.violations), eq=True)
        tm.that(execution.result.passed, eq=False)
        tm.that(
            tuple(issue.message for issue in execution.issues), eq=report.violations
        )
