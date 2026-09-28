"""Tests for census models and violation pattern.

Validates CensusViolation/CensusReport models and the compiled violation
regex pattern. Projects without pyproject.toml are filtered at the discovery
boundary, not via a hand-curated list.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from tests import c, m


class TestsFlextInfraCodegenCensusModels:
    """Violation pattern and census report model contracts."""

    def test_named_groups_present(self) -> None:
        match = c.Infra.VIOLATION_PATTERN.match("[NS-001-001] src/file.py:10 — msg")
        tm.that(match is not None, eq=True)
        if match is not None:
            tm.that(set(match.groupdict()), eq={"rule", "module", "line", "message"})

    def test_model_fields(self) -> None:
        v = m.Infra.CensusViolation(
            module="src/file.py",
            rule="NS-001",
            line=10,
            message="Test message",
            fixable=True,
        )
        tm.that(v.module, eq="src/file.py")
        tm.that(v.rule, eq="NS-001")
        tm.that(v.line, eq=10)
        tm.that(v.message, eq="Test message")
        tm.that(v.fixable, eq=True)

    def test_empty_report(self) -> None:
        report = m.Infra.CensusReport(
            project="test-project", violations=[], total=0, fixable=0
        )
        tm.that(report.project, eq="test-project")
        tm.that(report.total, eq=0)
        tm.that(report.fixable, eq=0)
        tm.that(report.violations, empty=True)

    def test_report_with_mixed_violations(self) -> None:
        violations = [
            m.Infra.CensusViolation(
                module="src/a.py", rule="NS-000", line=1, message="m1", fixable=False
            ),
            m.Infra.CensusViolation(
                module="src/b.py", rule="NS-001", line=2, message="m2", fixable=True
            ),
            m.Infra.CensusViolation(
                module="src/c.py", rule="NS-002", line=3, message="m3", fixable=True
            ),
        ]
        report = m.Infra.CensusReport(
            project="test-project",
            violations=violations,
            total=len(violations),
            fixable=sum(1 for v in violations if v.fixable),
        )
        tm.that(report.total, eq=3)
        tm.that(report.fixable, eq=2)
