"""Tests for FlextInfraConfigFixer service.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.deps.fix_pyrefly_config import FlextInfraConfigFixer
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraConfigFixer:
    """Test suite for FlextInfraConfigFixer."""

    @staticmethod
    def test_init_creates_instance() -> None:
        """Test that fixer initializes with default repository root."""
        fixer = FlextInfraConfigFixer()
        tm.that(fixer, none=False)

    @staticmethod
    def test_init_with_custom_repository_root(tmp_path: Path) -> None:
        """Test that fixer accepts custom repository root."""
        fixer = FlextInfraConfigFixer(repository_root=tmp_path)
        tm.that(fixer, none=False)

    @staticmethod
    def test_execute_returns_failure() -> None:
        """Test that execute() returns failure with helpful message."""
        fixer = FlextInfraConfigFixer()
        result = fixer.execute()
        tm.fail(result)
        tm.that(result.error, is_=str)
        tm.that(result.error, is_=str)
        tm.that(result.error, has="Use execute_command() directly")

    @staticmethod
    def test_run_with_empty_projects(tmp_path: Path) -> None:
        """Test that run() handles empty project list."""
        fixer = FlextInfraConfigFixer(repository_root=tmp_path)
        result = fixer.run([])
        tm.ok(result)
        tm.that(result.value, is_=list)

    @staticmethod
    def test_run_with_nonexistent_projects(tmp_path: Path) -> None:
        """Test that run() fails closed for an inaccessible explicit project."""
        u.Tests.reject_inaccessible_config_project(tmp_path)

    @staticmethod
    def test_run_with_dry_run_flag(tmp_path: Path) -> None:
        """Test that run() respects dry_run flag."""
        fixer = FlextInfraConfigFixer(repository_root=tmp_path)
        result = fixer.run([], dry_run=True)
        tm.ok(result)

    @staticmethod
    def test_run_with_verbose_flag(tmp_path: Path) -> None:
        """Test that run() respects verbose flag."""
        fixer = FlextInfraConfigFixer(repository_root=tmp_path)
        result = fixer.run([], verbose=True)
        tm.ok(result)

    @staticmethod
    def test_process_file_with_missing_file(tmp_path: Path) -> None:
        """Test that process_file handles missing files gracefully."""
        fixer = FlextInfraConfigFixer(repository_root=tmp_path)
        missing_file = tmp_path / "nonexistent.toml"
        result = fixer.process_file(missing_file)
        tm.fail(result)
        tm.that(result.error, is_=str)
        tm.that(result.error, has="not found")

    @staticmethod
    def test_process_file_with_valid_toml(tmp_path: Path) -> None:
        """Test that process_file handles valid TOML without pyrefly section."""
        fixer = FlextInfraConfigFixer(repository_root=tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool]\nother = true\n")
        result = fixer.process_file(pyproject)
        tm.ok(result)
        tm.that(result.value, eq=[])

    @staticmethod
    def test_process_file_with_invalid_toml(tmp_path: Path) -> None:
        """Test that process_file handles invalid TOML gracefully."""
        fixer = FlextInfraConfigFixer(repository_root=tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[invalid toml")
        result = fixer.process_file(pyproject)
        tm.fail(result)
        tm.that(result.error, is_=str)
        tm.that(result.error, has="TOML parse failed")

    @staticmethod
    def test_process_file_with_dry_run(tmp_path: Path) -> None:
        """Test that process_file with dry_run doesn't modify file."""
        fixer = FlextInfraConfigFixer(repository_root=tmp_path)
        pyproject = tmp_path / "pyproject.toml"
        original_content = "[tool]\nother = true\n"
        pyproject.write_text(original_content)
        result = fixer.process_file(pyproject, dry_run=True)
        tm.ok(result)
        tm.that(pyproject.read_text(), eq=original_content)
