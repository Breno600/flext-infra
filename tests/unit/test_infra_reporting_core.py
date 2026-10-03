"""Tests for FlextInfraReportingService — report dir/path operations.

Tests cover report path generation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import u


class TestsFlextInfraInfraReportingCore:
    """Test suite for FlextInfraReportingService core operations."""

    @staticmethod
    def test_resolve_report_dir_project_scope(tmp_path: Path) -> None:
        """Test getting project-level report directory."""
        result = u.Cli.resolve_report_dir(tmp_path, "project", "check")
        tm.that(result, is_=Path)
        tm.that(result.name, eq="check")
        tm.that(str(result), has=".reports")
        tm.that(str(result), lacks="workspace")

    @staticmethod
    def test_resolve_report_dir_workspace_scope(tmp_path: Path) -> None:
        """Test getting workspace-level report directory."""
        result = u.Cli.resolve_report_dir(tmp_path, "workspace", "validate")
        tm.that(result, is_=Path)
        tm.that(result.name, eq="validate")
        tm.that(str(result), has=".reports")
        tm.that(str(result), has="workspace")

    @staticmethod
    def test_resolve_report_dir_with_string_root(tmp_path: Path) -> None:
        """Test getting report directory with string root path."""
        result = u.Cli.resolve_report_dir(str(tmp_path), "project", "test")
        tm.that(result, is_=Path)
        tm.that(result.name, eq="test")

    @staticmethod
    def test_resolve_report_path_project_scope(tmp_path: Path) -> None:
        """Test getting project-level report file path."""
        result = u.Cli.resolve_report_path(tmp_path, "project", "check", "report.json")
        tm.that(result, is_=Path)
        tm.that(result.name, eq="report.json")
        tm.that(str(result), has=".reports")
        tm.that(str(result), has="check")

    @staticmethod
    def test_resolve_report_path_workspace_scope(tmp_path: Path) -> None:
        """Test getting workspace-level report file path."""
        result = u.Cli.resolve_report_path(
            tmp_path,
            "workspace",
            "validate",
            "summary.log",
        )
        tm.that(result, is_=Path)
        tm.that(result.name, eq="summary.log")
        tm.that(str(result), has=".reports")
        tm.that(str(result), has="workspace")
        tm.that(str(result), has="validate")

    @staticmethod
    def test_resolve_report_path_with_string_root(tmp_path: Path) -> None:
        """Test getting report file path with string root."""
        result = u.Cli.resolve_report_path(
            str(tmp_path),
            "project",
            "test",
            "results.xml",
        )
        tm.that(result, is_=Path)
        tm.that(result.name, eq="results.xml")
