"""Tests for Rule 3: Import rules (runtime vs TYPE_CHECKING)."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import u


class TestsFlextInfraRule3ImportRules:
    """Test suite for namespace validator Rule 3 (import rules)."""

    @pytest.mark.parametrize(
        ("module_source", "module_name", "expected_violation_substr"),
        [
            (
                (
                    "from __future__ import annotations\n"
                    "from flext_test import u\n\n"
                    "class FlextTestModels(Models):\n"
                    "    pass\n"
                ),
                "models.py",
                "reverse runtime import; later layers are TYPE_CHECKING-only: u",
            ),
            (
                (
                    "from __future__ import annotations\n"
                    "from flext_test._models.base import FlextTestModelsDeps\n\n"
                    "class FlextTestDetector:\n"
                    "    pass\n"
                ),
                "detector.py",
                "import through the public facade, not 'flext_test._models.base'",
            ),
        ],
    )
    def test_rule3_direct_runtime_import_detected(
        self,
        tmp_path: Path,
        module_source: str,
        module_name: str,
        expected_violation_substr: str,
    ) -> None:
        root = u.Tests.namespace_project(
            tmp_path, module_source=module_source, module_name=module_name
        )
        u.Tests.assert_namespace_invalid(
            root, expected_violation_substr=expected_violation_substr
        )

    def test_rule3_utilities_facade_import_remains_allowed(
        self, tmp_path: Path
    ) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture(
                "rule3_utilities_facade_import.pysrc"
            ),
            module_name="utilities.py",
        )
        u.Tests.assert_namespace_valid(root)

    def test_rule3_models_facade_import_remains_allowed(self, tmp_path: Path) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture("rule0_valid.pysrc"),
            module_name="models.py",
        )
        u.Tests.assert_namespace_valid(root)

    def test_rule3_settings_owner_declaration_facade_runtime_imports_allowed(
        self, tmp_path: Path
    ) -> None:
        """D1 carve-out: settings/config owners may runtime-import m/t/u.

        Nested Pydantic namespace-models in ``_settings.py`` require
        ``BaseModel``/``Field``/``MappingKV``/``model_validator``/``JsonValue``
        from the declaration facades at runtime; the fleet's canonical pattern
        (flext-auth/_settings.py, flext-api/_settings.py) depends on this.
        """
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture(
                "rule3_settings_owner_facade_imports.pysrc"
            ),
            module_name="_settings.py",
        )
        u.Tests.assert_namespace_valid(root)

    def test_rule3_settings_owner_c_import_allowed(self, tmp_path: Path) -> None:
        """Operator ruling 2026-09-19: settings defaults read declared constants.

        Settings owners bind Pydantic field defaults to ``c.<Ns>.CONSTANT``, so
        the runtime ``c`` import is part of the declaration-layer carve-out;
        operational facades stay flagged.
        """
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture(
                "rule3_settings_owner_c_import.pysrc"
            ),
            module_name="_settings.py",
        )

        result = u.Tests.namespace_validator().validate_project(root)

        tm.ok(result)
        u.Tests.assert_namespace_no_violation_contains(root, "reverse runtime import")
