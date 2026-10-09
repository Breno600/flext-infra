"""Tests for Rope semantic analysis helpers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRopeAnalysis:
    """Behavior contract for Rope-backed semantic analysis."""

    @staticmethod
    def test_installed_pydantic_root_and_alias_are_not_reexport_cycles(
        tmp_path: Path,
    ) -> None:
        """A provider handoff is not an edge back to the same provider."""
        project, package = u.Tests.demo_project(tmp_path)
        source = package / "consumer.py"
        content = (
            "from pydantic import BaseModel\n"
            "from pydantic import BaseModel as Parent\n"
            "class Direct(BaseModel):\n    pass\n"
            "class Aliased(Parent):\n    pass\n"
        )
        source.write_text(content, encoding="utf-8")
        required = ("pydantic.BaseModel",)

        discovered = u.Infra.runtime_evaluated_base_classes(
            project,
            {source: content},
            required,
        )

        tm.that(discovered, has=required[0])
        tm.that(discovered, has="BaseModel")
        tm.that(discovered, has="Parent")

    @staticmethod
    def test_external_provider_reexport_cycle_remains_an_error(
        tmp_path: Path,
    ) -> None:
        """Real provider edges retain cycle detection without importing the consumer."""
        project, package = u.Tests.demo_project(tmp_path)
        provider = package.parent / "external_provider"
        provider.mkdir()
        (provider / "__init__.py").write_text("", encoding="utf-8")
        (provider / "first.py").write_text(
            "from .second import Base\n",
            encoding="utf-8",
        )
        (provider / "second.py").write_text(
            "from .first import Base\n",
            encoding="utf-8",
        )
        source = package / "consumer.py"
        content = (
            "from external_provider.first import Base\n"
            "class Consumer(Base):\n"
            "    pass\n"
        )
        source.write_text(content, encoding="utf-8")

        with pytest.raises(ValueError, match="Cyclic provider reexport"):
            u.Infra.runtime_evaluated_base_classes(project, {source: content}, ())

    @staticmethod
    @pytest.mark.slow
    def test_external_provider_chain_obeys_declared_depth_budget(
        tmp_path: Path,
    ) -> None:
        """A handoff cannot remove the typed owner's reference-depth bound."""
        project, package = u.Tests.demo_project(tmp_path)
        provider = package.parent / "external_provider"
        provider.mkdir()
        (provider / "__init__.py").write_text("", encoding="utf-8")
        count = c.Infra.ROPE_WALK_DEPTH_BUDGET + 2
        for index in range(count):
            content = (
                f"from .layer_{index + 1} import Base\n"
                if index + 1 < count
                else "class Base:\n    pass\n"
            )
            (provider / f"layer_{index}.py").write_text(content, encoding="utf-8")
        source = package / "consumer.py"
        content = (
            "from external_provider.layer_0 import Base\n"
            "class Consumer(Base):\n"
            "    pass\n"
        )
        source.write_text(content, encoding="utf-8")

        with pytest.raises(ValueError, match=r"Unresolved external base.*at depth"):
            u.Infra.runtime_evaluated_base_classes(project, {source: content}, ())

    @staticmethod
    @pytest.mark.parametrize(
        ("statement", "suffix"),
        [
            ("from . import Owner as Local", ".inner.leaf.Owner"),
            ("from .. import Owner as Local", ".inner.Owner"),
            ("from ... import Owner as Local", ".Owner"),
            ("from ..leaf import Owner as Local", ".inner.leaf.Owner"),
        ],
    )
    def test_declared_imports_preserve_relative_levels(
        tmp_path: Path,
        statement: str,
        suffix: str,
    ) -> None:
        """Bare dots and renamed symbols retain their actual package provenance."""
        project, package = u.Tests.demo_project(tmp_path)
        nested = package / "inner" / "leaf"
        nested.mkdir(parents=True)
        for directory in (package, nested.parent, nested):
            (directory / "__init__.py").write_text(
                "class Owner:\n    pass\n",
                encoding="utf-8",
            )
        source = nested / "consumer.py"
        source.write_text(
            statement + "\nimport os.path as path_alias\nfrom pathlib import Path\n",
            encoding="utf-8",
        )
        with u.Infra.open_project(project) as rope_project:
            resource = tm.not_none(u.Infra.fetch_python_resource(rope_project, source))
            imports = u.Infra.resolve_declared_module_imports(rope_project, resource)
        tm.that(imports["Local"], eq=package.name + suffix)
        tm.that(imports["path_alias"], eq="os.path")
        tm.that(imports["Path"], eq="pathlib.Path")

    @staticmethod
    def test_facade_namespaces_skip_builtin_bases(tmp_path: Path) -> None:
        """A builtin base has no source scope and contributes no namespace."""
        project, package = u.Tests.demo_project(tmp_path)
        source = package / "errors.py"
        source.write_text(
            "class Parent:\n"
            "    class Shared:\n        pass\n"
            "class Errors(Parent, Exception):\n    pass\n",
            encoding="utf-8",
        )
        with u.Infra.open_project(project) as rope_project:
            resource = tm.not_none(u.Infra.fetch_python_resource(rope_project, source))
            names = u.Infra.inherited_facade_namespaces(
                rope_project,
                resource,
                class_name="Errors",
            )
        tm.that(tuple(names), eq=("Shared",))

    @staticmethod
    def test_declared_imports_reject_relative_level_beyond_package(
        tmp_path: Path,
    ) -> None:
        """An invalid relative import is not converted into an absolute import."""
        project, package = u.Tests.demo_project(tmp_path)
        source = package / "consumer.py"
        source.write_text("from .. import Owner\n", encoding="utf-8")
        with u.Infra.open_project(project) as rope_project:
            resource = tm.not_none(u.Infra.fetch_python_resource(rope_project, source))
            with pytest.raises(ImportError, match="beyond top-level package"):
                u.Infra.resolve_declared_module_imports(rope_project, resource)

    @staticmethod
    def test_ast_boundary_validates_before_traversal() -> None:
        """Accept actual ASTs and reject unrelated external runtime objects."""
        source_tree = ast.parse("value = 1")
        tree = u.Infra.ensure_ast_node(source_tree)
        tm.that(u.Infra.node_kind(tree), eq="Module")
        nodes = u.Infra.walk_ast_nodes(tree)
        tm.that(len(nodes), eq=len(list(ast.walk(source_tree))))
        parents = u.Infra.ast_parent_map(tree)
        child = u.Infra.ensure_ast_node(source_tree.body[0])
        tm.that(u.Infra.module_level_node(child, parents), eq=True)
        # The rejection names the offending runtime type; its prose is not a contract.
        with pytest.raises(TypeError, match=r"\bobject\b"):
            u.Infra.ensure_ast_node(object())

    @staticmethod
    def test_call_headed_assignment_binds_as_non_class(tmp_path: Path) -> None:
        """A call-headed value is a non-class binding, never a base reference.

        Generated package-data modules assign validated payloads
        (``Payload.model_validate_json(resource).section``); the inventory
        records that binding as ``None`` instead of feeding the call to the
        class-reference resolver.
        """
        project, package = u.Tests.demo_project(tmp_path)
        source = package / "data_module.py"
        source.write_text(
            "class Owner:\n"
            "    pass\n"
            "\n"
            "\n"
            "PAYLOAD_SECTION: dict[str, Owner] = Owner.factory(\n"
            "    resource_text('values.json'),\n"
            ").items\n",
            encoding="utf-8",
        )
        bases = u.Infra.runtime_evaluated_base_classes(
            project,
            {source: source.read_text(encoding="utf-8")},
            (),
        )
        tm.that(bases, eq=())

    @staticmethod
    def test_base_through_external_facade_instance_resolves_to_its_class(
        tmp_path: Path,
    ) -> None:
        """A base read through a provider's module-level facade instance resolves.

        Consumer facades publish their bases as nested classes of the facade
        type and expose one module-level instance (``meltano.Tap`` on
        ``meltano: FlextMeltano``). Attribute access on that instance reaches
        the class attribute through the instance's type, so the planner walks
        the type's MRO instead of rejecting the instance as a non-class base.
        """
        (tmp_path / "src").mkdir()
        (tmp_path / "flext-core").mkdir()
        _, provider = u.Tests.demo_project(tmp_path, name="provider-project")
        (provider / "bases.py").write_text(
            "class ProviderBases:\n    class Tap:\n        pass\n",
            encoding="utf-8",
        )
        (provider / "api.py").write_text(
            "from provider_project.bases import ProviderBases\n"
            "\n"
            "\n"
            "class ProviderFacade(ProviderBases):\n"
            "    pass\n"
            "\n"
            "\n"
            "facade: ProviderFacade = ProviderFacade()\n",
            encoding="utf-8",
        )
        (provider / "__init__.py").write_text(
            "from provider_project.api import ProviderFacade, facade\n",
            encoding="utf-8",
        )
        project, package = u.Tests.demo_project(tmp_path, name="consumer-project")
        consumer = package / "api.py"
        consumer.write_text(
            "from provider_project import facade\n"
            "\n"
            "\n"
            "class Consumer(facade.Tap):\n"
            "    pass\n",
            encoding="utf-8",
        )
        bases = u.Infra.runtime_evaluated_base_classes(
            project,
            {consumer: consumer.read_text(encoding="utf-8")},
            ("provider_project.bases.ProviderBases.Tap",),
        )
        tm.that(bases, has="provider_project.facade.Tap")

    @staticmethod
    def test_missing_planned_class_binding_fails_at_the_required_base(
        tmp_path: Path,
    ) -> None:
        """An explicit missing base fails instead of silently losing its lineage."""
        project, package = u.Tests.demo_project(tmp_path)
        helper = package / "data_module.py"
        helper.write_text(
            "def build() -> int:\n    return 0\n",
            encoding="utf-8",
        )
        consumer = package / "consumer.py"
        consumer.write_text(
            "from . import data_module\n"
            "\n"
            "\n"
            "class Consumer(data_module.Helper):\n"
            "    pass\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Unresolved planned base"):
            u.Infra.runtime_evaluated_base_classes(
                project,
                {
                    source: source.read_text(encoding="utf-8")
                    for source in (helper, consumer)
                },
                (),
            )
