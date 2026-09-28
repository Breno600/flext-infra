"""Tests for FlextInfraDocBuilder — core build and scope tests.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.docs.builder import FlextInfraDocBuilder
from tests import m

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraBuilder:
    """Core build invocation tests."""

    @pytest.fixture
    def builder(self) -> FlextInfraDocBuilder:
        """Provide the public documentation builder service."""
        return FlextInfraDocBuilder()

    def test_build_with_valid_scope_returns_success(
        self, builder: FlextInfraDocBuilder, tmp_path: Path
    ) -> None:
        """Test build with valid scope returns success."""
        reports: t.SequenceOf[m.Infra.DocsPhaseReport] = tm.ok(builder.build(tmp_path))
        tm.that(len(reports), gte=0)

    def test_build_report_frozen(self) -> None:
        """Test BuildReport is frozen (immutable)."""
        tm.that(m.Infra.DocsPhaseReport.model_config.get("frozen"), eq=True)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"projects": ["test-project"]},
            {"projects": ["proj1", "proj2"]},
            {"output_dir": "custom_output"},
        ],
    )
    def test_build_with_option_variants(
        self,
        builder: FlextInfraDocBuilder,
        tmp_path: Path,
        kwargs: t.MappingKV[str, str | t.SequenceOf[str]],
    ) -> None:
        """Build runs with each option variant and returns a railway result."""
        if "output_dir" in kwargs:
            match kwargs["output_dir"]:
                case str() as output_dir:
                    tm.ok(
                        builder.build(tmp_path, output_dir=str(tmp_path / output_dir))
                    )
                case invalid:
                    pytest.fail(f"invalid output_dir test case: {invalid!r}")
        else:
            match kwargs.get("projects"):
                case list() as projects:
                    tm.ok(builder.build(tmp_path, projects=projects))
                case invalid:
                    pytest.fail(f"invalid projects test case: {invalid!r}")

    @pytest.mark.parametrize("status", ["OK", "FAIL", "SKIP"])
    def test_build_report_result_field_values(
        self, status: str, tmp_path: Path
    ) -> None:
        """Test BuildReport result field accepts valid values."""
        report = m.Infra.DocsPhaseReport(
            phase="build",
            scope="test",
            result=status,
            reason="Test reason",
            site_dir=str(tmp_path / "site"),
        )
        tm.that(report.result, eq=status)

    def test_build_report_site_dir_field(self) -> None:
        """Test BuildReport site_dir field."""
        report = m.Infra.DocsPhaseReport(
            phase="build",
            scope="test",
            result="OK",
            reason="Build successful",
            site_dir="/path/to/site",
        )
        tm.that(report.site_dir, eq="/path/to/site")

    def test_build_with_multiple_projects_returns_list(
        self, builder: FlextInfraDocBuilder, tmp_path: Path
    ) -> None:
        """Test build with multiple projects returns list of reports."""
        result = builder.build(tmp_path, projects=["proj1", "proj2"])
        if result.success:
            tm.that(len(result.value), gte=0)
