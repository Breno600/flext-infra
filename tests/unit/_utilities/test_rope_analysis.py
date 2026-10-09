"""Tests for Rope semantic analysis helpers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from tests import c, t, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRopeAnalysis:
    """Behavior contract for Rope-backed semantic analysis."""

    @staticmethod
    @pytest.mark.parametrize(
        ("declarations", "base", "body", "expected"),
        [
            ("", "Exception", "pass", ()),
            ("", "object", "pass", ()),
            ("class Parent:\n    pass\n", "Parent", "pass", ()),
            (
                "class Parent(Exception):\n    class Shared:\n        pass\n",
                "Parent",
                "pass",
                ("Shared",),
            ),
            (
                (
                    "class Parent(object):\n    class Shared:\n        pass\n"
                    "class Middle(Parent):\n    pass\n"
                ),
                "Middle",
                "pass",
                ("Shared",),
            ),
            (
                "class Parent:\n    class Shared:\n        pass\n",
                "Parent",
                "class Shared:\n        pass",
                (),
            ),
            (
                (
                    "class Parent:\n    class Shared:\n        pass\n"
                    "class Left(Parent):\n    pass\n"
                    "class Right(Parent):\n    pass\n"
                ),
                "Left, Right",
                "pass",
                ("Shared",),
            ),
            (
                "from .provider import Parent\n",
                "Parent, Exception",
                "pass",
                ("Shared",),
            ),
        ],
    )
    def test_inherited_namespaces_require_source_scope_and_binding_identity(
        tmp_path: Path,
        declarations: str,
        base: str,
        body: str,
        expected: t.StrSequence,
    ) -> None:
        """Builtin bases have no source scopes; actual nested bindings survive."""
        project, package = u.Tests.demo_project(tmp_path)
        (package / "provider.py").write_text(
            "class Parent(object):\n    class Shared:\n        pass\n",
            encoding="utf-8",
        )
        source = package / "consumer.py"
        content = declarations + f"class Consumer({base}):\n    " + body + "\n"
        source.write_text(content, encoding="utf-8")
        with u.Infra.open_project(project) as rope_project:
            resource = tm.not_none(u.Infra.fetch_python_resource(rope_project, source))
            namespaces = u.Infra.inherited_facade_namespaces(
                rope_project,
                resource,
                class_name="Consumer",
            )
            tm.that(namespaces, eq=expected)
            tm.that(
                u.Infra.inherited_facade_namespaces(
                    rope_project,
                    resource,
                    class_name="Consumer",
                ),
                eq=namespaces,
            )
        tm.that(source.read_text(encoding="utf-8"), eq=content)

    @staticmethod
    def test_inherited_namespace_cycle_is_not_a_builtin_boundary(
        tmp_path: Path,
    ) -> None:
        """A source-defined cycle still fails instead of returning partial names."""
        project, package = u.Tests.demo_project(tmp_path)
        source = package / "consumer.py"
        source.write_text(
            "class Parent(Consumer):\n    pass\nclass Consumer(Parent):\n    pass\n",
            encoding="utf-8",
        )
        with u.Infra.open_project(project) as rope_project:
            resource = tm.not_none(u.Infra.fetch_python_resource(rope_project, source))
            with pytest.raises(ValueError, match="cyclic facade namespace inheritance"):
                u.Infra.inherited_facade_namespaces(
                    rope_project,
                    resource,
                    class_name="Consumer",
                )

    @staticmethod
    def test_namespace_policy_retains_inherited_public_payload(tmp_path: Path) -> None:
        """The real policy consumer publishes inherited names without changing MRO."""
        project, package = u.Tests.demo_project(tmp_path)
        alias = next(iter(sorted(c.Infra.ALIAS_NAMES)))
        source = package / "api.py"
        content = (
            "class Parent(Exception):\n    class Shared:\n        pass\n"
            "class Consumer(Parent):\n    pass\n"
            f"{alias} = Consumer\n__all__ = ['Consumer', '{alias}']\n"
        )
        source.write_text(content, encoding="utf-8")
        with u.Infra.open_project(project) as rope_project:
            policy = u.Infra.policy(source, rope_project=rope_project)
        tm.that(policy.inherited_namespaces, eq=("Shared",))
        tm.that(policy.expected_alias, eq=alias)
        tm.that(policy.model_dump()["inherited_namespaces"], eq=("Shared",))
        tm.that(source.read_text(encoding="utf-8"), eq=content)

    @staticmethod
    def test_installed_pydantic_root_and_alias_are_not_reexport_cycles(
        tmp_path: Path,
    ) -> None:
        """Ruff consumes qualified bases; both lexical aliases retain one provider.

        ``runtime-evaluated-base-classes`` uses import-qualified names, not
        module-local alias spellings. A subclass used as another base must
        retain its own qualified declaration as well as the provider root.
        """
        project, package = u.Tests.demo_project(tmp_path)
        source = package / "consumer.py"
        content = (
            "from pydantic import BaseModel\n"
            "from pydantic import BaseModel as Parent\n"
            "class Direct(BaseModel):\n    pass\n"
            "class Aliased(Parent):\n    pass\n"
            "class Local(Direct):\n    pass\n"
        )
        source.write_text(content, encoding="utf-8")
        required = ("pydantic.BaseModel",)

        discovered = u.Infra.runtime_evaluated_base_classes(
            project,
            {source: content},
            required,
        )

        tm.that(discovered, has=required[0])
        module_name = u.Infra.module_name_for_file(source, project_root=project)
        tm.that(discovered, has=f"{module_name}.Direct")
        with u.Infra.open_project(project) as rope_project:
            resource = tm.not_none(u.Infra.fetch_python_resource(rope_project, source))
            imports = u.Infra.resolve_declared_module_imports(rope_project, resource)
            tm.that(imports["BaseModel"], eq=required[0])
            tm.that(imports["Parent"], eq=required[0])
            module = u.Infra.resolve_pymodule(rope_project, resource)
            direct = module.get_attribute("BaseModel").get_object()
            renamed = module.get_attribute("Parent").get_object()
            tm.that(renamed is direct, eq=True)

    @staticmethod
    @pytest.mark.parametrize(
        ("declaration", "expected"),
        [
            ("value = object", "object"),
            ("value = Exception", "Exception"),
            ("class Parent:\n    pass\nvalue = Parent", "Parent"),
            ("class Parent:\n    pass\nvalue = Parent()", "Parent"),
            ("from .provider import Parent\nvalue = Parent", "Parent"),
        ],
    )
    def test_superclass_name_uses_the_sdk_class_or_instance_type(
        tmp_path: Path,
        declaration: str,
        expected: str,
    ) -> None:
        """Real builtin, local, imported and inferred classes use public SDK APIs."""
        project, package = u.Tests.demo_project(tmp_path)
        (package / "provider.py").write_text(
            "class Parent:\n    pass\n",
            encoding="utf-8",
        )
        source = package / "consumer.py"
        source.write_text(declaration + "\n", encoding="utf-8")
        with u.Infra.open_project(project) as rope_project:
            resource = tm.not_none(u.Infra.fetch_python_resource(rope_project, source))
            module = u.Infra.resolve_pymodule(rope_project, resource)
            value = module.get_attribute("value").get_object()
            tm.that(u.Infra.superclass_name(value), eq=expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("declaration", "message"),
        [
            ("def value():\n    pass\n", "not a class or inferred instance"),
            ("value = missing\n", "cyclic Rope superclass type"),
        ],
    )
    def test_superclass_name_refuses_nonclass_or_unresolved_type(
        tmp_path: Path,
        declaration: str,
        message: str,
    ) -> None:
        """Unknown types and functions cannot masquerade as named superclasses."""
        project, package = u.Tests.demo_project(tmp_path)
        source = package / "consumer.py"
        source.write_text(declaration, encoding="utf-8")
        with u.Infra.open_project(project) as rope_project:
            resource = tm.not_none(u.Infra.fetch_python_resource(rope_project, source))
            module = u.Infra.resolve_pymodule(rope_project, resource)
            value = module.get_attribute("value").get_object()
            with pytest.raises((TypeError, ValueError), match=message):
                u.Infra.superclass_name(value)

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

        with pytest.raises(
            ValueError,
            match=rf"Cyclic .*: {provider.name}\.first\.Base",
        ):
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
        project, package = test_u.Tests.demo_project(tmp_path)
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
        project, package = test_u.Tests.demo_project(tmp_path)
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
