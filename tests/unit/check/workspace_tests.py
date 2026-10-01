"""Tests for FlextInfraWorkspaceChecker service.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_core import r
from flext_infra import c, main
from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker
from tests import u as test_u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class TestsFlextInfraWorkspaceChecker:
    """Test suite for FlextInfraWorkspaceChecker."""

    pytestmark = pytest.mark.usefixtures("_clear_make_ci_token")

    @pytest.fixture
    def _clear_make_ci_token(self) -> Iterator[None]:
        with test_u.Tests.env_vars_context(vars_to_clear=(c.Infra.PYTEST_ENV_CI,)):
            yield

    def test_init_creates_instance(
        self, tmp_path: Path, rope_workspace: p.Infra.RopeWorkspaceDsl
    ) -> None:
        """Test that checker initializes with default workspace root."""
        checker = FlextInfraWorkspaceChecker(
            repository_root=tmp_path, rope=rope_workspace
        )
        tm.that(checker, none=False)

    def test_init_with_custom_repository_root(
        self, tmp_path: Path, rope_workspace: p.Infra.RopeWorkspaceDsl
    ) -> None:
        """Test that checker accepts custom workspace root."""
        checker = FlextInfraWorkspaceChecker(
            repository_root=tmp_path, rope=rope_workspace
        )
        tm.that(checker, none=False)

    def test_execute_returns_failure(
        self, tmp_path: Path, rope_workspace: p.Infra.RopeWorkspaceDsl
    ) -> None:
        """Test that execute() returns failure with helpful message."""
        checker = FlextInfraWorkspaceChecker(
            repository_root=tmp_path, rope=rope_workspace
        )
        result = checker.execute()
        tm.fail(result)
        tm.that(result.error, is_=str)
        tm.that(result.error, is_=str)
        tm.that(result.error, has="Use execute_command() directly")

    @pytest.mark.parametrize("declared_member", [False, True])
    def test_cli_rejects_nonproject_root_without_selecting_members(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        *,
        declared_member: bool,
    ) -> None:
        """An invalid current root never widens an omitted selection to members."""
        if declared_member:
            member, _package = test_u.Tests.demo_project(tmp_path, name="member")
            test_u.Tests.declare_workspace_projects(tmp_path, (member.name,))
        test_u.Tests.initialize_git_repo(tmp_path)
        exit_code = main(["check", "run", "--repository-root", str(tmp_path)])
        tm.that(exit_code, eq=1)
        captured = capsys.readouterr()
        assert "unknown projects: ." in captured.out + captured.err

    def test_cli_requires_explicit_member_selection(self, tmp_path: Path) -> None:
        """An omitted selection checks only the repository root."""
        project_dir = test_u.Tests.mk_project(
            tmp_path,
            "flext-core",
            pyproject=(
                '[project]\nname = "flext-core"\nversion = "0.1.0"\n'
                "[tool.hatch.build.targets.wheel]\n"
                'packages = ["src/flext_core"]\n'
            ),
            with_src=True,
        )
        package_dir = project_dir / "src" / "flext_core"
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text(
            '"""Fixture package."""\n', encoding="utf-8"
        )
        (package_dir / "module.py").write_text(
            '"""Fixture module."""\n\nvalue = 1\n', encoding="utf-8"
        )
        test_u.Tests.declare_workspace_projects(tmp_path, (project_dir.name,))
        test_u.Tests.initialize_git_repo(tmp_path)

        implicit_exit_code = main([
            "check",
            "run",
            "--repository-root",
            str(tmp_path),
            "--gates",
            "lint",
        ])
        tm.that(implicit_exit_code, eq=1)
        selected_exit_code = main([
            "check",
            "run",
            "--repository-root",
            str(tmp_path),
            "--projects",
            project_dir.name,
            "--gates",
            "lint",
        ])
        tm.that(selected_exit_code, eq=0)

    def test_resolve_gates_with_valid_gates(self) -> None:
        """Test that resolve_gates normalizes valid gate names."""
        result = FlextInfraWorkspaceChecker.resolve_gates([
            "lint",
            "pyrefly",
            "mypy",
            "pyright",
        ])
        tm.ok(result)
        tm.that(result.value, eq=["lint", "pyrefly", "mypy", "pyright"])

    def test_resolve_gates_rejects_a_repeated_gate(self) -> None:
        """A gate named twice is an operator mistake, not something to absorb.

        Silently collapsing the repeat would run exactly the gates the
        operator asked for while hiding that the request did not say what
        they thought it said.
        """
        result = FlextInfraWorkspaceChecker.resolve_gates(["lint", "lint", "format"])
        tm.fail(result)
        tm.that(result.error, has="duplicate gate 'lint'")

    def test_resolve_gates_with_invalid_gate(self) -> None:
        """Test that resolve_gates fails on invalid gate name."""
        result = FlextInfraWorkspaceChecker.resolve_gates(["invalid_gate"])
        tm.fail(result)

    def test_run_projects_creates_reports_dir(
        self, tmp_path: Path, rope_workspace: p.Infra.RopeWorkspaceDsl
    ) -> None:
        """Test that run_projects creates reports directory if missing."""
        checker = FlextInfraWorkspaceChecker(
            repository_root=tmp_path, rope=rope_workspace
        )
        project_dir = test_u.Tests.mk_project(tmp_path, "p1", with_src=True)
        (project_dir / "src" / "test.py").write_text("value = 1\n", encoding="utf-8")
        reports_dir = tmp_path / "reports"
        result = checker.run_projects(["p1"], ["lint"], reports_dir=reports_dir)
        tm.ok(result)
        tm.that(reports_dir.exists(), eq=True)

    def test_lint_returns_gate_result(
        self, tmp_path: Path, rope_workspace: p.Infra.RopeWorkspaceDsl
    ) -> None:
        """Test that lint() returns a GateResult."""
        checker = FlextInfraWorkspaceChecker(
            repository_root=tmp_path, rope=rope_workspace
        )
        result = checker.lint(tmp_path)
        tm.that(result, is_=r)
        tm.ok(result)

    def test_format_returns_gate_result(
        self, tmp_path: Path, rope_workspace: p.Infra.RopeWorkspaceDsl
    ) -> None:
        """Test that format() returns a GateResult."""
        checker = FlextInfraWorkspaceChecker(
            repository_root=tmp_path, rope=rope_workspace
        )
        result = checker.format(tmp_path)
        tm.that(result, is_=r)
        tm.ok(result)
