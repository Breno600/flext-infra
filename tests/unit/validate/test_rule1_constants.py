"""Tests for Rule 1: Constants facade validation."""

from __future__ import annotations

from pathlib import Path

from tests import u


class TestsFlextInfraRule1ConstantsFacade:
    """Test suite for namespace validator Rule 1 (constants facade)."""

    def test_rule1_valid_constants_passes(self, tmp_path: Path) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture("rule1_valid_constants.pysrc"),
            module_name="constants.py",
        )
        u.Tests.assert_namespace_valid(root)
