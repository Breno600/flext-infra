"""Tests for Rule 2: Typings facade validation."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import u, utilities


class TestsFlextInfraRule2TypingsFacade(
    utilities.TestsFlextInfraUtilities.TestsFlextInfraValidateNamespaceBase
):
    """Test suite for namespace validator Rule 2 (typings facade)."""

    def test_rule2_valid_types_passes(self, tmp_path: Path) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture("rule2_valid_types.pysrc"),
            module_name="typings.py",
        )
        self._assert_valid(root)

    def test_rule2_typevar_runtime_module_detected(self, tmp_path: Path) -> None:
        root = self._create_namespace_project(
            tmp_path,
            module_source='from typing import TypeVar\n\nT = TypeVar("T")\n',
            module_name="base.py",
        )

        result = self.validator.validate_project(root)

        tm.ok(result)
        self._assert_violation_contains(
            root, "module alias/data declaration is forbidden"
        )
