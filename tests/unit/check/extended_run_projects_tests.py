"""Public tests for workspace checker project execution.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRunProjects:
    """Verify project execution through the public checker methods."""

    @staticmethod
    def test_empty_gate_selection_fails(tmp_path: Path) -> None:
        """Test empty gate selection fails."""
        project = u.Tests.mk_project(tmp_path, "p1", with_src=True)
        (project / "src" / "test.py").write_text("value = 1\n", encoding="utf-8")
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)

        result = checker.run_projects(["p1"], [], reports_dir=tmp_path / "reports")

        tm.fail(result, has="at least one quality gate is required")

    @staticmethod
    def test_invalid_gates_fail(tmp_path: Path) -> None:
        """Test invalid gates fail."""
        result = FlextInfraWorkspaceChecker(repository_root=tmp_path).run_projects(
            ["p1"],
            ["invalid_gate"],
            reports_dir=tmp_path / "reports",
        )

        tm.fail(result)

    @staticmethod
    def test_project_without_pyproject_fails_loudly(tmp_path: Path) -> None:
        """Test project without pyproject fails loudly."""
        u.Tests.mk_project(tmp_path, "p1", with_src=True)
        result = FlextInfraWorkspaceChecker(repository_root=tmp_path).run_projects(
            ["p1", "nonexistent"],
            ["lint"],
            reports_dir=tmp_path / "reports",
        )

        tm.fail(result, has=str(tmp_path / "nonexistent" / c.PYPROJECT_FILENAME))
        tm.that((tmp_path / "reports" / "p1").exists(), eq=False)

    @staticmethod
    def test_empty_project_selection_fails_loudly(tmp_path: Path) -> None:
        """Test empty project selection fails loudly."""
        result = FlextInfraWorkspaceChecker(repository_root=tmp_path).run_projects(
            [],
            ["lint"],
            reports_dir=tmp_path / "reports",
        )

        tm.fail(result, has="selected no projects")

    @staticmethod
    @pytest.mark.parametrize(
        "report_name",
        [c.Infra.CHECK_REPORT_MARKDOWN_FILENAME, c.Infra.CHECK_REPORT_SARIF_FILENAME],
    )
    def test_run_projects_creates_reports(
        tmp_path: Path,
        report_name: str,
    ) -> None:
        """Test run projects creates reports."""
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)
        project_dir = u.Tests.mk_project(tmp_path, "p1", with_src=True)
        (project_dir / "src" / "test.py").write_text("value = 1\n", encoding="utf-8")

        result = checker.run_projects(
            ["p1"],
            ["lint"],
            reports_dir=tmp_path / "reports",
        )

        tm.ok(result)
        tm.that(tuple(result.value[0].gates), eq=("lint",))
        receipt = result.value[0].gates["lint"].raw_receipt
        assert receipt is not None
        tm.that((receipt.parent.parent / report_name).exists(), eq=True)
        tm.that(receipt.parent.parent.parent, eq=tmp_path / "reports")

    @staticmethod
    def test_run_projects_creates_project_scoped_reports_dir(
        tmp_path: Path,
    ) -> None:
        """Test run projects creates project scoped reports dir."""
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)
        project_dir = u.Tests.mk_project(tmp_path, "p1", with_src=True)
        (project_dir / "src" / "test.py").write_text("value = 1\n", encoding="utf-8")

        result = checker.run_projects(
            ["p1"],
            ["lint"],
            reports_dir=tmp_path / "reports",
        )

        tm.ok(result)
        receipt = result.value[0].gates["lint"].raw_receipt
        assert receipt is not None
        tm.that(receipt.parent.name, eq="p1")
        tm.that(receipt.parent.parent.parent, eq=tmp_path / "reports")

    @staticmethod
    def test_fail_fast_stops_after_first_failed_project(tmp_path: Path) -> None:
        """Test fail fast stops after first failed project."""
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)
        for name in ("p1", "p2", "p3"):
            project_dir = u.Tests.mk_project(tmp_path, name, with_src=True)
            (project_dir / "src" / "test.py").write_text(
                "import os\nimport os\n",
                encoding="utf-8",
            )
        result = checker.run_projects(
            ["p1", "p2", "p3"],
            ["lint"],
            reports_dir=tmp_path / "reports",
            fail_fast=True,
        )

        tm.ok(result)
        tm.that(len(result.value), eq=1)

    @staticmethod
    def test_run_projects_reports_mixed_project_errors(tmp_path: Path) -> None:
        """Test run projects reports mixed project errors."""
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)
        for name in ("p1", "p2"):
            project_dir = u.Tests.mk_project(tmp_path, name, with_src=True)
            (project_dir / "src" / "test.py").write_text(
                "value = 1\n",
                encoding="utf-8",
            )
        p1 = tmp_path / "p1"
        (p1 / "src" / "test.py").write_text("import os\nimport os\n", encoding="utf-8")
        result = checker.run_projects(
            ["p1", "p2"],
            ["lint"],
            reports_dir=tmp_path / "reports",
        )

        tm.ok(result)
        tm.that(len(result.value), eq=2)
        tm.that(result.value[0].total_findings > 0, eq=True)
        tm.that(result.value[1].total_findings, eq=0)

    @staticmethod
    def test_run_project_returns_single_project_result(tmp_path: Path) -> None:
        """Test run project returns single project result."""
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)
        project_dir = u.Tests.mk_project(tmp_path, "p1", with_src=True)
        (project_dir / "src" / "test.py").write_text("value = 1\n", encoding="utf-8")

        result = checker.run_project("p1", ["lint"])

        tm.ok(result)
        tm.that(len(result.value), eq=1)
