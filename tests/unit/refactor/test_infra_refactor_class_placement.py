"""Tests for the refactor class-placement detector."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from flext_infra.detectors.class_placement_detector import (
    FlextInfraClassPlacementDetector,
)
from flext_infra.fixers.rope_fixer import FlextInfraRopeFixerAdapter
from flext_infra.refactor.classvar_constant_autofix import (
    FlextInfraRefactorClassvarConstantAutofix,
)
from flext_tests import tm
from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraRefactorInfraRefactorClassPlacement:
    """Behavior contract for test_infra_refactor_class_placement."""

    def test_detects_basemodel_in_non_model_file(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        target = tmp_path / "consumer.py"
        target.write_text(
            "from pydantic import BaseModel\nclass PublicModel(BaseModel):\n    pass\n",
            encoding="utf-8",
        )

        violations = FlextInfraClassPlacementDetector.detect_file(
            m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
        )

        tm.that(len(violations), eq=1)
        tm.that(violations[0].name, eq="PublicModel")
        tm.that(violations[0].base_class, eq="BaseModel")

    def test_detects_attribute_base_class(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        target = tmp_path / "consumer.py"
        target.write_text(
            "from flext_core import FlextModels\n"
            "class PublicModel(FlextModels.ArbitraryTypesModel):\n"
            "    pass\n",
            encoding="utf-8",
        )

        violations = FlextInfraClassPlacementDetector.detect_file(
            m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
        )

        tm.that(len(violations), eq=1)
        tm.that(violations[0].name, eq="PublicModel")
        tm.that(violations[0].base_class, eq="ArbitraryTypesModel")

    def test_skips_models_file(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        target = tmp_path / "models.py"
        target.write_text(
            "from pydantic import BaseModel\nclass PublicModel(BaseModel):\n    pass\n",
            encoding="utf-8",
        )

        violations = FlextInfraClassPlacementDetector.detect_file(
            m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
        )

        tm.that(violations, eq=[])

    def test_skips_models_directory(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        models_dir = tmp_path / "models"
        models_dir.mkdir(parents=True)
        target = models_dir / "domain.py"
        target.write_text(
            "from pydantic import BaseModel\nclass PublicModel(BaseModel):\n    pass\n",
            encoding="utf-8",
        )

        violations = FlextInfraClassPlacementDetector.detect_file(
            m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
        )

        tm.that(violations, eq=[])

    def test_skips_private_models_directory(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        models_dir = tmp_path / "_models"
        models_dir.mkdir(parents=True)
        target = models_dir / "domain.py"
        target.write_text(
            "from pydantic import BaseModel\nclass PublicModel(BaseModel):\n    pass\n",
            encoding="utf-8",
        )

        violations = FlextInfraClassPlacementDetector.detect_file(
            m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
        )

        tm.that(violations, eq=[])

    def test_skips_sanctioned_root_namespace_files(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        for file_name in ("result.py", "lazy.py", "mixins.py"):
            target = tmp_path / file_name
            target.write_text(
                "from pydantic import BaseModel\n"
                "class PublicModel(BaseModel):\n"
                "    pass\n",
                encoding="utf-8",
            )

            violations = FlextInfraClassPlacementDetector.detect_file(
                m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
            )

            tm.that(violations, eq=[])

    def test_skips_settings_file(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        settings_file_name = min(c.Infra.NAMESPACE_SETTINGS_FILE_NAMES)
        target = tmp_path / settings_file_name
        target.write_text(
            "from pydantic import BaseModel\nclass PublicModel(BaseModel):\n    pass\n",
            encoding="utf-8",
        )

        violations = FlextInfraClassPlacementDetector.detect_file(
            m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
        )

        tm.that(violations, eq=[])

    def test_skips_protected_files(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        protected_file_name = min(c.Infra.NAMESPACE_PROTECTED_FILES)
        target = tmp_path / protected_file_name
        target.write_text(
            "from pydantic import BaseModel\nclass PublicModel(BaseModel):\n    pass\n",
            encoding="utf-8",
        )

        violations = FlextInfraClassPlacementDetector.detect_file(
            m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
        )

        tm.that(violations, eq=[])

    def test_skips_private_class(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        target = tmp_path / "consumer.py"
        target.write_text(
            "from pydantic import BaseModel\nclass _PrivateModel(BaseModel):\n    pass\n",
            encoding="utf-8",
        )

        violations = FlextInfraClassPlacementDetector.detect_file(
            m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
        )

        tm.that(violations, eq=[])

    def test_detects_multiple_models(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        target = tmp_path / "consumer.py"
        target.write_text(
            "from pydantic import BaseModel\n"
            "from flext_core import FlextModels\n"
            "class FirstModel(BaseModel):\n"
            "    pass\n"
            "class SecondModel(FlextModels.ArbitraryTypesModel):\n"
            "    pass\n",
            encoding="utf-8",
        )

        violations = FlextInfraClassPlacementDetector.detect_file(
            m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
        )

        tm.that(len(violations), eq=2)
        tm.that(
            {violation.name for violation in violations},
            eq={"FirstModel", "SecondModel"},
        )

    def test_non_pydantic_class_not_flagged(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        target = tmp_path / "consumer.py"
        target.write_text("class PlainClass:\n    pass\n", encoding="utf-8")

        violations = FlextInfraClassPlacementDetector.detect_file(
            m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
        )

        tm.that(violations, eq=[])

    def test_detects_classvar_constant_outside_constants(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        target = tmp_path / "consumer.py"
        target.write_text(
            "from typing import ClassVar\n"
            "class PlainClass:\n"
            "    GROUPS: ClassVar[frozenset[str]] = frozenset({'a'})\n",
            encoding="utf-8",
        )

        violations = FlextInfraClassPlacementDetector.detect_file(
            m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
        )

        tm.that(len(violations), eq=1)
        tm.that(violations[0].name, eq="GROUPS")
        tm.that(violations[0].action, eq="classvar_relocation")

    def test_detects_implicit_constant_without_classvar(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        target = tmp_path / "consumer.py"
        target.write_text(
            "class PlainClass:\n    GROUPS = frozenset({'a'})\n", encoding="utf-8"
        )

        violations = FlextInfraClassPlacementDetector.detect_file(
            m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
        )

        tm.that(len(violations), eq=1)
        tm.that(violations[0].name, eq="GROUPS")
        tm.that(violations[0].action, eq="classvar_relocation")

    def test_skips_implicit_constant_inside_constants_directory(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        constants_dir = tmp_path / "_constants"
        constants_dir.mkdir(parents=True)
        target = constants_dir / "domain.py"
        target.write_text(
            "class PlainClass:\n    GROUPS = frozenset({'a'})\n", encoding="utf-8"
        )

        violations = FlextInfraClassPlacementDetector.detect_file(
            m.Infra.DetectorContext(file_path=target, rope_project=rope_project)
        )

        tm.that(violations, eq=[])

    def test_autofix_moves_implicit_constant(self, tmp_path: Path) -> None:
        """Autofix can relocate an implicit UPPER_CASE class constant."""
        pkg = tmp_path / "src" / "demo"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "service.py").write_text(
            "class DemoService:\n"
            "    GROUPS = frozenset({'a'})\n"
            "    def run(self) -> None:\n"
            "        u.Cli.print(DemoService.GROUPS)\n",
            encoding="utf-8",
        )
        constants_mod = pkg / "_constants.py"
        constants_mod.write_text('"""Constants."""\n', encoding="utf-8")

        result = FlextInfraRefactorClassvarConstantAutofix.apply(
            tmp_path,
            "demo.service.DemoService",
            "GROUPS",
            "demo._constants",
            dry_run=True,
        )

        touched_files = result.touched_files
        tm.that(touched_files, is_=(list, tuple))
        tm.that(" ".join(touched_files), has="demo/service.py")
        tm.that(" ".join(touched_files), has="demo/_constants.py")
        target_text = result.target_text
        source_text = result.source_text
        tm.that(isinstance(target_text, str), eq=True)
        tm.that(isinstance(source_text, str), eq=True)
        tm.that(target_text, has="GROUPS = frozenset({'a'})")
        tm.that(source_text, lacks="GROUPS = frozenset({'a'})")

    def test_autofix_dry_run_fails_missing_constants_module(
        self, tmp_path: Path
    ) -> None:
        """Dry-run fails loud when the canonical constants module is absent."""
        pkg = tmp_path / "src" / "demo"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        constants_mod = pkg / "_constants.py"
        (pkg / "service.py").write_text(
            "class DemoService:\n"
            "    GROUPS = frozenset({'a'})\n"
            "    def run(self) -> None:\n"
            "        u.Cli.print(DemoService.GROUPS)\n",
            encoding="utf-8",
        )

        with pytest.raises(TypeError, match=r"constants module demo\._constants"):
            FlextInfraRefactorClassvarConstantAutofix.apply(
                tmp_path,
                "demo.service.DemoService",
                "GROUPS",
                "demo._constants",
                dry_run=True,
            )

        tm.that(not constants_mod.exists(), eq=True)

    def test_autofix_dry_run_resolves_project_tests_package(
        self, tmp_path: Path
    ) -> None:
        """Project-local Rope roots resolve top-level tests packages."""
        tests_pkg = tmp_path / "tests" / "unit"
        tests_pkg.mkdir(parents=True)
        (tmp_path / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (tests_pkg / "__init__.py").write_text("", encoding="utf-8")
        (tests_pkg / "_constants.py").write_text('"""Constants."""\n', encoding="utf-8")
        (tests_pkg / "test_execution_result.py").write_text(
            "class TestsDemo:\n"
            "    TEST_VALUE = 1.5\n"
            "    def test_value(self) -> None:\n"
            "        assert self.TEST_VALUE == 1.5\n",
            encoding="utf-8",
        )

        result = FlextInfraRefactorClassvarConstantAutofix.apply(
            tmp_path,
            "tests.unit.test_execution_result.TestsDemo",
            "TEST_VALUE",
            "tests.unit._constants",
            dry_run=True,
        )

        target_text = result.target_text
        source_text = result.source_text
        tm.that(isinstance(target_text, str), eq=True)
        tm.that(isinstance(source_text, str), eq=True)
        tm.that(target_text, has="TEST_VALUE = 1.5")
        tm.that(source_text, lacks="TEST_VALUE = 1.5")

    @staticmethod
    def _classvar_rule() -> m.EnforcementRuleSpec:
        catalog = u.build_canonical_catalog()
        return next(
            rule
            for rule in catalog.enabled_rules()
            if rule.fix_action is not None
            and rule.fix_action.target == "classvar_relocation"
        )

    @staticmethod
    def _write_classvar_test_module(project_root: Path) -> Path:
        tests_pkg = project_root / "tests" / "unit"
        tests_pkg.mkdir(parents=True)
        (project_root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (tests_pkg / "__init__.py").write_text("", encoding="utf-8")
        module_path = tests_pkg / "test_execution_result.py"
        module_path.write_text(
            "class TestsDemo:\n"
            "    TEST_VALUE = 1.5\n"
            "    def test_value(self) -> None:\n"
            "        assert self.TEST_VALUE == 1.5\n",
            encoding="utf-8",
        )
        return module_path

    def test_classvar_relocation_targets_tests_package_constants(
        self, tmp_path: Path
    ) -> None:
        """ENFORCE-079 maps project tests modules to their sibling _constants."""
        project_root = tmp_path / "demo"
        module_path = self._write_classvar_test_module(project_root)
        adapter = FlextInfraRopeFixerAdapter(tmp_path)
        ctx = m.Infra.FixEnforcementCommand(
            workspace=str(tmp_path), projects=("demo",), apply=False
        )

        result = adapter.fix_project(
            project_root,
            ((self._classvar_rule(), SimpleNamespace(file_path=str(module_path))),),
            ctx,
        )

        tm.that(
            " ".join(fix.error for fix in result.failed), has="tests.unit._constants"
        )

    def test_classvar_relocation_uses_existing_tests_root_constants(
        self, tmp_path: Path
    ) -> None:
        """ENFORCE-079 reuses an existing top-level tests constants SSOT."""
        project_root = tmp_path / "demo"
        module_path = self._write_classvar_test_module(project_root)
        constants_root = project_root / "tests" / "_constants"
        constants_root.mkdir(parents=True)
        (constants_root / "__init__.py").write_text("", encoding="utf-8")
        adapter = FlextInfraRopeFixerAdapter(tmp_path)
        ctx = m.Infra.FixEnforcementCommand(
            workspace=str(tmp_path), projects=("demo",), apply=False
        )

        result = adapter.fix_project(
            project_root,
            ((self._classvar_rule(), SimpleNamespace(file_path=str(module_path))),),
            ctx,
        )

        tm.that(
            " ".join(preview.message for preview in result.previewed),
            has="tests._constants",
        )

    def test_autofix_dry_run_resolves_package_constants_module(
        self, tmp_path: Path
    ) -> None:
        """ENFORCE-079 writes package-backed _constants modules through __init__."""
        tests_root = tmp_path / "tests"
        tests_pkg = tests_root / "unit"
        constants_root = tests_root / "_constants"
        tests_pkg.mkdir(parents=True)
        constants_root.mkdir(parents=True)
        (tests_root / "__init__.py").write_text("", encoding="utf-8")
        (tests_pkg / "__init__.py").write_text("", encoding="utf-8")
        (constants_root / "__init__.py").write_text(
            '"""Constants."""\n', encoding="utf-8"
        )
        (tests_pkg / "test_execution_result.py").write_text(
            "class TestsDemo:\n"
            "    TEST_VALUE = 1.5\n"
            "    def test_value(self) -> None:\n"
            "        assert self.TEST_VALUE == 1.5\n",
            encoding="utf-8",
        )

        result = FlextInfraRefactorClassvarConstantAutofix.apply(
            tmp_path,
            "tests.unit.test_execution_result.TestsDemo",
            "TEST_VALUE",
            "tests._constants",
            dry_run=True,
        )

        target_text = result.target_text
        source_text = result.source_text
        touched_files = result.touched_files
        tm.that(isinstance(target_text, str), eq=True)
        tm.that(isinstance(source_text, str), eq=True)
        tm.that(touched_files, is_=(list, tuple))
        tm.that(target_text, has="TEST_VALUE = 1.5")
        tm.that(source_text, lacks="TEST_VALUE = 1.5")
        tm.that(" ".join(touched_files), has="tests/_constants/__init__.py")

    def test_autofix_apply_inserts_import_after_module_header(
        self, tmp_path: Path
    ) -> None:
        """Apply mode inserts constants import at module scope."""
        pkg = tmp_path / "src" / "demo"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "_constants.py").write_text('"""Constants."""\n', encoding="utf-8")
        service = pkg / "service.py"
        service.write_text(
            '"""Demo service."""\n\n'
            "from __future__ import annotations\n\n"
            "class DemoService:\n"
            "    VALUE = 1.5\n\n"
            "    def run(self) -> float:\n"
            '        """Return value."""\n'
            "        return self.VALUE\n",
            encoding="utf-8",
        )

        FlextInfraRefactorClassvarConstantAutofix.apply(
            tmp_path,
            "demo.service.DemoService",
            "VALUE",
            "demo._constants",
            dry_run=False,
        )

        source_text = service.read_text(encoding="utf-8")
        tm.that(source_text, has="from __future__ import annotations")
        tm.that(source_text, has="from . import _constants")
        tm.that(
            source_text.index("from __future__ import annotations")
            < source_text.index("from . import _constants"),
            eq=True,
        )
        tm.that(source_text, lacks='"""Return value."""\nfrom . import _constants')
        tm.that(source_text, has="return _constants.VALUE")

    def test_autofix_apply_removes_alias_to_existing_constant_owner(
        self, tmp_path: Path
    ) -> None:
        """Apply mode removes class aliases without duplicating constants."""
        pkg = tmp_path / "src" / "demo"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        constants_mod = pkg / "_constants.py"
        constants_text = '"""Constants."""\n\nVALUE = 1.5\n'
        constants_mod.write_text(constants_text, encoding="utf-8")
        service = pkg / "service.py"
        source_text = (
            '"""Demo service."""\n\n'
            "from __future__ import annotations\n\n"
            "from . import _constants\n\n"
            "class DemoService:\n"
            "    VALUE = _constants.VALUE\n\n"
            "    def run(self) -> float:\n"
            "        return self.VALUE\n"
        )
        service.write_text(source_text, encoding="utf-8")

        dry_run_result = FlextInfraRefactorClassvarConstantAutofix.apply(
            tmp_path,
            "demo.service.DemoService",
            "VALUE",
            "demo._constants",
            dry_run=True,
        )

        tm.that(dry_run_result.target_text, eq=constants_text)
        tm.that(constants_mod.read_text(encoding="utf-8"), eq=constants_text)
        tm.that(service.read_text(encoding="utf-8"), eq=source_text)

        FlextInfraRefactorClassvarConstantAutofix.apply(
            tmp_path,
            "demo.service.DemoService",
            "VALUE",
            "demo._constants",
            dry_run=False,
        )

        updated_source = service.read_text(encoding="utf-8")
        updated_constants = constants_mod.read_text(encoding="utf-8")
        tm.that(updated_constants, eq=constants_text)
        tm.that(updated_source, lacks="    VALUE = _constants.VALUE")
        tm.that(updated_source, has="return _constants.VALUE")

    def test_autofix_apply_moves_multiline_classvar_to_src_constants(
        self, tmp_path: Path
    ) -> None:
        """Apply mode moves multiline constants to the package src tree."""
        pkg = tmp_path / "src" / "demo"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        constants_pkg = pkg / "_constants"
        constants_pkg.mkdir()
        (constants_pkg / "__init__.py").write_text("", encoding="utf-8")
        (constants_pkg / "factory.py").write_text(
            '"""Factory constants."""\n', encoding="utf-8"
        )
        (pkg / "typings.py").write_text(
            "from typing import TypeAlias\n\n"
            "JsonMapping: TypeAlias = dict[str, int | bool]\n",
            encoding="utf-8",
        )
        service = pkg / "service.py"
        service.write_text(
            '"""Demo service."""\n\n'
            "from __future__ import annotations\n\n"
            "from collections.abc import Mapping\n"
            "from typing import ClassVar\n\n"
            "from demo.typings import t\n\n"
            "class DemoService:\n"
            "    PRESETS: ClassVar[Mapping[str, t.JsonMapping]] = {\n"
            '        "development": {\n'
            '            "batch_size": 100,\n'
            '            "enabled": True,\n'
            "        },\n"
            "    }\n\n"
            "    def run(self) -> t.JsonMapping:\n"
            '        return self.PRESETS["development"]\n',
            encoding="utf-8",
        )

        FlextInfraRefactorClassvarConstantAutofix.apply(
            tmp_path,
            "demo.service.DemoService",
            "PRESETS",
            "demo._constants.factory",
            dry_run=False,
        )

        constants = pkg / "_constants" / "factory.py"
        constants_init = pkg / "_constants" / "__init__.py"
        source_text = service.read_text(encoding="utf-8")
        constants_text = constants.read_text(encoding="utf-8")
        tm.that(constants.exists(), eq=True)
        tm.that(constants_init.exists(), eq=True)
        tm.that(source_text, lacks="PRESETS: ClassVar")
        tm.that(source_text, has='return factory.PRESETS["development"]')
        tm.that(source_text, has="from ._constants import factory")
        tm.that(constants_text, has="from collections.abc import Mapping")
        tm.that(constants_text, lacks="from typing import ClassVar")
        tm.that(constants_text, has="from demo.typings import t")
        tm.that(constants_text, has="PRESETS: Mapping[str, t.JsonMapping]")
        tm.that(constants_text, has='    "development": {')
        tm.that(constants_text, has='"batch_size": 100')

    def test_autofix_dry_run_removes_alias_when_constants_owner_exists(
        self, tmp_path: Path
    ) -> None:
        """Class-level aliases to an existing constants owner are not duplicated."""
        pkg = tmp_path / "src" / "demo"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "_constants.py").write_text(
            "from __future__ import annotations\n\n"
            "GROUPS: frozenset[str] = frozenset({'a'})\n",
            encoding="utf-8",
        )
        (pkg / "service.py").write_text(
            "from __future__ import annotations\n\n"
            "from typing import ClassVar\n\n"
            "from . import _constants\n\n\n"
            "class DemoService:\n"
            "    GROUPS: ClassVar[frozenset[str]] = _constants.GROUPS\n\n"
            "    def groups(self) -> frozenset[str]:\n"
            "        return self.GROUPS\n",
            encoding="utf-8",
        )

        result = FlextInfraRefactorClassvarConstantAutofix.apply(
            tmp_path,
            "demo.service.DemoService",
            "GROUPS",
            "demo._constants",
            dry_run=True,
        )

        source_text = result.source_text
        target_text = result.target_text
        source_text = tm.not_none(source_text)
        target_text = tm.not_none(target_text)
        tm.that(source_text, lacks="GROUPS: ClassVar")
        tm.that(source_text, has="_constants.GROUPS")
        tm.that(target_text.count("GROUPS"), eq=1)
