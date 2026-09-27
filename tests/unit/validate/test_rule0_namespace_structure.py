"""Tests for Rule 0: Namespace structure and facade aliases."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import c, u, utilities


class TestsFlextInfraRule0NamespaceStructure(
    utilities.TestsFlextInfraUtilities.TestsFlextInfraValidateNamespaceBase
):
    """Test suite for namespace validator Rule 0."""

    @pytest.mark.parametrize("family", tuple(c.Infra.FAMILY_SUFFIXES))
    def test_required_public_facade_alias_passes(
        self, tmp_path: Path, family: str
    ) -> None:
        root = self._create_namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture("rule0_valid.py"),
            module_name="models.py",
        )
        layout = tm.not_none(u.Infra.layout(root))
        facade = layout.package_dir / c.Infra.FAMILY_FILES[family].lstrip("*")
        alias, suffix = c.Infra.NAMESPACE_FAMILY_EXPECTED_ALIAS[facade.name]
        class_name = f"{layout.class_stem}{suffix}"
        content = facade.read_text(encoding="utf-8")
        if f"{alias} = {class_name}" not in content:
            facade.write_text(
                content
                + f"\n{alias} = {class_name}\n"
                + f"__all__ = [{class_name!r}, {alias!r}]\n",
                encoding="utf-8",
            )

        report = self._validate_project(root)

        tm.that(report.passed, eq=True, msg=str(report.violations))
        tm.that(report.violations, empty=True)

    @pytest.mark.parametrize(
        ("module_path", "assignment"),
        [
            ("models.py", "other = FlextTestModels"),
            ("models.py", "m = FlextTestModelsBase"),
            ("models.py", "m = FlextTestModels.Test"),
            ("models.py", "m = other = FlextTestModels"),
            ("models.py", "m, other = FlextTestModels, FlextTestModels"),
            ("models.py", "VALUE = 42"),
            ("models.py", "m: type[FlextTestModels]"),
            ("models.py", "m = FlextTestModels\nother = FlextTestModels"),
            ("models.py", "m = FlextTestModels\nm = FlextTestModels"),
            ("_models/models.py", "m = FlextTestModels"),
            ("services/models.py", "m = FlextTestModels"),
        ],
    )
    def test_noncanonical_facade_assignments_still_fail(
        self, tmp_path: Path, module_path: str, assignment: str
    ) -> None:
        source = u.Tests.namespace_fixture("rule0_valid.py").replace(
            "m = FlextTestModels", assignment
        )
        root, target = self._create_namespace_project_path(
            tmp_path, module_source=source, module_path=module_path
        )

        report = self._validate_project(root)

        tm.that(report.passed, eq=False)
        tm.that(
            any(
                str(target.relative_to(root)) in violation
                and "module alias/data declaration is forbidden" in violation
                for violation in report.violations
            ),
            eq=True,
        )

    def test_facade_alias_before_class_is_not_canonical(self, tmp_path: Path) -> None:
        source = u.Tests.namespace_fixture("rule0_valid.py").replace(
            "m = FlextTestModels", ""
        )
        source = source.replace(
            "class FlextTestModels(FlextTestModelsBase):",
            "m = FlextTestModels\n\nclass FlextTestModels(FlextTestModelsBase):",
        )
        root = self._create_namespace_project(
            tmp_path, module_source=source, module_name="models.py"
        )

        report = self._validate_project(root)

        tm.that(report.passed, eq=False)
        tm.that(
            any("module alias/data declaration" in item for item in report.violations),
            eq=True,
        )

    def test_rule0_valid_module_passes(self, tmp_path: Path) -> None:
        root = self._create_namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture("rule0_valid.py"),
            module_name="models.py",
        )
        report = self._validate_project(root)
        tm.that(report.passed, eq=True)
        tm.that(report.violations, empty=True)

    def test_rule0_does_not_flag_non_namespace_runtime_module(
        self, tmp_path: Path
    ) -> None:
        module_source = (
            "from __future__ import annotations\n\n"
            "VALUE = 1\n\n"
            "def helper() -> int:\n"
            "    return VALUE\n"
        )
        root = self._create_namespace_project(
            tmp_path, module_source=module_source, module_name="api.py"
        )

        result = self._validate_project(root)

        tm.that(
            any(violation.startswith("[NS-000") for violation in result.violations),
            eq=False,
        )

    @pytest.mark.parametrize(
        "module_source",
        [
            pytest.param("class RuntimeService:\n    pass\n", id="class"),
            pytest.param("def runtime_service() -> None:\n    pass\n", id="function"),
            pytest.param("pass\n", id="module-statement"),
        ],
    )
    def test_rule0_validates_statements_without_expression_values(
        self, tmp_path: Path, module_source: str
    ) -> None:
        """Ordinary statements without expression values remain valid AST input."""
        root = self._create_namespace_project(
            tmp_path, module_source=module_source, module_name="runtime.py"
        )

        report = self._validate_project(root)

        tm.that(report.violations, empty=False)

    @pytest.mark.parametrize(
        ("module_source", "forbidden_violation_substr"),
        [
            pytest.param(
                "from __future__ import annotations\n"
                "from typing import TYPE_CHECKING\n\n"
                "if TYPE_CHECKING:\n"
                "    from collections.abc import Sequence\n\n"
                "class FlextTestModels(Models):\n"
                "    pass\n",
                "Disallowed top-level statement: If",
                id="rule0-allows-type-checking-block",
            ),
            pytest.param(
                "from __future__ import annotations\n\n"
                "class FlextTestModels(Models):\n"
                "    pass\n\n"
                '__all__: list[str] = ["FlextTestModels"]\n',
                "Disallowed top-level statement: AnnAssign",
                id="rule0-allows-annotated-dunder-assign",
            ),
        ],
    )
    def test_rule0_allows_top_level_statement(
        self, tmp_path: Path, module_source: str, forbidden_violation_substr: str
    ) -> None:
        """Rule 0 never rejects the top-level statements a namespace may carry."""
        root = self._create_namespace_project(
            tmp_path, module_source=module_source, module_name="models.py"
        )

        report = self._validate_project(root)

        tm.that(
            any(
                forbidden_violation_substr in violation
                for violation in report.violations
            ),
            eq=False,
        )
