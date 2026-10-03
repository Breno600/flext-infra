"""Test scanning module.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from tests import m

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraUtilitiesscanning:
    @staticmethod
    def test_scan_violation_model_fields() -> None:
        violation = m.Infra.ScanViolation(
            line=42,
            message="forbidden import",
            severity="high",
            rule_id="FLEXT001",
        )

        tm.that(violation.line, eq=42)
        tm.that(violation.message, eq="forbidden import")
        tm.that(violation.severity, eq="high")
        tm.that(violation.rule_id, eq="FLEXT001")

    @staticmethod
    def test_scan_result_model_fields_and_defaults(tmp_path: Path) -> None:
        result = m.Infra.ScanResult(
            file_path=tmp_path / "sample.py",
            detector_name="scanner-x",
            violations=[],
        )
        payload = result.model_dump()

        tm.that(result.file_path, eq=tmp_path / "sample.py")
        tm.that(result.detector_name, eq="scanner-x")
        tm.that(payload["violations"], eq=[])

    @staticmethod
    def test_scan_result_with_violations(tmp_path: Path) -> None:
        violation = m.Infra.ScanViolation(
            line=7,
            message="rule hit",
            severity="medium",
            rule_id=None,
        )
        result = m.Infra.ScanResult(
            file_path=tmp_path / "violating.py",
            detector_name="scanner-y",
            violations=[violation],
        )
        payload = result.model_dump()

        violations = payload["violations"]
        tm.that(len(violations), eq=1)
        tm.that(violations[0]["message"], eq="rule hit")
        tm.that(violations[0]["rule_id"], none=True)
