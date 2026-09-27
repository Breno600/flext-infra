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

    def test_empty_gate_selection_fails(self, tmp_path: Path) -> None:
        project = u.Tests.mk_project(tmp_path, "p1", with_src=True)
        (project / "src" / "test.py").write_text("value = 1\n", encoding="utf-8")
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)

        result = checker.run_projects(["p1"], [], reports_dir=tmp_path / "reports")

        tm.fail(result, has="at least one quality gate is required")

    def test_invalid_gates_fail(self, tmp_path: Path) -> None:
        result = FlextInfraWorkspaceChecker(repository_root=tmp_path).run_projects(
            ["p1"], ["invalid_gate"], reports_dir=tmp_path / "reports"
        )

        tm.fail(result)

    def test_missing_projects_are_skipped(self, tmp_path: Path) -> None:
        result = FlextInfraWorkspaceChecker(repository_root=tmp_path).run_projects(
            ["nonexistent"], ["lint"], reports_dir=tmp_path / "reports"
        )

        tm.ok(result)
        tm.that(result.value, eq=())

    @pytest.mark.parametrize(
        "report_name",
        [c.Infra.CHECK_REPORT_MARKDOWN_FILENAME, c.Infra.CHECK_REPORT_SARIF_FILENAME],
    )
    def test_run_projects_creates_reports(
        self, tmp_path: Path, report_name: str
    ) -> None:
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)
        project_dir = u.Tests.mk_project(tmp_path, "p1", with_src=True)
        (project_dir / "src" / "test.py").write_text("value = 1\n", encoding="utf-8")

        result = checker.run_projects(
            ["p1"], ["lint"], reports_dir=tmp_path / "reports"
        )

        tm.ok(result)
        tm.that((tmp_path / "reports" / report_name).exists(), eq=True)

    def test_run_projects_creates_project_scoped_reports_dir(
        self, tmp_path: Path
    ) -> None:
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)
        project_dir = u.Tests.mk_project(tmp_path, "p1", with_src=True)
        (project_dir / "src" / "test.py").write_text("value = 1\n", encoding="utf-8")

        result = checker.run_projects(
            ["p1"], ["lint"], reports_dir=tmp_path / "reports"
        )

        tm.ok(result)
        tm.that((tmp_path / "reports" / "p1").is_dir(), eq=True)

    def test_fail_fast_stops_after_first_failed_project(self, tmp_path: Path) -> None:
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)
        for name in ("p1", "p2", "p3"):
            project_dir = u.Tests.mk_project(tmp_path, name, with_src=True)
            (project_dir / "src" / "test.py").write_text(
                "import os\nimport os\n", encoding="utf-8"
            )
        result = checker.run_projects(
            ["p1", "p2", "p3"],
            ["lint"],
            reports_dir=tmp_path / "reports",
            fail_fast=True,
        )

        tm.ok(result)
        tm.that(len(result.value), eq=1)

    def test_run_projects_reports_mixed_project_errors(self, tmp_path: Path) -> None:
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)
        for name in ("p1", "p2"):
            project_dir = u.Tests.mk_project(tmp_path, name, with_src=True)
            (project_dir / "src" / "test.py").write_text(
                "value = 1\n", encoding="utf-8"
            )
        p1 = tmp_path / "p1"
        (p1 / "src" / "test.py").write_text("import os\nimport os\n", encoding="utf-8")
        result = checker.run_projects(
            ["p1", "p2"], ["lint"], reports_dir=tmp_path / "reports"
        )

        tm.ok(result)
        tm.that(len(result.value), eq=2)
        tm.that(result.value[0].total_errors > 0, eq=True)
        tm.that(result.value[1].total_errors, eq=0)

    def test_run_project_returns_single_project_result(self, tmp_path: Path) -> None:
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)
        project_dir = u.Tests.mk_project(tmp_path, "p1", with_src=True)
        (project_dir / "src" / "test.py").write_text("value = 1\n", encoding="utf-8")

        result = checker.run_project("p1", ["lint"])

        tm.ok(result)
        tm.that(len(result.value), eq=1)
