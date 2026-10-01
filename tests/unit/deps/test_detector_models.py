"""Test detector models behavior."""

from __future__ import annotations

from flext_tests import tm

from tests import m


class TestsFlextInfraDepsDetectorModels:
    """Test flext infra deps detector models behavior."""

    def test_dependency_limits_info_creation(self) -> None:
        """Verify dependency limits info creation."""
        info = m.Infra.DependencyLimitsInfo(python_version=None, limits_path="")
        tm.that(info.python_version, eq=None)
        tm.that(info.limits_path, eq="")

    def test_pip_check_report_creation(self) -> None:
        """Verify pip check report creation."""
        report = m.Infra.PipCheckReport(ok=True, lines=[])
        tm.that(report.ok, eq=True)
        tm.that(report.lines, empty=True)

    def test_workspace_dependency_report_creation(self) -> None:
        """Verify workspace dependency report creation."""
        report = m.Infra.WorkspaceDependencyReport(
            workspace="test-workspace", projects={}
        )
        tm.that(report.workspace, eq="test-workspace")
        tm.that(report.projects, empty=True)
        tm.that(report.pip_check, eq=None)
        tm.that(report.dependency_limits, eq=None)
