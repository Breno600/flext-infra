"""Tests for the refactor class-placement detector."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.detectors.class_placement_detector import (
    FlextInfraClassPlacementDetector,
)
from flext_infra.refactor.classvar_constant_autofix import (
    FlextInfraRefactorClassvarConstantAutofix,
)
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraRefactorInfraRefactorClassPlacement:
    """Behavior contract for test_infra_refactor_class_placement."""

    def test_detects_basemodel_in_non_model_file(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "consumer.py",
                "from pydantic import BaseModel\nclass PublicModel(BaseModel):\n    pass\n",
                rope_project,
            )
        )

        tm.that(len(violations), eq=1)
        tm.that(violations[0].name, eq="PublicModel")
        tm.that(violations[0].base_class, eq="BaseModel")

    def test_detects_attribute_base_class(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "consumer.py",
                "from flext_core import FlextModels\n"
                "class PublicModel(FlextModels.ArbitraryTypesModel):\n"
                "    pass\n",
                rope_project,
            )
        )

        tm.that(len(violations), eq=1)
        tm.that(violations[0].name, eq="PublicModel")
        tm.that(violations[0].base_class, eq="ArbitraryTypesModel")

    def test_skips_models_file(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "models.py",
                "from pydantic import BaseModel\nclass PublicModel(BaseModel):\n    pass\n",
                rope_project,
            )
        )

        tm.that(violations, eq=[])

    def test_skips_models_directory(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "models" / "domain.py",
                "from pydantic import BaseModel\nclass PublicModel(BaseModel):\n    pass\n",
                rope_project,
            )
        )

        tm.that(violations, eq=[])

    def test_skips_private_models_directory(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "_models" / "domain.py",
                "from pydantic import BaseModel\nclass PublicModel(BaseModel):\n    pass\n",
                rope_project,
            )
        )

        tm.that(violations, eq=[])

    def test_skips_settings_file(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        settings_file_name = min(c.Infra.NAMESPACE_SETTINGS_FILE_NAMES)
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / settings_file_name,
                "from pydantic import BaseModel\nclass PublicModel(BaseModel):\n    pass\n",
                rope_project,
            )
        )

        tm.that(violations, eq=[])

    def test_skips_protected_files(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        protected_file_name = min(c.Infra.NAMESPACE_PROTECTED_FILES)
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / protected_file_name,
                "from pydantic import BaseModel\nclass PublicModel(BaseModel):\n    pass\n",
                rope_project,
            )
        )

        tm.that(violations, eq=[])

    def test_skips_private_class(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "consumer.py",
                "from pydantic import BaseModel\nclass _PrivateModel(BaseModel):\n    pass\n",
                rope_project,
            )
        )

        tm.that(violations, eq=[])

    def test_detects_multiple_models(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "consumer.py",
                "from pydantic import BaseModel\n"
                "from flext_core import FlextModels\n"
                "class FirstModel(BaseModel):\n"
                "    pass\n"
                "class SecondModel(FlextModels.ArbitraryTypesModel):\n"
                "    pass\n",
                rope_project,
            )
        )

        tm.that(len(violations), eq=2)
        tm.that(
            {violation.name for violation in violations},
            eq={"FirstModel", "SecondModel"},
        )

    def test_non_pydantic_class_not_flagged(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "consumer.py", "class PlainClass:\n    pass\n", rope_project
            )
        )

        tm.that(violations, eq=[])

    @pytest.mark.parametrize(
        "source",
        [
            (
                "from typing import ClassVar\n"
                "class PlainClass:\n"
                "    GROUPS: ClassVar[frozenset[str]] = frozenset({'a'})\n"
            ),
            "class PlainClass:\n    GROUPS = frozenset({'a'})\n",
        ],
        ids=["explicit_classvar", "implicit_constant"],
    )
    def test_detects_class_constant_outside_constants(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject, source: str
    ) -> None:
        """An annotated ClassVar and a bare UPPER_CASE constant both relocate."""
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(tmp_path / "consumer.py", source, rope_project)
        )

        tm.that(len(violations), eq=1)
        tm.that(violations[0].name, eq="GROUPS")
        tm.that(violations[0].action, eq="classvar_relocation")

    def test_detects_every_class_constant_in_one_class(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Every class-level constant is reported, not only the first one."""
        source = (
            "class PlainClass:\n"
            "    VERSION = '1.0'\n"
            "    VENDOR_STRING_MAX_TOKENS = 64\n"
        )
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(tmp_path / "consumer.py", source, rope_project)
        )

        tm.that(
            sorted(v.name for v in violations),
            eq=["VENDOR_STRING_MAX_TOKENS", "VERSION"],
        )
        tm.that({v.action for v in violations}, eq={"classvar_relocation"})

    def test_skips_implicit_constant_inside_constants_directory(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "_constants" / "domain.py",
                "class PlainClass:\n    GROUPS = frozenset({'a'})\n",
                rope_project,
            )
        )

        tm.that(violations, eq=[])

    def test_detects_constants_nested_inside_a_facade_class(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Nested domain-class constants carry a dotted owner and are reported."""
        source = (
            "class Facade:\n"
            "    class Domain:\n"
            "        DEFAULT_CHARSET: str = 'UTF8'\n"
            "        MAX_NAME_LENGTH: int = 100\n"
        )
        violations = FlextInfraClassPlacementDetector.detect_file(
            u.Tests.detector_context(tmp_path / "constants.py", source, rope_project)
        )

        tm.that(
            sorted((v.base_class, v.name) for v in violations),
            eq=[
                ("Facade.Domain", "DEFAULT_CHARSET"),
                ("Facade.Domain", "MAX_NAME_LENGTH"),
            ],
        )
        tm.that({v.action for v in violations}, eq={"classvar_relocation"})

    def test_autofix_relocates_a_nested_owner_constant(self, tmp_path: Path) -> None:
        """Autofix can relocate a constant owned by a nested class."""
        pkg = tmp_path / "src" / "demo"
        (pkg / "_constants").mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "_constants" / "__init__.py").write_text(
            '"""Constants."""\n', encoding="utf-8"
        )
        (pkg / "facade.py").write_text(
            "class Facade:\n    class Domain:\n        DEFAULT_CHARSET: str = 'UTF8'\n",
            encoding="utf-8",
        )

        result = FlextInfraRefactorClassvarConstantAutofix.apply(
            tmp_path,
            "demo.facade.Facade.Domain",
            "DEFAULT_CHARSET",
            "demo._constants",
            dry_run=True,
        )

        touched_files = " ".join(result.touched_files)
        tm.that(touched_files, has="demo/facade.py")
        tm.that(touched_files, has="demo/_constants/__init__.py")
        tm.that(result.source_text, has="class Domain:")
        tm.that(result.source_text, lacks="DEFAULT_CHARSET: str = 'UTF8'")
        tm.that(result.target_text, has="DEFAULT_CHARSET: str = 'UTF8'")

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
