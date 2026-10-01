"""Tests for flext_infra.check.workspace_check module.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT

Tests the real entry-point behavior.
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import main


class TestsFlextInfraWorkspaceCheckModule:
    """Tests for ``FlextInfraWorkspaceCheckModule``."""

    @staticmethod
    def test_workspace_check_main_returns_error_without_projects() -> None:
        """Test workspace check main returns error without projects."""
        exit_code = main(["check", "run"])
        tm.that(exit_code, eq=1)
