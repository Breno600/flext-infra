"""Tests for flext_infra.check.workspace_check module.

Tests the real entry-point behavior.
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import main


class TestsFlextInfraWorkspaceCheckModule:
    def test_workspace_check_main_returns_error_without_projects(self) -> None:
        exit_code = main(["check", "run"])
        tm.that(exit_code, eq=1)
