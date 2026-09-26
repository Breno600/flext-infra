"""Unit tests for namespace enforcer detection and auto-fix behaviors."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.detectors.loose_object_detector import FlextInfraLooseObjectDetector
from flext_infra.detectors.manual_protocol_detector import (
    FlextInfraManualProtocolDetector,
)
from flext_infra.refactor.namespace_enforcer import FlextInfraNamespaceEnforcer
from tests import m, u

if TYPE_CHECKING:
    from tests import t


class TestsFlextInfraRefactorInfraRefactorNamespaceEnforcer:
    """Behavior contract for test_infra_refactor_namespace_enforcer."""

    def test_namespace_enforcer_creates_missing_facades_and_rewrites_imports(
        self, tmp_path: Path
    ) -> None:
        """Create missing facades and rewrite imports during enforcement."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        _ = (pkg / "service.py").write_text(
            "from flext_core import c, m, r, p, t, u, p\nfrom flext_infra import c, m, t, u, p\n\nVALUE = 1",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=True
        )

        tm.that(report.total_facades_missing, eq=0)
        tm.that(report.total_import_violations, eq=0)
        tm.that((pkg / "constants.py").exists(), eq=True)
        tm.that((pkg / "typings.py").exists(), eq=True)
        tm.that((pkg / "protocols.py").exists(), eq=True)
        tm.that((pkg / "models.py").exists(), eq=True)
        tm.that((pkg / "utilities.py").exists(), eq=True)

        service_source = (pkg / "service.py").read_text(encoding="utf-8")
        tm.that(service_source, has="from __future__ import annotations")
        tm.that(service_source, has="VALUE = 1")
        tm.that(service_source, lacks="from flext_core import c, m, r, p, t, u, p")
        tm.that(service_source, lacks="from flext_infra import c, m, t, u, p")
        tm.that(service_source, lacks="from sample_pkg import")

    def test_namespace_enforcer_detects_manual_typings_and_compat_aliases(
        self, tmp_path: Path
    ) -> None:
        """Detect manual typings and compatibility aliases."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        _ = (pkg / "service.py").write_text(
            "from __future__ import annotations\nfrom typing import TypeAlias\n\nPayloadMap: TypeAlias = dict[str, str]\nLegacyResult = ModernResult",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=False
        )

        tm.that(report.total_manual_typing_violations, gt=0)
        tm.that(report.total_compatibility_alias_violations, gt=0)

    def test_namespace_enforcer_splits_foreign_canonical_aliases(
        self, tmp_path: Path
    ) -> None:
        """ENFORCE-080 has a distinct report field from legacy aliases."""
        workspace, _project, pkg = u.Tests.namespace_workspace(
            tmp_path,
            project_name="flext-infra",
            package_name="flext_infra",
            pyproject="[project]\nname='flext-infra'\n",
        )
        models_dir = pkg / "_models"
        typings_dir = pkg / "_typings"
        models_dir.mkdir()
        typings_dir.mkdir()
        _ = (pkg / "service.py").write_text(
            "from __future__ import annotations\n\n"
            "from flext_core import c, r, t\n\n"
            "VALUE = c.MAX_SIZE\n"
            "RESULT: r.Result[str] | None = None\n"
            "NAMES: t.StrSequence = ()\n",
            encoding="utf-8",
        )
        _ = (pkg / "submodule_consumer.py").write_text(
            "from __future__ import annotations\n\n"
            "from flext_core.typings import (\n"
            "    FlextTypes as t,\n"
            ")\n\n"
            "NAMES: t.StrSequence = ()\n",
            encoding="utf-8",
        )
        _ = (models_dir / "base.py").write_text(
            "from __future__ import annotations\n\n"
            "from flext_core import m\n\n"
            "class DemoModel(m.Base):\n"
            "    value: str\n",
            encoding="utf-8",
        )
        _ = (typings_dir / "base.py").write_text(
            "from __future__ import annotations\n\n"
            "from flext_core import m, t\n\n"
            "Payload = t.StrMapping\n"
            "ModelBase = m.Base\n",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=False
        )

        project_report = report.projects[0]
        tm.that(report.total_compatibility_alias_violations, eq=0)
        tm.that(report.total_foreign_canonical_alias_violations, gt=0)
        tm.that(project_report.compatibility_alias_violations, empty=True)
        tm.that(project_report.foreign_canonical_alias_violations, empty=False)
        violation_paths = {
            Path(violation.file).relative_to(pkg).as_posix()
            for violation in project_report.foreign_canonical_alias_violations
        }
        tm.that(violation_paths, has="submodule_consumer.py")
        tm.that(violation_paths, lacks="_models/base.py")
        tm.that(violation_paths, lacks="_typings/base.py")
        rendered = FlextInfraNamespaceEnforcer.render_text(report)
        tm.that(rendered, has="Foreign canonical alias violations:")

    def test_namespace_enforcer_detects_manual_protocol_outside_canonical_files(
        self, tmp_path: Path
    ) -> None:
        """Detect manual protocols outside canonical protocol modules."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        _ = (pkg / "service.py").write_text(
            "from __future__ import annotations\nfrom typing import Protocol\n\nclass ServiceContract(Protocol):\n    def run(self) -> str:\n        ...",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=False
        )

        tm.that(report.total_manual_protocol_violations, eq=1)
        project_report = report.projects[0]
        violations = project_report.manual_protocol_violations
        tm.that(len(violations), eq=1)
        violation = violations[0]
        tm.that(violation.name, eq="ServiceContract")
        rendered = FlextInfraNamespaceEnforcer.render_text(report)
        tm.that(rendered, has="Manual protocol violations: 1")

    def test_namespace_enforcer_detects_internal_private_imports(
        self, tmp_path: Path
    ) -> None:
        """Detect imports that cross an internal private boundary."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        _ = (pkg / "service.py").write_text(
            "from __future__ import annotations\nfrom flext_core import FlextUtilitiesGuards\nfrom sample_pkg.protocols import _InternalContract\n\n_ = FlextUtilitiesGuards\n_ = _InternalContract",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=False
        )

        tm.that(report.total_internal_import_violations, gt=0)
        rendered = FlextInfraNamespaceEnforcer.render_text(report)
        tm.that(rendered, has="Internal import violations:")

    def test_manual_protocol_detector_sanctions_private_protocols_directory(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Allow protocols declared in the private protocols directory."""
        violations = FlextInfraManualProtocolDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "_protocols" / "base.py",
                "from __future__ import annotations\n"
                "from typing import Protocol\n\n"
                "class BaseContract(Protocol):\n"
                "    def run(self) -> str: ...\n",
                rope_project,
            )
        )

        tm.that(violations, empty=True)

    def test_manual_protocol_detector_sanctions_canonical_protocols_file(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Allow protocols declared in the canonical protocols module."""
        violations = FlextInfraManualProtocolDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "protocols.py",
                "from __future__ import annotations\n"
                "from typing import Protocol\n\n"
                "class BaseContract(Protocol):\n"
                "    def run(self) -> str: ...\n",
                rope_project,
            )
        )

        tm.that(violations, empty=True)

    def test_manual_protocol_detector_flags_protocol_in_service_module(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Flag a protocol declared in a service module."""
        violations = FlextInfraManualProtocolDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "service.py",
                "from __future__ import annotations\n"
                "from typing import Protocol\n\n"
                "class ServiceContract(Protocol):\n"
                "    def run(self) -> str: ...\n",
                rope_project,
            )
        )

        tm.that(len(violations), eq=1)
        tm.that(violations[0].name, eq="ServiceContract")

    def test_namespace_enforcer_exempts_same_package_facade_assembly_imports(
        self, tmp_path: Path
    ) -> None:
        """Allow same-package imports used to assemble a facade."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path, declare=False)
        parts_pkg = pkg / "_parts"
        nested_pkg = pkg / "nested"
        parts_pkg.mkdir(parents=True)
        nested_pkg.mkdir(parents=True)
        _ = (nested_pkg / "__init__.py").write_text("", encoding="utf-8")
        _ = (parts_pkg / "__init__.py").write_text("", encoding="utf-8")
        _ = (parts_pkg / "impl.py").write_text(
            "from __future__ import annotations\n\n"
            "class _PartsMixin:\n"
            "    pass\n\n"
            "class PartsImpl(_PartsMixin):\n"
            "    pass\n",
            encoding="utf-8",
        )
        _ = (pkg / "service.py").write_text(
            "from __future__ import annotations\n"
            "from sample_pkg._parts.impl import PartsImpl, _PartsMixin\n\n"
            "class Service(PartsImpl, _PartsMixin):\n"
            "    pass\n",
            encoding="utf-8",
        )
        _ = (nested_pkg / "_base.py").write_text(
            "from __future__ import annotations\n\nclass _NestedMixin:\n    pass\n",
            encoding="utf-8",
        )
        _ = (nested_pkg / "impl.py").write_text(
            "from __future__ import annotations\n"
            "from ._base import _NestedMixin\n\n"
            "class NestedService(_NestedMixin):\n"
            "    pass\n",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=False
        )

        tm.that(report.total_internal_import_violations, eq=0)

    def test_namespace_enforcer_flags_cross_package_private_import_from_scripts_tree(
        self, tmp_path: Path
    ) -> None:
        """Flag cross-package private imports originating in a scripts tree."""
        workspace, project, pkg = u.Tests.namespace_workspace(
            tmp_path,
            pyproject=(
                "[project]\n"
                "name='sample'\n"
                "[tool.hatch.build.targets.wheel]\n"
                "packages=['src/sample_pkg']\n"
            ),
        )
        parts_pkg = pkg / "_parts"
        scripts_dir = project / "scripts"
        parts_pkg.mkdir(parents=True)
        scripts_dir.mkdir(parents=True)
        _ = (parts_pkg / "__init__.py").write_text("", encoding="utf-8")
        _ = (parts_pkg / "impl.py").write_text(
            "from __future__ import annotations\n\nclass PartsImpl:\n    pass\n",
            encoding="utf-8",
        )
        _ = (scripts_dir / "helper.py").write_text(
            "from __future__ import annotations\n"
            "from sample_pkg._parts.impl import PartsImpl\n\n"
            "_ = PartsImpl\n",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=False
        )

        tm.that(report.total_internal_import_violations, eq=1)
        violation = report.projects[0].internal_import_violations[0]
        tm.that(violation.file.replace("\\", "/"), has="scripts/helper.py")

    def test_namespace_enforcer_allows_pytest_whitebox_project_private_import(
        self, tmp_path: Path
    ) -> None:
        """Allow pytest white-box imports within the same project."""
        workspace, project, pkg = u.Tests.namespace_workspace(
            tmp_path,
            pyproject=(
                "[project]\n"
                "name='sample'\n"
                "[tool.hatch.build.targets.wheel]\n"
                "packages=['src/sample_pkg']\n"
            ),
            declare=False,
        )
        parts_pkg = pkg / "_parts"
        tests_dir = project / "tests"
        parts_pkg.mkdir(parents=True)
        tests_dir.mkdir(parents=True)
        _ = (parts_pkg / "__init__.py").write_text("", encoding="utf-8")
        _ = (parts_pkg / "impl.py").write_text(
            "from __future__ import annotations\n\nclass PartsImpl:\n    pass\n",
            encoding="utf-8",
        )
        _ = (tests_dir / "test_parts.py").write_text(
            "from __future__ import annotations\n"
            "from sample_pkg._parts.impl import PartsImpl\n\n"
            "def test_parts_impl() -> None:\n"
            "    assert PartsImpl() is not None\n",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=False
        )

        tm.that(report.total_internal_import_violations, eq=0)

    def test_namespace_enforce_does_not_expose_in_place_diff(self) -> None:
        """Keep in-place diff outside the namespace-enforce input contract."""
        tm.that(tuple(m.Infra.RefactorNamespaceEnforceInput.model_fields), lacks="diff")

    def test_loose_object_detector_detects_module_logger_assignment(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Detect a loose module logger assignment."""
        violations = FlextInfraLooseObjectDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "target.py",
                "from __future__ import annotations\n"
                "from flext_core import FlextLogger\n\n"
                "logger = u.fetch_logger(__name__)\n\n"
                "class DemoTarget:\n"
                "    pass\n",
                rope_project,
                project_name="sample-proj",
            )
        )

        tm.that(len(violations), eq=1)
        tm.that(violations[0].kind, eq="logger")
        tm.that(violations[0].name, eq="logger")

    def test_loose_object_detector_flags_private_function_as_loose(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Flag a private module function as a loose object."""
        violations = FlextInfraLooseObjectDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "target.py",
                "from __future__ import annotations\n"
                "\n"
                "def _helper() -> None:\n"
                "    return None\n"
                "\n"
                "class DemoTarget:\n"
                "    pass\n",
                rope_project,
                project_name="sample-proj",
            )
        )

        function_violations = [v for v in violations if v.kind == "function"]
        tm.that(len(function_violations), eq=1)
        tm.that(function_violations[0].name, eq="_helper")

    def test_loose_object_detector_enforces_single_class_pattern(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Enforce one public class per canonical module."""
        violations = FlextInfraLooseObjectDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "target.py",
                "from __future__ import annotations\n\nVALUE = 1\n",
                rope_project,
                project_name="sample-proj",
            )
        )

        single_class = [v for v in violations if v.kind == "single_class"]
        tm.that(len(single_class), eq=1)

    def test_loose_object_detector_skips_private_base_module_flext_contract(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Skip the private base-module FLEXT contract exception."""
        violations = FlextInfraLooseObjectDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "_base.py",
                "from __future__ import annotations\n\n"
                "class _DemoTyping:\n"
                "    pass\n\n"
                "class _DemoBase:\n"
                "    pass\n",
                rope_project,
                project_name="sample-proj",
            )
        )

        tm.that([v for v in violations if v.kind == "single_class"], empty=True)

    def test_loose_object_detector_skips_pytest_module_functions(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Skip pytest module functions in test files."""
        violations = FlextInfraLooseObjectDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "tests" / "test_sample.py",
                "from __future__ import annotations\n\n"
                "import pytest\n\n"
                "@pytest.fixture\n"
                "def sample_value() -> int:\n"
                "    return 1\n\n"
                "def test_sample_value(sample_value: int) -> None:\n"
                "    assert sample_value == 1\n",
                rope_project,
                project_name="sample-proj",
            )
        )

        tm.that(violations, empty=True)

    def test_loose_object_detector_skips_typings_module_exception(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Skip the canonical typings-module exception."""
        violations = FlextInfraLooseObjectDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "typings.py",
                "from __future__ import annotations\n"
                "from typing import TypeVar\n"
                "\n"
                "TValue = TypeVar('TValue')\n",
                rope_project,
                project_name="sample-proj",
            )
        )

        tm.that(violations, empty=True)

    def test_loose_object_detector_flags_classvar_outside_constants_class(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Flag a public ClassVar outside a constants class."""
        violations = FlextInfraLooseObjectDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "target.py",
                "from __future__ import annotations\n"
                "from pathlib import Path\n"
                "from typing import ClassVar\n\n"
                "class ServiceConfig:\n"
                "    HOME: ClassVar[Path] = Path('/home')\n"
                "    AI_HUB: ClassVar[Path] = Path('.ai-hub')\n",
                rope_project,
                project_name="sample-proj",
            )
        )

        classvar_violations = [v for v in violations if v.kind == "classvar"]
        tm.that(len(classvar_violations), eq=2)
        tm.that({v.name for v in classvar_violations}, eq={"HOME", "AI_HUB"})
        tm.that(classvar_violations[0].suggestion, has="Constants")

    @pytest.mark.parametrize(
        ("module_parts", "owner_class"),
        [
            (("target.py",), "SampleConstants"),
            (("_constants", "service.py"), "ServiceConfig"),
        ],
        ids=["constants_class", "constants_module"],
    )
    def test_loose_object_detector_skips_classvar_owned_by_constants(
        self,
        tmp_path: Path,
        rope_project: t.Infra.RopeProject,
        module_parts: t.VariadicTuple[str],
        owner_class: str,
    ) -> None:
        """Allow ClassVar in a constants class and in a private constants module."""
        violations = FlextInfraLooseObjectDetector.detect_file(
            u.Tests.detector_context(
                tmp_path.joinpath(*module_parts),
                "from __future__ import annotations\n"
                "from pathlib import Path\n"
                "from typing import ClassVar\n\n"
                f"class {owner_class}:\n"
                "    HOME: ClassVar[Path] = Path.home()\n",
                rope_project,
                project_name="sample-proj",
            )
        )

        tm.that([v for v in violations if v.kind == "classvar"], empty=True)

    def test_loose_object_detector_flags_typing_classvar(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Flag ClassVar imported through the typing module."""
        violations = FlextInfraLooseObjectDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "target.py",
                "from __future__ import annotations\n"
                "import typing\n\n"
                "class ServiceConfig:\n"
                "    HOME: typing.ClassVar[str] = 'home'\n",
                rope_project,
                project_name="sample-proj",
            )
        )

        classvar_violations = [v for v in violations if v.kind == "classvar"]
        tm.that(len(classvar_violations), eq=1)
        tm.that(classvar_violations[0].name, eq="HOME")

    def test_loose_object_detector_skips_private_classvar(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Skip private ClassVar declarations."""
        violations = FlextInfraLooseObjectDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "target.py",
                "from __future__ import annotations\n"
                "from typing import ClassVar\n\n"
                "class ServiceConfig:\n"
                "    _INTERNAL: ClassVar[str] = 'secret'\n",
                rope_project,
                project_name="sample-proj",
            )
        )

        tm.that([v for v in violations if v.kind == "classvar"], empty=True)

    def test_loose_object_detector_skips_init_module_exception(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Skip the package initializer module exception."""
        violations = FlextInfraLooseObjectDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "__init__.py",
                "from __future__ import annotations\n\n_LAZY_IMPORTS = {}\n",
                rope_project,
                project_name="sample-proj",
            )
        )

        tm.that(violations, empty=True)

    def test_loose_object_detector_skips_canonical_class_alias_in_single_class_count(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        """Exclude a canonical class alias from the public-class count."""
        violations = FlextInfraLooseObjectDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "protocols.py",
                "from __future__ import annotations\n"
                "\n"
                "class SampleProtocols:\n"
                "    pass\n"
                "\n"
                "p = SampleProtocols\n",
                rope_project,
                project_name="sample-proj",
            )
        )

        tm.that(violations, empty=True)

    def test_namespace_enforcer_apply_moves_manual_protocol_to_protocols_file(
        self, tmp_path: Path
    ) -> None:
        """Move a manual protocol into the canonical protocols module."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        service_file = pkg / "service.py"
        _ = service_file.write_text(
            "from __future__ import annotations\nfrom typing import Protocol\n\nclass ServiceContract(Protocol):\n    def run(self) -> str:\n        ...\n\nclass ServiceImpl:\n    def run(self) -> str:\n        return 'ok'",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=True
        )

        tm.that(report.total_manual_protocol_violations, eq=0)
        protocols_file = pkg / "protocols.py"
        tm.that(protocols_file.exists(), eq=True)

        protocols_source = protocols_file.read_text(encoding="utf-8")
        tm.that(protocols_source, has="class ServiceContract(Protocol):")
        tm.that(protocols_source, has="from __future__ import annotations")
        tm.that(protocols_source, has="from typing import Protocol")

    def test_namespace_enforcer_apply_keeps_autofixes_when_other_violations_remain(
        self, tmp_path: Path
    ) -> None:
        """Keep applied fixes when unrelated violations remain."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        service_file = pkg / "service.py"
        _ = service_file.write_text(
            "from __future__ import annotations\n"
            "import logging\n"
            "from typing import Protocol\n\n"
            "logger = logging.getLogger(__name__)\n\n"
            "class ServiceContract(Protocol):\n"
            "    def run(self) -> str:\n"
            "        ...\n",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=True
        )

        tm.that(report.has_violations, eq=True)
        tm.that(report.total_manual_protocol_violations, eq=0)
        tm.that(report.total_loose_objects, gt=0)
        tm.that((pkg / "protocols.py").exists(), eq=True)
        tm.that(
            (pkg / "protocols.py").read_text(encoding="utf-8"),
            has="class ServiceContract(Protocol):",
        )
        tm.that(
            service_file.read_text(encoding="utf-8"),
            lacks="class ServiceContract(Protocol):",
        )

    def test_namespace_enforcer_detects_cyclic_imports_in_source_package(
        self, tmp_path: Path
    ) -> None:
        """Detect cyclic imports inside the production source package."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        _ = (pkg / "a.py").write_text(
            "from __future__ import annotations\nfrom sample_pkg.b import value_b\nvalue_a = value_b\n",
            encoding="utf-8",
        )
        _ = (pkg / "b.py").write_text(
            "from __future__ import annotations\nfrom sample_pkg.a import value_a\nvalue_b = value_a\n",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=False
        )

        tm.that(report.total_cyclic_imports, gte=1)

    @pytest.mark.parametrize(
        ("declaration", "violations"),
        [("", 0), ('__all__: list[str] = ["DemoConstants", "c"]\n\n', 1)],
    )
    def test_namespace_enforcer_does_not_infer_alias_from_external_filename(
        self, tmp_path: Path, declaration: str, violations: int
    ) -> None:
        """Only a letter declared in ``__all__`` is owed; never one from a filename."""
        workspace, project, _pkg = u.Tests.namespace_workspace(tmp_path)
        scripts_dir = project / "scripts"
        scripts_dir.mkdir(parents=True)
        _ = (scripts_dir / "constants.py").write_text(
            "from __future__ import annotations\n\n"
            f"{declaration}"
            "class DemoConstants:\n    pass\n",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=False
        )

        tm.that(report.total_runtime_alias_violations, eq=violations)

    def test_namespace_enforcer_respects_tool_flext_namespace_scan_dirs(
        self, tmp_path: Path
    ) -> None:
        """Respect configured namespace scan directories."""
        workspace, project, _pkg = u.Tests.namespace_workspace(
            tmp_path,
            pyproject=(
                "[project]\nname='sample'\n\n[tool.flext.namespace]\nscan_dirs = ['src']\n"
            ),
            declare=False,
        )
        examples_dir = project / "examples"
        examples_dir.mkdir(parents=True)
        _ = (examples_dir / "constants.py").write_text(
            "from __future__ import annotations\n\nclass DemoConstants:\n    pass\n",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=False
        )

        tm.that(report.total_runtime_alias_violations, eq=0)

    def test_namespace_enforcer_skips_dynamic_dirs_by_default(
        self, tmp_path: Path
    ) -> None:
        """Skip dynamic directories when no scan override is declared."""
        workspace, project, _pkg = u.Tests.namespace_workspace(tmp_path, declare=False)
        docs_dir = project / "docs"
        docs_dir.mkdir(parents=True)
        _ = (docs_dir / "contracts.py").write_text(
            "from __future__ import annotations\nfrom typing import Protocol\n\nclass HiddenContract(Protocol):\n    def run(self) -> str:\n        ...\n",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=False
        )

        tm.that(report.total_manual_protocol_violations, eq=0)

    def test_namespace_enforcer_apply_keeps_script_shebang_when_adding_future(
        self, tmp_path: Path
    ) -> None:
        """Preserve a script shebang while adding the future import."""
        workspace, project, _pkg = u.Tests.namespace_workspace(tmp_path)
        scripts_dir = project / "scripts"
        scripts_dir.mkdir(parents=True)
        script_file = scripts_dir / "run.py"
        _ = script_file.write_text(
            "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\nu.Cli.print('ok')\n",
            encoding="utf-8",
        )

        _ = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(apply=True)

        rewritten_lines = script_file.read_text(encoding="utf-8").splitlines()
        tm.that(rewritten_lines[0], eq="#!/usr/bin/env python3")
        tm.that(rewritten_lines[1], eq="# -*- coding: utf-8 -*-")
        tm.that(rewritten_lines, has="from __future__ import annotations")

    def test_namespace_enforcer_apply_inserts_future_after_single_line_module_docstring(
        self, tmp_path: Path
    ) -> None:
        """Insert the future import after a one-line module docstring."""
        workspace, project, _pkg = u.Tests.namespace_workspace(tmp_path)
        scripts_dir = project / "scripts"
        scripts_dir.mkdir(parents=True)
        target_file = scripts_dir / "base_improved.py"
        _ = target_file.write_text(
            '"""Improved test base with high automation and real functionality."""\n'
            "from pathlib import Path\n"
            "\n"
            "class DemoMigrationTestBase:\n"
            '    """Highly automated test base with real functionality patterns."""\n'
            "    temp_dir: Path\n",
            encoding="utf-8",
        )

        _ = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(apply=True)

        rewritten_lines = target_file.read_text(encoding="utf-8").splitlines()
        tm.that(rewritten_lines[0].startswith('"""Improved test base'), eq=True)
        future_index = rewritten_lines.index("from __future__ import annotations")
        import_index = rewritten_lines.index("from pathlib import Path")
        tm.that(future_index > 0, eq=True)
        tm.that(future_index < import_index, eq=True)

    def test_namespace_enforcer_does_not_rewrite_indented_import_aliases(
        self, tmp_path: Path
    ) -> None:
        """Leave indented import aliases unchanged."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path, declare=False)
        service_file = pkg / "service.py"
        _ = service_file.write_text(
            "from __future__ import annotations\n\n"
            "def runner() -> None:\n"
            "    from flext_core import System\n"
            "    _ = System\n",
            encoding="utf-8",
        )

        _ = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(apply=True)

        service_source = service_file.read_text(encoding="utf-8")
        tm.that(service_source, has="    from flext_core import System")

    def test_namespace_enforcer_does_not_rewrite_multiline_import_alias_blocks(
        self, tmp_path: Path
    ) -> None:
        """Leave multiline import alias blocks unchanged."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path, declare=False)
        module_file = pkg / "constants.py"
        _ = module_file.write_text(
            "from __future__ import annotations\n"
            "from flext_infra import (\n"
            "    FlextInfraConstantsCore,\n"
            "    FlextInfraConstantsSharedInfra,\n"
            ")\n"
            "\n"
            "class DemoConstants:\n"
            "    CORE = FlextInfraConstantsCore\n"
            "    SHARED = FlextInfraConstantsSharedInfra\n",
            encoding="utf-8",
        )

        _ = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(apply=True)

        module_source = module_file.read_text(encoding="utf-8")
        tm.that(module_source, has="from flext_infra import (")
        tm.that(module_source, has="FlextInfraConstantsCore")
        tm.that(module_source, has="FlextInfraConstantsSharedInfra")
        tm.that(module_source, has="CORE = FlextInfraConstantsCore")
        tm.that(module_source, has="SHARED = FlextInfraConstantsSharedInfra")
