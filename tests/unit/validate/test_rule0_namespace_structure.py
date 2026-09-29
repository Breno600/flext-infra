"""Tests for Rule 0: Namespace structure and facade aliases."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import c, m, u


class TestsFlextInfraRule0NamespaceStructure:
    """Test suite for namespace validator Rule 0."""

    @pytest.mark.parametrize("family", tuple(c.Infra.FAMILY_SUFFIXES))
    def test_required_public_facade_alias_passes(
        self, tmp_path: Path, family: str
    ) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture("rule0_valid.py"),
            module_name="models.py",
        )
        layout = tm.not_none(u.Infra.layout(root))
        facade = layout.package_dir / c.Infra.FAMILY_FILES[family].lstrip("*")
        alias = c.Infra.NAMESPACE_FILE_TO_FAMILY[facade.name]
        suffix = c.Infra.FAMILY_SUFFIXES[alias]
        class_name = f"{layout.class_stem}{suffix}"
        content = facade.read_text(encoding="utf-8")
        if f"{alias} = {class_name}" not in content:
            facade.write_text(
                content
                + f"\n{alias} = {class_name}\n"
                + f"__all__ = [{class_name!r}, {alias!r}]\n",
                encoding="utf-8",
            )

        report = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )

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
        root, target = u.Tests.namespace_project_path(
            tmp_path, module_source=source, module_path=module_path
        )

        report = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )

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
        root = u.Tests.namespace_project(
            tmp_path, module_source=source, module_name="models.py"
        )

        report = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )

        tm.that(report.passed, eq=False)
        tm.that(
            any("module alias/data declaration" in item for item in report.violations),
            eq=True,
        )

    def test_rule0_valid_module_passes(self, tmp_path: Path) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture("rule0_valid.py"),
            module_name="models.py",
        )
        report = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )
        tm.that(report.passed, eq=True)
        tm.that(report.violations, empty=True)

    def test_project_without_services_needs_no_service_facades(
        self, tmp_path: Path
    ) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture("rule0_valid.py"),
            module_name="models.py",
        )
        package = tm.not_none(u.Infra.layout(root)).package_dir
        (package / "api.py").unlink()
        (package / "base.py").unlink()
        (package / "services" / "__init__.py").unlink()
        (package / "services").rmdir()

        report = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )

        tm.that(report.passed, eq=True, msg=str(report.violations))

    def test_project_with_service_requires_composition_facades(
        self, tmp_path: Path
    ) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture("rule0_valid.py"),
            module_name="models.py",
        )
        package = tm.not_none(u.Infra.layout(root)).package_dir
        (package / "services" / "search.py").write_text(
            '"""Search use case."""\nclass FlextTestSearch:\n    pass\n',
            encoding="utf-8",
        )
        (package / "api.py").unlink()
        (package / "base.py").unlink()

        report = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )

        tm.that(report.passed, eq=False)
        tm.that(
            any("missing api facade" in item for item in report.violations), eq=True
        )
        tm.that(
            any("missing base facade" in item for item in report.violations), eq=True
        )

    def test_settings_model_inherits_without_redundant_nested_namespace(
        self, tmp_path: Path
    ) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=(
                "from flext_core import FlextSettings\n\n"
                "class FlextTestSettings(FlextSettings):\n"
                '    """Project settings inherit the canonical settings model."""\n'
                "\nsettings = FlextTestSettings\n"
                "__all__ = ('FlextTestSettings', 'settings')\n"
            ),
            module_name="settings.py",
        )

        report = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )

        tm.that(report.passed, eq=True, msg=str(report.violations))
        tm.that(
            any(
                "must declare or inherit a nested namespace" in violation
                for violation in report.violations
            ),
            eq=False,
        )

    def test_project_service_base_inherits_without_artificial_namespace(
        self, tmp_path: Path
    ) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=(
                "import flext_core\n\n"
                "class FlextTestServiceBase(flext_core.s[bool]):\n"
                '    """Base inherited by the project\'s use cases."""\n'
                "\ns = FlextTestServiceBase\n"
                "__all__ = ('FlextTestServiceBase', 's')\n"
            ),
            module_name="base.py",
        )

        report = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )

        tm.that(report.passed, eq=True, msg=str(report.violations))
        tm.that(
            any(
                "must declare or inherit a nested namespace" in violation
                for violation in report.violations
            ),
            eq=False,
        )

    def test_api_does_not_publish_inherited_service_base_alias(
        self, tmp_path: Path
    ) -> None:
        root = u.Tests.namespace_project(
            tmp_path,
            module_source=(
                "from .base import FlextTestServiceBase\n\n"
                "class FlextTestApi(FlextTestServiceBase):\n"
                '    """Public composition root."""\n'
                "\napi = FlextTestApi.fetch_global()\n"
                "__all__ = ('FlextTestApi', 'api')\n"
            ),
            module_name="api.py",
        )
        (root / "src" / "flext_test" / "base.py").write_text(
            "import flext_core\n\n"
            "class FlextTestServiceBase(flext_core.s[bool]):\n"
            '    """Project service base."""\n'
            "\ns = FlextTestServiceBase\n"
            "__all__ = ('FlextTestServiceBase', 's')\n",
            encoding="utf-8",
        )

        report = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )

        tm.that(report.passed, eq=True, msg=str(report.violations))

    def test_rule0_does_not_flag_non_namespace_runtime_module(
        self, tmp_path: Path
    ) -> None:
        module_source = (
            "from __future__ import annotations\n\n"
            "VALUE = 1\n\n"
            "def helper() -> int:\n"
            "    return VALUE\n"
        )
        root = u.Tests.namespace_project(
            tmp_path, module_source=module_source, module_name="api.py"
        )

        result = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )

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
        root = u.Tests.namespace_project(
            tmp_path, module_source=module_source, module_name="runtime.py"
        )

        report = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )

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
        root = u.Tests.namespace_project(
            tmp_path, module_source=module_source, module_name="models.py"
        )

        report = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )

        tm.that(
            any(
                forbidden_violation_substr in violation
                for violation in report.violations
            ),
            eq=False,
        )

    @staticmethod
    def _write_manifest(project_root: Path, *, package: bool) -> None:
        """Declare the workspace SSOT publish contract for one project."""
        config_dir = project_root / "config"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "workspace.yaml").write_text(
            "version: 3\n"
            'name: "content-only"\n'
            "repository:\n"
            '  name: "content-only"\n'
            '  distribution: "content-only"\n'
            '  provider: "sample"\n'
            '  url: "https://example.com/content-only.git"\n'
            '  path: "."\n'
            '  role: "workspace"\n'
            '  state: "active"\n'
            '  checkout: "root"\n'
            '  codegen: "conform"\n'
            f"  package: {str(package).lower()}\n"
            "  editable: false\n"
            "  read_only: false\n"
            "members: []\n"
            "exclusions: []\n",
            encoding="utf-8",
        )

    def test_content_only_declared_root_skips_layout_contract(
        self, tmp_path: Path
    ) -> None:
        """A manifest declaring package=false receives the layout receipt.

        The invest root is the real consumer: a workspace shell whose
        analyzable surface lives in examples/tests owns no facade layout,
        so NS-LAYOUT-001 must not fire when the SSOT declares
        repository.package=false (bead invest-6n6u family).
        """
        root = u.Tests.namespace_project(
            tmp_path, module_source="VALUE = 41\n", module_name="loose_module.py"
        )
        self._write_manifest(root, package=False)
        report = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )
        tm.that(
            any("NS-LAYOUT-001" in violation for violation in report.violations),
            eq=False,
        )

    def test_undeclared_root_without_layout_stays_loud(self, tmp_path: Path) -> None:
        """No manifest declaration keeps NS-LAYOUT-001 loud.

        A root whose package discovery fails without a content-only
        declaration is a broken packaged project, not a declared topology.
        """
        root = tmp_path / "broken_packaged"
        root.mkdir()
        (root / "pyproject.toml").write_text(
            '[project]\nname = "broken-packaged"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        (root / "loose_module.py").write_text("VALUE = 41\n", encoding="utf-8")
        u.Tests.initialize_git_repo(root)
        report = u.Tests.validate_namespace_project(
            m.Infra.NamespaceValidateCommand(repository_root=root)
        )
        tm.that(
            any("NS-LAYOUT-001" in violation for violation in report.violations),
            eq=True,
        )
