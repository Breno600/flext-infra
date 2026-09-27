"""Tests for module path-based namespace rules (test directory patterns)."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import c, utilities


class TestsFlextInfraModulePathRules(
    utilities.TestsFlextInfraUtilities.TestsFlextInfraValidateNamespaceBase
):
    """Namespace rules key on the module path a project actually declares."""

    @pytest.mark.parametrize("family", ["c", "t", "p", "m", "u"])
    @pytest.mark.parametrize("valid_alias", [True, False])
    def test_test_facade_namespace_and_alias(
        self, tmp_path: Path, family: str, *, valid_alias: bool
    ) -> None:
        """Test facades own Tests and their exact family alias, never loose aliases."""
        module = c.Infra.FAMILY_PUBLIC_MODULES[family]
        suffix = c.Infra.FAMILY_SUFFIXES[family]
        # The negative case binds the alias to the IMPORTED parent class, not
        # the local facade: the owner election accepts any locally-declared
        # published alias, so only a foreign binding stays a violation.
        target_alias = family if valid_alias else "unrelated"
        bound_class = f"TestsFlextTest{suffix}" if valid_alias else f"FlextTest{suffix}"
        # The test facade extends the parent package's family CLASS and
        # rebinds the letter locally; importing the letter itself would
        # shadow the binding and break the owner election.
        root, _ = self._create_namespace_project_path(
            tmp_path,
            module_path=f"tests/{module}.py",
            module_source=(
                f"from flext_test.{module} import FlextTest{suffix}\n\n"
                f"class TestsFlextTest{suffix}(FlextTest{suffix}):\n"
                f"    class Tests(FlextTest{suffix}.Tests):\n        pass\n\n"
                f"{target_alias} = {bound_class}\n\n"
                f'__all__: list[str] = ["TestsFlextTest{suffix}", "{target_alias}"]\n'
            ),
        )
        report = self._validate_project(root)
        tm.that(report.passed, eq=valid_alias, msg=str(report.violations))

    @pytest.mark.parametrize(
        (
            "module_path",
            "module_source",
            "violation_substr",
            "expect_violation",
            "expect_passed",
        ),
        [
            pytest.param(
                "_constants/sample.py",
                "from __future__ import annotations\n"
                "from enum import Enum\n\n"
                "class FlextTestModelsConstants:\n"
                "    class Status(Enum):\n"
                '        OK = "ok"\n',
                "Loose Enum 'Status' belongs in constants.py",
                False,
                None,
                id="rule1-skips-enum-inside-private-constants-dir",
            ),
            pytest.param(
                "_typings/typeadapters.py",
                "from __future__ import annotations\n\ntype LocalAlias = str | int\n",
                "PEP 695 TypeAlias 'LocalAlias' belongs in typings.py",
                False,
                None,
                id="rule2-skips-typealias-inside-private-typings-dir",
            ),
            pytest.param(
                "_utilities/private_runtime.py",
                "from __future__ import annotations\n"
                "from flext_test import FlextTestModelsSomething\n\n"
                "class FlextTestModelsThing(Models):\n"
                "    pass\n",
                "instead of direct import 'FlextTestModelsSomething'",
                False,
                None,
                id="rule3-skips-direct-imports-inside-private-dirs",
            ),
            pytest.param(
                "tests/constants.py",
                "from tests import m\n\nclass TestsFlextTestConstants:\n    pass\n\n"
                "c = TestsFlextTestConstants\n\n"
                '__all__: list[str] = ["TestsFlextTestConstants", "c"]\n',
                "facade must extend its declared owner",
                True,
                False,
                id="rule3-test-constants-facade-shape-required",
            ),
            pytest.param(
                "tests/_typings/domain.py",
                "from tests import u\n\nclass TestsFlextTestTypesDomain:\n    pass\n",
                "facade must inherit canonical",
                False,
                True,
                id="rule3-test-private-typings-nonfacade-passes",
            ),
            pytest.param(
                "tests/typings.py",
                "from typing import TYPE_CHECKING\n\n"
                "if TYPE_CHECKING:\n"
                "    from tests import u\n\n"
                "class TestsFlextTestTypes(t):\n"
                "    class Tests(TestsFlextTestTypesBase, "
                "TestsFlextTestTypesDomain):\n"
                "        pass\n",
                "runtime namespace import",
                False,
                True,
                id="rule3-test-type-checking-reverse-import-allowed",
            ),
            pytest.param(
                "tests/models.py",
                "from tests import helper\n\nclass TestsFlextTestModels:\n    pass\n\n"
                "m = TestsFlextTestModels\n\n"
                '__all__: list[str] = ["TestsFlextTestModels", "m"]\n',
                "facade must extend its declared owner",
                True,
                False,
                id="rule3-test-facade-imports-tests-package",
            ),
            pytest.param(
                "tests/models.py",
                "from tests.conftest import helper\n\n"
                "class TestsFlextTestModels:\n"
                "    pass\n\n"
                "m = TestsFlextTestModels\n\n"
                '__all__: list[str] = ["TestsFlextTestModels", "m"]\n',
                "facade must extend its declared owner",
                True,
                False,
                id="rule3-test-facade-imports-conftest",
            ),
            pytest.param(
                "tests/models.py",
                "from tests.fixtures import helper\n\n"
                "class TestsFlextTestModels:\n"
                "    pass\n\n"
                "m = TestsFlextTestModels\n\n"
                '__all__: list[str] = ["TestsFlextTestModels", "m"]\n',
                "facade must extend its declared owner",
                True,
                False,
                id="rule3-test-facade-imports-fixtures",
            ),
            pytest.param(
                "tests/models.py",
                "from tests.unit.test_service import helper\n\n"
                "class TestsFlextTestModels:\n"
                "    pass\n\n"
                "m = TestsFlextTestModels\n\n"
                '__all__: list[str] = ["TestsFlextTestModels", "m"]\n',
                "facade must extend its declared owner",
                True,
                False,
                id="rule3-test-facade-imports-test-module",
            ),
            pytest.param(
                "tests/models.py",
                "from tests import c, t, p, m\n\n"
                "class TestsFlextTestModels(m):\n"
                "    class Tests(c, t, p):\n"
                "        pass\n",
                "facade must inherit canonical",
                False,
                True,
                id="rule3-test-models-forward-owner-assembly-allowed",
            ),
            pytest.param(
                "tests/utilities.py",
                "from tests import c, t, p, m, u\n\n"
                "class TestsFlextTestUtilities(u):\n"
                "    class Tests(c, t, p):\n"
                "        pass\n",
                "facade must inherit canonical",
                False,
                True,
                id="rule3-test-utilities-forward-owner-assembly-allowed",
            ),
            pytest.param(
                "tests/models.py",
                "from tests import m\n"
                "from tests._models.domain import TestsFlextTestModelsDomain\n\n"
                "class TestsFlextTestModels(m):\n"
                "    class Tests(TestsFlextTestModelsDomain, "
                "TestsFlextTestModelsBase):\n"
                "        pass\n",
                "test support module",
                False,
                True,
                id="rule3-test-matching-private-family-assembly-allowed",
            ),
            pytest.param(
                "tests/_typings/domain.py",
                "from tests._utilities.domain import TestsFlextTestUtilitiesDomain\n\n"
                "class TestsFlextTestTypesDomain:\n"
                "    pass\n",
                "facade must inherit canonical",
                False,
                True,
                id="rule3-test-private-family-cross-import-passes",
            ),
        ],
    )
    def test_module_path_violation_presence(
        self,
        tmp_path: Path,
        module_path: str,
        module_source: str,
        violation_substr: str,
        *,
        expect_violation: bool,
        expect_passed: bool | None,
    ) -> None:
        """Namespace rules key on the module path a project actually declares."""
        root, target = self._create_namespace_project_path(
            tmp_path, module_source=module_source, module_path=module_path
        )
        self._assert_file_in_inventory(root, target)

        report = self._validate_project(root)

        if expect_passed is not None:
            tm.that(report.passed, eq=expect_passed, msg=str(report.violations))
        tm.that(
            any(violation_substr in v for v in report.violations), eq=expect_violation
        )
