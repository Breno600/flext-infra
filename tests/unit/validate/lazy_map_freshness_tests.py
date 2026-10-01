"""Tests for FlextInfraValidateLazyMapFreshness.

Guard 2/3: stale-lazy-map detector. Thin wrapper over the existing
ROPE-backed lazy-init generator in check-only mode; the
generator's own unit tests cover the detailed stale-detection
semantics.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.validate.lazy_map_freshness import FlextInfraValidateLazyMapFreshness
from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraLazyMapFreshness:
    """Wrapper semantics: runs the check-only generator and formats the report."""

    @pytest.fixture
    def v(self) -> FlextInfraValidateLazyMapFreshness:
        """Shared validator instance."""
        return FlextInfraValidateLazyMapFreshness()

    def test_empty_workspace_yields_passing_report(
        self, tmp_path: Path, v: FlextInfraValidateLazyMapFreshness
    ) -> None:
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report, is_=m.Infra.ValidationReport)
        tm.that(report.passed, eq=True)
        tm.that(report.violations, length=0)

    def test_passing_summary_mentions_lazy_maps(
        self, tmp_path: Path, v: FlextInfraValidateLazyMapFreshness
    ) -> None:
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.summary, has="lazy")

    def test_report_is_validation_report(
        self, tmp_path: Path, v: FlextInfraValidateLazyMapFreshness
    ) -> None:
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report, is_=m.Infra.ValidationReport)

    # Why (suite budget): full-suite xdist can stall durable atomic writes
    # beyond the default case timeout while the lazy-init harness publishes files.
    @pytest.mark.slow
    def test_stale_generated_lazy_map_fails_report(
        self, tmp_path: Path, v: FlextInfraValidateLazyMapFreshness
    ) -> None:
        """Freshness validation fails when generated lazy maps drift."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        init_path = package_root / "__init__.py"
        init_path.write_text(
            f"{init_path.read_text(encoding='utf-8')}\n# stale generated drift\n",
            encoding="utf-8",
        )

        report: m.Infra.ValidationReport = tm.ok(v.build_report(repository_root))

        tm.that(report.passed, eq=False)
        tm.that(report.summary, has="stale")
        tm.that(len(tuple(report.violations)), gte=1)
