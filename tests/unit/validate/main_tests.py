"""Tests for the centralized validate CLI group.

Tests CLI subcommand routing via subprocess for real integration testing.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import main as infra_main
from flext_infra.validate.inventory import FlextInfraInventoryService
from flext_infra.validate.scanner import FlextInfraTextPatternScanner
from tests import c

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraValidateMain:
    """Test inventory, scan, and CLI routing subcommands with real services."""

    def _cli(self, *args: str) -> int:
        """Run validate routing through the canonical infra CLI."""
        return infra_main(["validate", *args])

    def test_success(self, tmp_path: Path) -> None:
        """Inventory succeeds with empty workspace."""
        result = FlextInfraInventoryService(repository_root=tmp_path).execute()
        tm.that(result.success, eq=True)

    def test_with_output_dir(self, tmp_path: Path) -> None:
        """Inventory succeeds with output directory."""
        output = tmp_path / "output"
        output.mkdir()
        result = FlextInfraInventoryService(repository_root=tmp_path, output_dir=output)
        result = result.execute()
        tm.that(result.success, eq=True)

    def test_no_violations(self, tmp_path: Path) -> None:
        """Scan returns success when no violations found."""
        (tmp_path / "test.txt").write_text("hello world")
        result = FlextInfraTextPatternScanner(
            repository_root=tmp_path,
            pattern="NONEXISTENT_PATTERN",
            include=["*.txt"],
            exclude=[],
            match=c.Infra.MatchMode.PRESENT,
        )
        result = result.execute()
        tm.that(result.success, eq=True)

    def test_with_violations(self, tmp_path: Path) -> None:
        """Scan returns failure when violations found."""
        (tmp_path / "test.txt").write_text("TODO fix this")
        result = FlextInfraTextPatternScanner(
            repository_root=tmp_path,
            pattern="TODO",
            include=["*.txt"],
            exclude=[],
            match=c.Infra.MatchMode.PRESENT,
        )
        result = result.execute()
        tm.that(result.failure, eq=True)

    def test_help_flag(self) -> None:
        """--help returns 0."""
        tm.that(self._cli("--help"), eq=0)

    def test_inventory_routing(self, tmp_path: Path) -> None:
        """Inventory subcommand routes correctly."""
        result = self._cli("inventory", "--repository-root", str(tmp_path))
        tm.that({0, 1}, has=result)

    def test_scan_routing(self, tmp_path: Path) -> None:
        """Scan subcommand routes correctly."""
        (tmp_path / "test.txt").write_text("content")
        result = self._cli(
            "scan",
            "--repository-root",
            str(tmp_path),
            "--pattern",
            "content",
            "--include",
            "*.txt",
        )
        tm.that({0, 1}, has=result)

    def test_no_command_returns_1(self) -> None:
        """No subcommand returns exit code 1."""
        tm.that(self._cli(), eq=1)

    def test_unknown_command_returns_error(self) -> None:
        """Unknown subcommand returns non-zero exit code."""
        tm.that(self._cli("unknown"), ne=0)

    def test_skill_validate_routing(self, tmp_path: Path) -> None:
        """skill-validate subcommand routes correctly."""
        result = self._cli(
            "skill-validate",
            "--skill",
            "test-skill",
            "--repository-root",
            str(tmp_path),
        )
        tm.that({0, 1}, has=result)

    def test_stub_validate_routing(self, tmp_path: Path) -> None:
        """stub-validate subcommand routes correctly."""
        result = self._cli("stub-validate", "--repository-root", str(tmp_path))
        tm.that({0, 1}, has=result)
