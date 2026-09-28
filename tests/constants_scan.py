"""Text-scan fixture pattern constants for FLEXT infra tests."""

from __future__ import annotations

import re as _re
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from flext_infra import t


class TestsFlextInfraConstantsScanMixin:
    """Log, scanner, and lazy-init export scan fixture patterns."""

    LOG_NOISE_LINES: ClassVar[t.StrSequence] = (
        "make[1]: Nothing to be done",
        "INFO: running tests",
        "warning: ignoring duplicate",
        "Success: 5 passed",
        "make[2]: Entering directory",
    )
    LOG_ERROR_LINES: ClassVar[t.StrSequence] = (
        "ERROR: something went wrong",
        "FAIL: test_foo failed",
        "error: compilation failed",
        "E  AssertionError: mismatch",
        "FAILED tests/test_foo.py::test_bar",
    )
    LOG_PATTERN_CASES: ClassVar[t.VariadicTuple[t.Pair[str, int]]] = (
        ("error: compilation failed", 1),
        ("E  AssertionError: mismatch", 1),
        ("FAILED tests/test_foo.py::test_bar", 1),
        ("make[2]: Entering directory", 0),
        ("warning: ignoring duplicate", 0),
        ("Success: 5 passed", 0),
    )
    LOG_ERROR_PREFIX_RE: ClassVar[t.RegexPattern] = _re.compile(
        r"^(ERROR|FAIL|error|E\s+AssertionError|FAILED)"
    )
    LOG_MIXED_SCENARIO_LINES: ClassVar[t.StrSequence] = (
        "make[1]: running",
        "ERROR: build failed",
        "INFO: post-build",
        "FAIL: test broken",
        "Total: 2 failed",
    )
    SCANNER_HELLO_RE: ClassVar[t.RegexPattern] = _re.compile(r"hello", _re.MULTILINE)
    LAZY_INIT_EXPORT_NAME_RE: ClassVar[t.RegexPattern] = _re.compile(
        r'["\']([^"\']+)["\']'
    )


__all__: list[str] = ["TestsFlextInfraConstantsScanMixin"]
