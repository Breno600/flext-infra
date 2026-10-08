"""Tests for Rope semantic analysis helpers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRopeAnalysis:
    """Behavior contract for Rope-backed semantic analysis."""

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
