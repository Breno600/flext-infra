"""Tests for fixture-based namespace rule violations."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import u, utilities


class TestsFlextInfraFixtureViolations(
    utilities.TestsFlextInfraUtilities.TestsFlextInfraValidateNamespaceBase
):
    """Each namespace-rule fixture fails the project with its own message."""

    @pytest.mark.parametrize(
        ("fixture_name", "module_name", "expected_violation_substr"),
        [
            pytest.param(
                "rule0_no_class.py",
                "models.py",
                "module must declare at least one top-level class; found 0",
                id="rule0-no-class",
            ),
            pytest.param(
                "rule0_wrong_prefix.py",
                "constants.py",
                "module must declare at least one class starting with 'FlextTest'",
                id="rule0-wrong-prefix",
            ),
            pytest.param(
                "rule0_loose_items.py",
                "models.py",
                "top-level function is forbidden; nest behavior in the module class",
                id="rule0-loose-items",
            ),
            pytest.param(
                "rule1_loose_constant.py",
                "models.py",
                "module alias/data declaration is forbidden; use the canonical "
                "facade class",
                id="rule1-loose-constant",
            ),
            pytest.param(
                "rule1_method_in_constants.py",
                "constants.py",
                "facade must inherit canonical 'c'",
                id="rule1-method-in-constants",
            ),
            pytest.param(
                "rule1_magic_number.py",
                "models.py",
                "module alias/data declaration is forbidden; use the canonical "
                "facade class",
                id="rule1-magic-number",
            ),
            pytest.param(
                "rule2_typevar_in_class.py",
                "typings.py",
                "facade must inherit canonical 't'",
                id="rule2-typevar-in-class",
            ),
            pytest.param(
                "rule2_typevar_wrong_module.py",
                "models.py",
                "module alias/data declaration is forbidden; use the canonical "
                "facade class",
                id="rule2-typevar-wrong-module",
            ),
            pytest.param(
                "rule2_composite_type_loose.py",
                "models.py",
                "module alias/data declaration is forbidden; use the canonical "
                "facade class",
                id="rule2-composite-type-loose",
            ),
            pytest.param(
                "rule2_protocol_in_types.py",
                "typings.py",
                "facade must declare one nested Test MRO",
                id="rule2-protocol-in-types",
            ),
        ],
    )
    def test_fixture_module_reports_its_violation(
        self,
        tmp_path: Path,
        fixture_name: str,
        module_name: str,
        expected_violation_substr: str,
    ) -> None:
        """Each namespace-rule fixture fails the project with its own message."""
        root = self._create_namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture(fixture_name),
            module_name=module_name,
        )
        result = self.validator.validate_project(root)
        tm.that(result.success, eq=True)
        tm.that(not result.value.passed, eq=True)
        self._assert_violation_contains(root, expected_violation_substr)
