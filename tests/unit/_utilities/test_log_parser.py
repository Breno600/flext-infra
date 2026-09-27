"""Tests for u.Infra.extract_errors log parsing.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraUtilitiesLogParser:
    def test_missing_file_returns_zero_empty(self, tmp_path: Path) -> None:
        result = u.Infra.extract_errors(tmp_path / "nonexistent.log")

        tm.that(result, eq=(0, []))

    def test_empty_file_returns_zero_empty(self, tmp_path: Path) -> None:
        log_file = tmp_path / "empty.log"
        log_file.write_text("", encoding="utf-8")

        count, lines = u.Infra.extract_errors(log_file)

        tm.that(count, eq=0)
        tm.that(list(lines), eq=[])

    def test_file_with_only_whitespace_returns_zero_empty(self, tmp_path: Path) -> None:
        log_file = tmp_path / "whitespace.log"
        log_file.write_text("   \n\n   \n", encoding="utf-8")

        count, lines = u.Infra.extract_errors(log_file)

        tm.that(count, eq=0)
        tm.that(list(lines), eq=[])

    def test_error_line_is_detected(self, tmp_path: Path) -> None:
        log_file = tmp_path / "errors.log"
        log_file.write_text(f"{c.Tests.LOG_ERROR_LINES[0]}\n", encoding="utf-8")

        count, lines = u.Infra.extract_errors(log_file)

        tm.that(count, eq=1)
        tm.that(lines[0], has=c.Tests.LOG_ERROR_LINES[0])

    def test_fail_line_is_detected(self, tmp_path: Path) -> None:
        log_file = tmp_path / "fail.log"
        log_file.write_text(f"{c.Tests.LOG_ERROR_LINES[1]}\n", encoding="utf-8")

        count, lines = u.Infra.extract_errors(log_file)

        tm.that(count, eq=1)
        tm.that(lines[0], has=c.Tests.LOG_ERROR_LINES[1])

    def test_noise_patterns_are_skipped(self, tmp_path: Path) -> None:
        log_file = tmp_path / "noise.log"
        log_file.write_text(
            "\n".join(c.Tests.LOG_NOISE_LINES[:2]) + "\n", encoding="utf-8"
        )

        count, lines = u.Infra.extract_errors(log_file)

        tm.that(count, eq=0)
        tm.that(list(lines), eq=[])

    def test_max_lines_truncates_results(self, tmp_path: Path) -> None:
        error_lines = "\n".join(f"ERROR: error line {i}" for i in range(10))
        log_file = tmp_path / "many_errors.log"
        log_file.write_text(error_lines + "\n", encoding="utf-8")

        count, lines = u.Infra.extract_errors(log_file, max_lines=3)

        tm.that(count, eq=10)
        tm.that(len(list(lines)), eq=3)

    def test_default_max_lines_is_five(self, tmp_path: Path) -> None:
        error_lines = "\n".join(f"ERROR: error line {i}" for i in range(10))
        log_file = tmp_path / "many_errors2.log"
        log_file.write_text(error_lines + "\n", encoding="utf-8")

        count, lines = u.Infra.extract_errors(log_file)

        tm.that(count, eq=10)
        tm.that(len(list(lines)), eq=5)

    def test_python_file_error_lines_detected(self, tmp_path: Path) -> None:
        log_file = tmp_path / "pyerr.log"
        log_file.write_text("  foo/bar.py:42 ImportError\n", encoding="utf-8")

        count, _lines = u.Infra.extract_errors(log_file)

        tm.that(count, eq=1)

    def test_mixed_errors_and_noise(self, tmp_path: Path) -> None:
        content = "\n".join(c.Tests.LOG_MIXED_SCENARIO_LINES) + "\n"
        log_file = tmp_path / "mixed.log"
        log_file.write_text(content, encoding="utf-8")

        count, _lines = u.Infra.extract_errors(log_file)

        tm.that(count, eq=2)

    @pytest.mark.parametrize(("line", "expected_count"), c.Tests.LOG_PATTERN_CASES)
    def test_pattern_matching(
        self, tmp_path: Path, line: str, expected_count: int
    ) -> None:
        log_file = tmp_path / "pattern.log"
        log_file.write_text(line + "\n", encoding="utf-8")

        count, _ = u.Infra.extract_errors(log_file)

        tm.that(count, eq=expected_count)

    @pytest.mark.parametrize("line", c.Tests.LOG_ERROR_LINES)
    def test_error_lines_follow_prefix_rule(self, line: str) -> None:
        tm.that(c.Tests.LOG_ERROR_PREFIX_RE.match(line) is not None, eq=True)
