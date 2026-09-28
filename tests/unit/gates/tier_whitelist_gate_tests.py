"""Tests for FlextInfraTierWhitelistGate.

The gate must surface every abstraction-boundary violation the detector found.
Collapsing them into one aggregate issue pinned to the repository root makes
the gate unactionable and aggregates independent defects, which ``fail loud``
forbids.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tf, tm

from flext_infra.gates.tier_whitelist import FlextInfraTierWhitelistGate
from tests import m, u

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests import t


class TestsFlextInfraTierWhitelistGateReporting:
    """Each violation reaches the report as its own issue."""

    @pytest.fixture
    def gate_result(self, tmp_path: Path) -> Callable[..., m.Infra.GateResult]:
        """Seed a package with the given modules and run the gate over it.

        One owner for the whole arrange-act pair: every test differs only in which
        modules it seeds, so repeating the package/context construction per test
        would be a structural clone.
        """

        def run(*modules: t.Pair[str, str]) -> m.Infra.GateResult:
            package = u.Tests.write_package_init(tmp_path / "src" / "pkg", "").parent
            files = tf(base_dir=package)
            for source, filename in modules:
                files.create(source, filename)
            context = m.Infra.GateContext(
                repository_root=tmp_path, reports_dir=tmp_path / ".reports"
            )
            gate = FlextInfraTierWhitelistGate(repository_root=tmp_path)
            return gate.check(tmp_path, context).result

        return run

    def test_clean_project_passes_without_errors(
        self, gate_result: Callable[..., m.Infra.GateResult]
    ) -> None:
        result = gate_result(("from flext_core import m\nX = m.BaseModel\n", "ok.py"))
        tm.that(result.passed, eq=True)
        tm.that(len(result.errors), eq=0)

    def test_every_violation_is_reported_individually(
        self, gate_result: Callable[..., m.Infra.GateResult]
    ) -> None:
        # Three offending modules must yield three errors, never one aggregate
        # count: the operator needs the offending file on every entry.
        result = gate_result(
            ("from pydantic import BaseModel\n", "one.py"),
            ("import structlog\n", "two.py"),
            ("from returns.result import Result\n", "three.py"),
        )
        tm.that(result.passed, eq=False)
        tm.that(len(result.errors), eq=3)
        joined = " | ".join(result.errors)
        for offender in ("one.py", "two.py", "three.py"):
            tm.that(joined, has=offender)

    def test_error_text_is_not_the_summary_count(
        self, gate_result: Callable[..., m.Infra.GateResult]
    ) -> None:
        # Guards the regression this gate carried: execute() returns a bool and
        # the summary "N violation(s)", so the gate emitted a single error that
        # named no file at all.
        result = gate_result(
            ("from pydantic import BaseModel\n", "a.py"), ("import structlog\n", "b.py")
        )
        tm.that(len(result.errors), eq=2)
        tm.that(" | ".join(result.errors), lacks="violation(s)")
