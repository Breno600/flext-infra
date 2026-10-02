"""Public behavior tests for FlextInfraWorkspaceChecker.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.check import FlextInfraWorkspaceChecker
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraWorkspaceInit:
    """Declarative public-contract tests for workspace checker setup."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("--fix --unsafe-fixes", ["--fix", "--unsafe-fixes"]), (None, []), ("", [])],
    )
    @staticmethod
    def test_parse_tool_args(raw: str | None, expected: t.StrSequence) -> None:
        """Test parse tool args."""
        tm.that(FlextInfraWorkspaceChecker.parse_tool_args(raw), eq=list(expected))

    @staticmethod
    def test_execute_returns_failure(tmp_path: Path) -> None:
        """Test execute returns failure."""
        result = FlextInfraWorkspaceChecker(repository_root=tmp_path).execute()
        tm.fail(result, has="Use execute_command() directly")

    @staticmethod
    def test_resolve_gates_rejects_duplicate_explicit_gates() -> None:
        """Test resolve gates rejects duplicate explicit gates."""
        result = FlextInfraWorkspaceChecker.resolve_gates([
            c.Infra.PYREFLY,
            c.Infra.PYREFLY,
        ])
        tm.fail(result, has=f"duplicate gate '{c.Infra.PYREFLY}'")

    @staticmethod
    def test_resolve_gates_rejects_unknown_gate() -> None:
        """Test resolve gates rejects unknown gate."""
        result = FlextInfraWorkspaceChecker.resolve_gates(["unknown"])
        tm.fail(result, has="unknown gate")

    @staticmethod
    def test_resolve_repository_root_or_cwd_returns_absolute_path() -> None:
        """Test resolve repository root or cwd returns absolute path."""
        tm.that(u.Infra.resolve_repository_root_or_cwd(None).is_absolute(), eq=True)

    @staticmethod
    def test_run_projects_fails_when_reports_dir_is_not_a_directory(
        tmp_path: Path,
    ) -> None:
        """Test run projects fails when reports dir is not a directory."""
        reports_file = tmp_path / "reports.txt"
        reports_file.write_text("", encoding="utf-8")

        result = FlextInfraWorkspaceChecker(repository_root=tmp_path).run_projects(
            ["project-a"],
            [c.Infra.LINT],
            reports_dir=reports_file,
        )

        tm.fail(result)
