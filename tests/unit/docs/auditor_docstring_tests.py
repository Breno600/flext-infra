"""Behavior tests for docstring coverage in the docs audit pipeline.

Real packages on disk (no mocks): a synthetic project with one documented
and one undocumented public export must report 50% coverage through both
the utility metric and the persisted audit reports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import config
from flext_infra.docs.auditor import FlextInfraDocAuditor
from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class TestsFlextInfraAuditorDocstring:
    """Unit under test: docstring coverage metric + audit report integration."""

    _FULL_COVERAGE_PERCENT = 100.0
    _PARTIAL_COVERAGE_THRESHOLD = 80.0

    @staticmethod
    def _audit_warns() -> bool:
        """Read the audit posture from the same typed SSOT production reads."""
        return "audit" in config.Infra.codegen.make.docs.warning_actions

    def _assert_verdict(self, result: p.Result[bool]) -> None:
        """The execute verdict follows the configured audit posture."""
        if self._audit_warns():
            tm.ok(result)
        else:
            tm.fail(result)

    _PACKAGE_INIT = '''"""Demo package."""


def documented_fn() -> str:
    """Return a documented value."""
    return "documented"


def undocumented_fn() -> str:
    return "undocumented"


__all__ = ["documented_fn", "undocumented_fn"]
'''

    def _write_project(self, tmp_path: Path) -> Path:
        project = tmp_path / "flext-demo"
        package = project / "src" / "flext_demo"
        package.mkdir(parents=True)
        (project / "pyproject.toml").write_text(
            '[project]\nname = "flext-demo"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        (package / "__init__.py").write_text(self._PACKAGE_INIT, encoding="utf-8")
        u.Tests.write_beads_project(
            project,
            workspace="flext-demo",
            database="flext-demo",
            issue_prefix="flext-demo",
        )
        # The audit resolves the project's own Git identity; the fixture never
        # borrows an enclosing repository.
        u.Tests.initialize_git_repo(
            project, origin_url=u.Tests.repository_ref("flext-demo").url
        )
        return project

    def test_partial_docstrings_report_ratio(self, tmp_path: Path) -> None:
        project = self._write_project(tmp_path)
        contract = u.Infra.public_contract(project, "flext_demo")

        coverage = u.Infra.docstring_coverage(project, contract)

        tm.that(coverage.checked > 0, eq=True)
        tm.that(coverage.documented > 0, eq=True)
        tm.that(coverage.documented < coverage.checked, eq=True)
        tm.that(
            coverage.percent,
            eq=round(100.0 * coverage.documented / coverage.checked, 1),
        )

    def test_empty_contract_reports_full_coverage(self, tmp_path: Path) -> None:
        coverage = u.Infra.docstring_coverage(tmp_path, {})

        tm.that(coverage.checked, eq=0)
        tm.that(coverage.documented, eq=0)
        tm.that(coverage.percent, eq=pytest.approx(100.0))

    def test_root_scope_has_no_coverage_metric(self, tmp_path: Path) -> None:
        scope = m.Infra.DocScope(
            name="root", path=tmp_path, report_dir=tmp_path / ".reports/docs"
        )

        tm.that(u.Infra.docs_public_docstring_coverage(scope), none=True)

    def test_project_scope_reports_include_coverage(self, tmp_path: Path) -> None:
        project = self._write_project(tmp_path)
        report_dir = project / ".reports/docs"
        scope = m.Infra.DocScope(
            name="flext-demo",
            path=project,
            report_dir=report_dir,
            project_class="project",
            package_name="flext_demo",
        )

        report = FlextInfraDocAuditor().audit_scope(
            scope, params=m.Infra.AuditScopeParams(check="docstrings")
        )
        warns = "audit" in config.Infra.codegen.make.docs.warning_actions
        tm.that(report.passed, eq=warns)
        tm.that(report.items, empty=False)

        markdown = (report_dir / "audit-report.md").read_text(encoding="utf-8")
        tm.that(markdown, has="Docstring coverage:")
        summary = u.Tests.json_payload(
            (report_dir / "audit-summary.json").read_text(encoding="utf-8")
        )
        metric = u.Tests.toml_mapping(
            u.Tests.toml_mapping(summary["summary"])["docstring_coverage"]
        )
        checked = metric["checked"]
        percent = metric["percent"]
        assert isinstance(checked, int)
        assert isinstance(percent, float)
        tm.that(checked > 0, eq=True)
        tm.that(0.0 <= percent < self._FULL_COVERAGE_PERCENT, eq=True)

    def test_checks_docstrings_runs_only_that_check(self, tmp_path: Path) -> None:
        project = self._write_project(tmp_path)

        result = FlextInfraDocAuditor(
            repository_root=project, checks="docstrings"
        ).execute()

        self._assert_verdict(result)
        summary = u.Tests.json_payload(
            (project / ".reports/docs/audit-summary.json").read_text(encoding="utf-8")
        )
        summary = u.Tests.toml_mapping(summary["summary"])
        tm.that(summary["checks"], eq=["docstrings"])
        tm.that(u.Tests.number(summary["issues"]), gt=0)
        coverage = u.Tests.toml_mapping(summary["docstring_coverage"])
        checked = coverage["checked"]
        assert isinstance(checked, int)
        tm.that(checked > 0, eq=True)

    def test_default_checks_runs_full_suite(self, tmp_path: Path) -> None:
        project = self._write_project(tmp_path)

        result = FlextInfraDocAuditor(repository_root=project).execute()

        self._assert_verdict(result)
        summary = u.Tests.json_payload(
            (project / ".reports/docs/audit-summary.json").read_text(encoding="utf-8")
        )
        summary = u.Tests.toml_mapping(summary["summary"])
        tm.that(summary["checks"], has="docstrings")
        tm.that(summary["checks"], has="links")
        tm.that(u.Tests.number(summary["issues"]), gt=0)

    def test_coverage_below_minimum_follows_configured_posture(
        self, tmp_path: Path
    ) -> None:
        project = self._write_project(tmp_path)

        result = FlextInfraDocAuditor(
            repository_root=project, checks="docstrings", docstring_min=80.0
        ).execute()

        self._assert_verdict(result)
        summary = u.Tests.json_payload(
            (project / ".reports/docs/audit-summary.json").read_text(encoding="utf-8")
        )
        summary = u.Tests.toml_mapping(summary["summary"])
        tm.that(
            (
                u.Tests.number(
                    u.Tests.toml_mapping(summary["docstring_coverage"])["percent"]
                )
                < self._PARTIAL_COVERAGE_THRESHOLD
            ),
            eq=True,
        )

    def test_coverage_above_minimum_keeps_every_finding(self, tmp_path: Path) -> None:
        project = self._write_project(tmp_path)

        result = FlextInfraDocAuditor(
            repository_root=project, checks="docstrings", docstring_min=40.0
        ).execute()

        self._assert_verdict(result)
        if not self._audit_warns():
            tm.that(result.error, has="issues:")

    def test_no_threshold_still_reports_missing_docstrings(
        self, tmp_path: Path
    ) -> None:
        project = self._write_project(tmp_path)

        result = FlextInfraDocAuditor(
            repository_root=project, checks="docstrings"
        ).execute()

        self._assert_verdict(result)
        if not self._audit_warns():
            tm.that(result.error, has="issues:")

    def test_coverage_floor_applies_with_other_selected_checks(
        self, tmp_path: Path
    ) -> None:
        """Selecting links cannot silently disable an explicit coverage floor."""
        project = self._write_project(tmp_path)
        result = FlextInfraDocAuditor(
            repository_root=project, checks="links", docstring_min=80.0
        ).execute()
        self._assert_verdict(result)
        if not self._audit_warns():
            tm.that(result.error, has="below minimum")

    def test_fully_documented_package_passes(self, tmp_path: Path) -> None:
        """Repairing the finding, rather than lowering a floor, makes it pass."""
        project = self._write_project(tmp_path)
        package_init = project / "src/flext_demo/__init__.py"
        package_init.write_text(
            self._PACKAGE_INIT.replace(
                "def undocumented_fn() -> str:\n",
                "def undocumented_fn() -> str:\n"
                '    """Return an undocumented label."""\n',
            ),
            encoding="utf-8",
        )
        result = FlextInfraDocAuditor(
            repository_root=project, checks="docstrings", docstring_min=100.0
        ).execute()
        tm.ok(result)
