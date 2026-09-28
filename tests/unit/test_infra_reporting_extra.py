"""Tests for FlextInfraReportingService — path types.

Tests cover return type validation for report path methods.
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import u


class TestsFlextInfraInfraReportingExtra:
    """Test suite for FlextInfraReportingService extra operations."""

    def test_resolve_report_dir_returns_path(self, tmp_path: Path) -> None:
        """Test that resolve_report_dir returns Path type."""
        result = u.Cli.resolve_report_dir(tmp_path, "project", "check")
        tm.that(result, is_=Path)
        tm.that(result.is_absolute(), eq=True)

    def test_resolve_report_path_returns_path(self, tmp_path: Path) -> None:
        """Test that resolve_report_path returns Path type."""
        result = u.Cli.resolve_report_path(tmp_path, "project", "check", "report.json")
        tm.that(result, is_=Path)
        tm.that(result.is_absolute(), eq=True)
