"""Behavior contract for deferred-self-reference and recursive-model detection.

Both defects share one root cause: a nested model that cannot name what it
depends on while its own class body executes. The canonical repair is
diamond-FLEXT composition, so the detector must fire on the deferral and stay
silent once the model is composed through inherited namespaces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import m, u
from flext_infra.detectors.deferred_self_reference_detector import (
    FlextInfraDeferredSelfReferenceDetector,
)
from tests import t

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDeferredSelfReferenceDetector:
    """Behavior contract for deferred-self-reference detection."""

    _DEFERRED = "DEFERRED_SELF_REFERENCE"
    _RECURSIVE = "RECURSIVE_MODEL"

    @staticmethod
    def _codes(tmp_path: Path, source: str) -> t.VariadicTuple[str]:
        project = tmp_path / "demo-project"
        package_dir = project / "src" / "demo_project"
        package_dir.mkdir(parents=True)
        _ = (project / "pyproject.toml").write_text(
            "[project]\nname='demo-project'\n", encoding="utf-8"
        )
        _ = (package_dir / "__init__.py").write_text("", encoding="utf-8")
        module = package_dir / "subject.py"
        _ = module.write_text(source, encoding="utf-8")
        with u.Infra.open_project(project) as rope_project:
            issues = FlextInfraDeferredSelfReferenceDetector.detect_file(
                m.Infra.DetectorContext(
                    file_path=module, project_root=project, rope_project=rope_project
                )
            )
        return tuple(issue.code for issue in issues)

    def test_lambda_factory_reaching_the_enclosing_class_is_reported(
        self, tmp_path: Path
    ) -> None:
        """A default_factory deferring the outer class name is the core defect."""
        source = (
            "class Outer:\n"
            "    class Leaf:\n"
            "        pass\n"
            "    class Holder:\n"
            "        leaf: Outer.Leaf = Field(default_factory=lambda: Outer.Leaf())\n"
        )
        tm.that(self._codes(tmp_path, source), eq=(self._DEFERRED,))

    def test_diamond_flext_composition_is_accepted(self, tmp_path: Path) -> None:
        """The canonical repair resolves the model eagerly, so it must be clean."""
        source = (
            "class Base:\n"
            "    class Leaf:\n"
            "        pass\n"
            "class Outer(Base):\n"
            "    class Holder:\n"
            "        leaf: Base.Leaf = Field(default_factory=Base.Leaf)\n"
        )
        tm.that(self._codes(tmp_path, source), eq=())

    def test_value_factories_are_not_deferred_references(self, tmp_path: Path) -> None:
        """A lambda producing an immutable default names no enclosing class."""
        source = (
            "class Outer:\n"
            "    class Holder:\n"
            "        mapping: Map = Field(default_factory=lambda: MappingProxyType({}))\n"
            "        missing: object = Field(default_factory=lambda: None)\n"
        )
        tm.that(self._codes(tmp_path, source), eq=())

    def test_self_annotated_field_is_reported_as_recursive(
        self, tmp_path: Path
    ) -> None:
        """A field typed as its own owner cannot be instantiated."""
        source = "class Node:\n    child: Node | None = None\n"
        tm.that(self._codes(tmp_path, source), eq=(self._RECURSIVE,))

    def test_classvar_singleton_slot_is_not_recursive(self, tmp_path: Path) -> None:
        """A ClassVar slot is never instantiated as a field."""
        source = "class Config:\n    _instance: ClassVar[Config | None] = None\n"
        tm.that(self._codes(tmp_path, source), eq=())

    def test_type_adapter_table_is_not_recursive(self, tmp_path: Path) -> None:
        """A TypeAdapter table types a converter, not an instantiated field."""
        source = (
            "class Types:\n"
            "    ADAPTER: m.TypeAdapter[t.SequenceOf[Types.Payload]] = m.TypeAdapter(\n"
            "        t.SequenceOf[Payload]\n"
            "    )\n"
        )
        tm.that(self._codes(tmp_path, source), eq=())

    def test_annotated_local_inside_a_method_is_not_a_field(
        self, tmp_path: Path
    ) -> None:
        """A method body runs after the class is bound, so neither defect applies."""
        source = (
            "class Service:\n"
            "    def run(self) -> object:\n"
            "        resolved: Service.Inner = build()\n"
            "        return resolved\n"
        )
        tm.that(self._codes(tmp_path, source), eq=())

    def test_report_names_the_flext_repair(self, tmp_path: Path) -> None:
        """The finding must tell the author how to fix it, not just that it failed."""
        project = tmp_path / "demo-project"
        package_dir = project / "src" / "demo_project"
        package_dir.mkdir(parents=True)
        _ = (project / "pyproject.toml").write_text(
            "[project]\nname='demo-project'\n", encoding="utf-8"
        )
        _ = (package_dir / "__init__.py").write_text("", encoding="utf-8")
        module = package_dir / "subject.py"
        _ = module.write_text(
            "class Outer:\n"
            "    class Leaf:\n"
            "        pass\n"
            "    class Holder:\n"
            "        leaf: Outer.Leaf = Field(default_factory=lambda: Outer.Leaf())\n",
            encoding="utf-8",
        )
        with u.Infra.open_project(project) as rope_project:
            issues = FlextInfraDeferredSelfReferenceDetector.detect_file(
                m.Infra.DetectorContext(
                    file_path=module, project_root=project, rope_project=rope_project
                )
            )
        tm.that(len(issues), eq=1)
        tm.that(issues[0].message, has="FLEXT")
        tm.that(issues[0].line, eq=5)

    def test_public_normalizer_qualifies_sibling_annotations_without_reordering(
        self,
    ) -> None:
        """Sibling annotations use the owner while declaration order stays stable."""
        source = (
            "from __future__ import annotations\n\n"
            "class Models:\n"
            "    class Consumer:\n"
            "        dependency: Dependency\n\n"
            "        def runtime(self) -> object:\n"
            "            return Models.Dependency()\n\n"
            "    class Dependency:\n"
            "        pass\n"
        )
        normalized = u.Infra.normalize_deferred_self_references(source)
        tm.that(
            normalized.index("    class Consumer:"),
            lt=normalized.index("    class Dependency:"),
        )
        tm.that(normalized, has="dependency: Models.Dependency")
        tm.that(normalized, has="return Models.Dependency()")

    def test_public_normalizer_ignores_a_nested_models_own_return_type(self) -> None:
        """A method returning its enclosing nested model is not a graph edge."""
        source = (
            "class Models:\n"
            "    class Target:\n"
            "        @classmethod\n"
            "        def create(cls) -> Target:\n"
            "            return cls()\n\n"
            "    class Other:\n"
            "        pass\n"
        )
        tm.that(u.Infra.normalize_deferred_self_references(source), eq=source)

    def test_public_normalizer_restores_executable_nested_class_bases(self) -> None:
        """A nested base resolves from the active owner namespace at definition time."""
        source = (
            "class Models:\n"
            "    class Base:\n"
            "        pass\n\n"
            "    class Child(Models.Base):\n"
            "        pass\n"
        )
        normalized = u.Infra.normalize_deferred_self_references(source)
        tm.that(normalized, has="class Child(Base):")
        tm.that("class Child(Models.Base):" not in normalized, eq=True)

    def test_public_normalizer_rejects_ambiguous_owners_and_model_rebuild(self) -> None:
        """Unknown owner members and runtime schema repair fail loud."""
        ambiguous = (
            "class Models:\n"
            "    class First:\n"
            "        value: Models.Missing\n\n"
            "    class Second:\n"
            "        pass\n"
        )
        rebuild = "class Model:\n    pass\n\nModel.model_rebuild()\n"
        with pytest.raises(ValueError, match="ambiguous self-qualified annotation"):
            u.Infra.normalize_deferred_self_references(ambiguous)
        with pytest.raises(ValueError, match="model_rebuild is prohibited"):
            u.Infra.normalize_deferred_self_references(rebuild)

    def test_public_normalizer_preserves_inherited_owner_annotations(self) -> None:
        """An inherited public type need not be redeclared in the local facade."""
        source = (
            "from __future__ import annotations\n\n"
            "class Base:\n"
            "    class Target:\n"
            "        pass\n\n"
            "class Models(Base):\n"
            "    class Consumer:\n"
            "        value: Models.Target\n"
        )
        tm.that(u.Infra.normalize_deferred_self_references(source), eq=source)

    @pytest.mark.parametrize(
        "declaration",
        [
            '_Kind = Literal["one", "two"]',
            '_Kind: TypeAlias = Literal["one", "two"]',
            'type _Kind = Literal["one", "two"]',
        ],
    )
    def test_public_normalizer_accepts_declared_owner_aliases(
        self, declaration: str
    ) -> None:
        """An existing qualified alias must not block unrelated sibling repairs."""
        source = (
            "from __future__ import annotations\n"
            "from typing import Annotated, Literal, TypeAlias\n\n"
            "class Models:\n"
            f"    {declaration}\n"
            "    class Dependency:\n"
            "        pass\n"
            "    class Consumer:\n"
            "        kind: Annotated[Models._Kind, 'category']\n"
            "        dependency: Dependency\n"
        )
        normalized = u.Infra.normalize_deferred_self_references(source)

        tm.that(
            normalized,
            eq=source.replace(
                "dependency: Dependency", "dependency: Models.Dependency"
            ),
        )
        tm.that(u.Infra.normalize_deferred_self_references(normalized), eq=normalized)

    def test_public_normalizer_does_not_qualify_bare_assignment_bindings(self) -> None:
        """Recognizing a member does not turn every class attribute into a type."""
        source = (
            "from __future__ import annotations\n\n"
            "class Models:\n"
            "    int = 1\n"
            "    class Consumer:\n"
            "        value: int\n"
        )

        tm.that(u.Infra.normalize_deferred_self_references(source), eq=source)

    @pytest.mark.parametrize(
        "declaration", ["_Kind: object", "class Other:\n        _Kind = str"]
    )
    def test_public_normalizer_rejects_unbound_or_foreign_owner_members(
        self, declaration: str
    ) -> None:
        """An annotation-only slot or another class's member is not an owner binding."""
        source = (
            "from __future__ import annotations\n\n"
            "class Models:\n"
            f"    {declaration}\n"
            "    class Consumer:\n"
            "        kind: Models._Kind\n"
        )

        with pytest.raises(ValueError, match="ambiguous self-qualified annotation"):
            u.Infra.normalize_deferred_self_references(source)
