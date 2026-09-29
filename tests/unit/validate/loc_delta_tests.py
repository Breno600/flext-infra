"""Tests for the net-LOC-delta validator (AGENTS.md §3.5).

The pure ``evaluate`` rule fails labelled refactor/cleanup commits with a net
positive delta and passes everything else.
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra.validate.loc_delta import FlextInfraLocDeltaValidator


class TestsFlextInfraLocDelta:
    def test_refactor_positive_delta_fails(self) -> None:
        result = FlextInfraLocDeltaValidator.evaluate(
            subject="refactor: collapse helpers", insertions=10, deletions=3
        )
        tm.that(result.failure, eq=True)

    def test_refactor_negative_delta_passes(self) -> None:
        result = FlextInfraLocDeltaValidator.evaluate(
            subject="refactor: collapse helpers", insertions=3, deletions=20
        )
        tm.that(result.success, eq=True)

    def test_refactor_zero_delta_passes(self) -> None:
        result = FlextInfraLocDeltaValidator.evaluate(
            subject="cleanup: drop dead code", insertions=5, deletions=5
        )
        tm.that(result.success, eq=True)

    def test_non_labelled_subject_is_exempt(self) -> None:
        result = FlextInfraLocDeltaValidator.evaluate(
            subject="feat: add new gate", insertions=120, deletions=0
        )
        tm.that(result.success, eq=True)
