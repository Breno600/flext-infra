"""Tests for FlextInfraTextPatternScanner.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.validate.scanner import FlextInfraTextPatternScanner
from tests import c

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraScanner:
    """Core, multi-file, and nested-directory scanning tests."""

    def _scanner(self) -> FlextInfraTextPatternScanner:
        """Return a scanner instance with a harmless default pattern for helper tests."""
        return FlextInfraTextPatternScanner(pattern="")

    def test_scan_matching_pattern(self, tmp_path: Path) -> None:
        """Matching pattern returns violation count."""
        scanner = self._scanner()
        (tmp_path / "test.txt").write_text("hello world")
        result = scanner.scan(tmp_path, pattern="hello", includes=["*.txt"])
        tm.ok(result)
        tm.that(result.value["violation_count"], eq=1)

    def test_scan_no_matches(self, tmp_path: Path) -> None:
        """No matches returns zero violations."""
        scanner = self._scanner()
        (tmp_path / "test.txt").write_text("goodbye world")
        result = scanner.scan(tmp_path, pattern="hello", includes=["*.txt"])
        tm.ok(result)
        tm.that(result.value["violation_count"], eq=0)

    def test_scan_with_excludes(self, tmp_path: Path) -> None:
        """Exclude patterns filter files."""
        scanner = self._scanner()
        (tmp_path / "included.txt").write_text("hello")
        (tmp_path / "excluded.log").write_text("hello")
        result = scanner.scan(
            tmp_path, pattern="hello", includes=["*.txt"], excludes=["*.log"]
        )
        tm.ok(result)
        tm.that(result.value["files_scanned"], eq=1)

    def test_scan_absent_mode(self, tmp_path: Path) -> None:
        """Absent mode counts files missing the pattern."""
        scanner = self._scanner()
        (tmp_path / "missing.txt").write_text("goodbye")
        (tmp_path / "found.txt").write_text("hello world")
        missing = scanner.scan(
            tmp_path,
            pattern="hello",
            includes=["missing.txt"],
            match_mode=c.Infra.MatchMode.ABSENT,
        )
        tm.ok(missing)
        tm.that(missing.value["violation_count"], eq=1)
        found = scanner.scan(
            tmp_path,
            pattern="hello",
            includes=["found.txt"],
            match_mode=c.Infra.MatchMode.ABSENT,
        )
        tm.ok(found)
        tm.that(found.value["violation_count"], eq=0)

    def test_scan_nonexistent_root(self, tmp_path: Path) -> None:
        """Nonexistent root returns failure."""
        scanner = self._scanner()
        tm.fail(scanner.scan(tmp_path / "nope", pattern="x", includes=["*.txt"]))

    def test_scan_invalid_inputs(self, tmp_path: Path) -> None:
        """Empty includes fail and invalid enum payload is rejected at validation."""
        tm.fail(self._scanner().scan(tmp_path, pattern="x", includes=[]))
        with pytest.raises(c.ValidationError):
            _ = FlextInfraTextPatternScanner.model_validate({
                "pattern": "x",
                "match": "invalid",
            })

    def test_scan_invalid_regex(self, tmp_path: Path) -> None:
        """Invalid regex pattern returns failure."""
        (tmp_path / "test.txt").write_text("content")
        tm.fail(self._scanner().scan(tmp_path, pattern="[invalid", includes=["*.txt"]))

    def test_scan_multiple_files(self, tmp_path: Path) -> None:
        """Matches across multiple files are counted."""
        scanner = self._scanner()
        (tmp_path / "file1.txt").write_text("hello world")
        (tmp_path / "file2.txt").write_text("hello again")
        (tmp_path / "file3.txt").write_text("goodbye")
        result = scanner.scan(tmp_path, pattern="hello", includes=["*.txt"])
        tm.ok(result)
        tm.that(result.value["match_count"], eq=2)

    def test_scan_multiline_pattern(self, tmp_path: Path) -> None:
        """Multiline regex pattern matches all lines."""
        scanner = self._scanner()
        (tmp_path / "test.txt").write_text("line1\nline2\nline3")
        result = scanner.scan(tmp_path, pattern="^line", includes=["*.txt"])
        tm.ok(result)
        tm.that(result.value["match_count"], eq=3)

    def test_scan_nested_directories(self, tmp_path: Path) -> None:
        """Files in nested directories are found."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("hello")
        result = self._scanner().scan(tmp_path, pattern="hello", includes=["**/*.txt"])
        tm.ok(result)
        tm.that(result.value["files_scanned"], eq=1)

    def test_scan_unreadable_file_surfaces_failure(self, tmp_path: Path) -> None:
        """An unreadable file surfaces as a scan failure — never silently skipped."""
        f = tmp_path / "test.txt"
        f.write_text("hello")
        f.chmod(0o000)
        try:
            result = self._scanner().scan(tmp_path, pattern="hello", includes=["*.txt"])
            tm.that(result.failure, eq=True)
        finally:
            f.chmod(0o644)
