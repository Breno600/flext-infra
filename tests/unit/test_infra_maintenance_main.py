"""Tests for maintenance CLI entry point using real services.

Tests the main() function with various argument combinations using
real FlextInfraPythonVersionEnforcer against tmp_path workspaces.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, override

from flext_tests import tm

from flext_infra import main as infra_main
from flext_infra.maintenance.python_version import FlextInfraPythonVersionEnforcer
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraInfraMaintenanceMain:
    """Tests for the maintenance main entry point."""

    def _maintenance_main(self, argv: t.SequenceOf[str] | None = None) -> int:
        args = ["maintenance"]
        if argv is not None:
            args.extend(argv)
        return infra_main(args)

    def _create_workspace(self, root: Path, *, python_minor: int = 13) -> Path:
        """Create a valid workspace structure for testing."""
        root.mkdir(exist_ok=True)
        (root / ".git").mkdir(exist_ok=True)
        (root / "Makefile").touch()
        (root / "pyproject.toml").write_text(
            f'requires-python = ">=3.{python_minor}"\n', encoding="utf-8"
        )
        (root / ".python-version").write_text(f"3.{python_minor}\n", encoding="utf-8")
        return root

    def _make_enforcer(self, workspace: Path) -> FlextInfraPythonVersionEnforcer:
        class _TestEnforcer(FlextInfraPythonVersionEnforcer):
            @override
            def _repository_root_from_file(self, file: str | Path) -> Path:
                _ = file
                return workspace

        return _TestEnforcer()

    def test_main_with_help_flag(self) -> None:
        tm.that(self._maintenance_main(["--help"]), eq=0)

    def test_main_calls_sys_exit_on_help(self) -> None:
        tm.that(self._maintenance_main(["--help"]), eq=0)

    def test_enforcer_check_only_success(self, tmp_path: Path) -> None:
        workspace = self._create_workspace(
            tmp_path / "ws", python_minor=sys.version_info.minor
        )
        enforcer = self._make_enforcer(workspace)
        result = enforcer.execute(check_only=True, verbose=False)
        tm.ok(result, eq=0)

    def test_enforcer_enforce_mode(self, tmp_path: Path) -> None:
        workspace = self._create_workspace(
            tmp_path / "ws", python_minor=sys.version_info.minor
        )
        enforcer = self._make_enforcer(workspace)
        result = enforcer.execute(check_only=False, verbose=False)
        tm.ok(result, eq=0)

    def test_enforcer_verbose_mode(self, tmp_path: Path) -> None:
        workspace = self._create_workspace(
            tmp_path / "ws", python_minor=sys.version_info.minor
        )
        enforcer = self._make_enforcer(workspace)
        result = enforcer.execute(check_only=True, verbose=True)
        tm.ok(result, eq=0)
        tm.that(enforcer.verbose, eq=True)

    def test_enforcer_failure_on_version_mismatch(self, tmp_path: Path) -> None:
        mismatched_minor = sys.version_info.minor + 1
        workspace = self._create_workspace(
            tmp_path / "ws", python_minor=mismatched_minor
        )
        enforcer = self._make_enforcer(workspace)
        result = enforcer.execute(check_only=True, verbose=False)
        tm.fail(result)

    def test_enforcer_check_only_flag_stored(self, tmp_path: Path) -> None:
        workspace = self._create_workspace(
            tmp_path / "ws", python_minor=sys.version_info.minor
        )
        enforcer = self._make_enforcer(workspace)
        enforcer.execute(check_only=True, verbose=False)
        tm.that(enforcer.check_only, eq=True)

    def test_enforcer_verbose_flag_stored(self, tmp_path: Path) -> None:
        workspace = self._create_workspace(
            tmp_path / "ws", python_minor=sys.version_info.minor
        )
        enforcer = self._make_enforcer(workspace)
        enforcer.execute(check_only=False, verbose=True)
        tm.that(enforcer.verbose, eq=True)

    def test_enforcer_both_flags(self, tmp_path: Path) -> None:
        workspace = self._create_workspace(
            tmp_path / "ws", python_minor=sys.version_info.minor
        )
        enforcer = self._make_enforcer(workspace)
        result = enforcer.execute(check_only=True, verbose=True)
        tm.ok(result, eq=0)
        tm.that(enforcer.check_only, eq=True)
        tm.that(enforcer.verbose, eq=True)

    def test_enforcer_empty_workspace(self, tmp_path: Path) -> None:
        workspace = self._create_workspace(
            tmp_path / "ws", python_minor=sys.version_info.minor
        )
        enforcer = self._make_enforcer(workspace)
        result = enforcer.execute(check_only=True)
        tm.ok(result, eq=0)

    def test_enforcer_project_mismatch(self, tmp_path: Path) -> None:
        workspace = self._create_workspace(
            tmp_path / "ws", python_minor=sys.version_info.minor
        )
        project = workspace / "project-a"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "Makefile").touch()
        (project / "src").mkdir()
        mismatched = sys.version_info.minor + 1
        (project / "pyproject.toml").write_text(
            (
                "[project]\n"
                "name = 'project-a'\n"
                "dependencies = ['flext-core>=0.1.0']\n"
                f'requires-python = ">=3.{mismatched}"\n'
            ),
            encoding="utf-8",
        )
        u.Tests.declare_workspace_projects(workspace, ("project-a",))
        enforcer = self._make_enforcer(workspace)
        result = enforcer.execute(check_only=True, verbose=False)
        tm.fail(result)

    def test_enforcer_creates_instance(self) -> None:
        enforcer = FlextInfraPythonVersionEnforcer()
        tm.that(type(enforcer).__name__, eq="FlextInfraPythonVersionEnforcer")
