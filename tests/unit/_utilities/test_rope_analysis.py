"""Tests for Rope semantic analysis helpers."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import u
from flext_infra.detectors.facade_scanner import FlextInfraScanner
from tests import u as test_u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRopeAnalysis:
    """Behavior contract for Rope-backed semantic analysis."""

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
        self, tmp_path: Path, statement: str, suffix: str
    ) -> None:
        """Bare dots and renamed symbols retain their actual package provenance."""
        project, package = test_u.Tests.demo_project(tmp_path)
        nested = package / "inner" / "leaf"
        nested.mkdir(parents=True)
        for directory in (package, nested.parent, nested):
            (directory / "__init__.py").write_text(
                "class Owner:\n    pass\n", encoding="utf-8"
            )
        source = nested / "consumer.py"
        source.write_text(
            statement + "\nimport os.path as path_alias\nfrom pathlib import Path\n",
            encoding="utf-8",
        )
        with u.Infra.open_project(project) as rope_project:
            resource = tm.not_none(u.Infra.fetch_python_resource(rope_project, source))
            imports = u.Infra.get_declared_module_imports(rope_project, resource)
        tm.that(imports["Local"], eq=package.name + suffix)
        tm.that(imports["path_alias"], eq="os.path")
        tm.that(imports["Path"], eq="pathlib.Path")

    def test_declared_imports_reject_relative_level_beyond_package(
        self, tmp_path: Path
    ) -> None:
        """An invalid relative import is not converted into an absolute import."""
        project, package = test_u.Tests.demo_project(tmp_path)
        source = package / "consumer.py"
        source.write_text("from .. import Owner\n", encoding="utf-8")
        with u.Infra.open_project(project) as rope_project:
            resource = tm.not_none(u.Infra.fetch_python_resource(rope_project, source))
            with pytest.raises(ImportError, match="beyond top-level package"):
                u.Infra.get_declared_module_imports(rope_project, resource)

    def test_ast_boundary_validates_before_traversal(self) -> None:
        """Accept actual ASTs and reject unrelated external runtime objects."""
        source_tree = ast.parse("value = 1")
        tree = u.Infra.ensure_ast_node(source_tree)
        tm.that(u.Infra.node_kind(tree), eq="Module")
        nodes = u.Infra.walk_ast_nodes(tree)
        tm.that(len(nodes), eq=len(list(ast.walk(source_tree))))
        parents = u.Infra.ast_parent_map(tree)
        child = u.Infra.ensure_ast_node(source_tree.body[0])
        tm.that(u.Infra.is_module_level_node(child, parents), eq=True)
        # The rejection names the offending runtime type; its prose is not a contract.
        with pytest.raises(TypeError, match=r"\bobject\b"):
            u.Infra.ensure_ast_node(object())

    def test_facade_scanner_reads_facade_with_imported_superclass(
        self, tmp_path: Path
    ) -> None:
        project, package_dir = test_u.Tests.demo_project(tmp_path)
        _ = (package_dir / "constants.py").write_text(
            "from __future__ import annotations\n"
            "from flext_cli import FlextCliConstants\n\n"
            "class DemoProjectConstants(FlextCliConstants):\n"
            "    class Demo:\n"
            "        VALUE = 'ok'\n\n"
            "c = DemoProjectConstants\n"
            "__all__ = ['DemoProjectConstants', 'c']\n",
            encoding="utf-8",
        )

        with u.Infra.open_project(project) as rope_project:
            statuses = FlextInfraScanner.scan_project(
                project_root=project, rope_project=rope_project
            )

        constants_status = next(status for status in statuses if status.family == "c")
        tm.that(constants_status.exists, eq=True)
        tm.that(constants_status.class_name, eq="DemoProjectConstants")
        model_context = u.Infra.contextual_runtime_alias_sources(
            project_root=project, file_path=package_dir / "_models" / "brand.py"
        )
        settings_context = u.Infra.contextual_runtime_alias_sources(
            project_root=project, file_path=package_dir / "settings.py"
        )
        tm.that(model_context["m"], eq=frozenset({"flext_cli", "flext_core"}))
        tm.that(settings_context["m"], eq=frozenset({"flext_cli", "flext_core"}))

    def test_contextual_runtime_sources_resolve_parent_facade_alias_base(
        self, tmp_path: Path
    ) -> None:
        project, package_dir = test_u.Tests.demo_project(tmp_path)
        _ = (package_dir / "constants.py").write_text(
            "from __future__ import annotations\n"
            "from flext_cli import c\n\n"
            "class DemoProjectConstants(c):\n"
            "    class Demo:\n"
            "        VALUE = 'ok'\n\n"
            "c = DemoProjectConstants\n"
            "__all__ = ['DemoProjectConstants', 'c']\n",
            encoding="utf-8",
        )

        parent_packages = u.Infra.resolve_parent_constants_flext(
            package_dir, return_module=True
        )
        model_context = u.Infra.contextual_runtime_alias_sources(
            project_root=project, file_path=package_dir / "_utilities" / "brand.py"
        )
        base_context = u.Infra.contextual_runtime_alias_sources(
            project_root=project, file_path=package_dir / "base.py"
        )

        tm.that(parent_packages, contains="flext_cli")
        tm.that(model_context["u"], eq=frozenset({"flext_cli", "flext_core"}))
        tm.that(base_context["s"], eq=frozenset({"flext_cli", "flext_core"}))

    def test_contextual_runtime_sources_resolve_transitive_parent_facades(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        _ = (workspace / ".gitmodules").write_text(
            '[submodule "demo-grandparent"]\n'
            "\tpath = demo-grandparent\n"
            "\turl = https://example.invalid/demo-grandparent.git\n"
            '[submodule "demo-parent"]\n'
            "\tpath = demo-parent\n"
            "\turl = https://example.invalid/demo-parent.git\n"
            '[submodule "demo-child"]\n'
            "\tpath = demo-child\n"
            "\turl = https://example.invalid/demo-child.git\n",
            encoding="utf-8",
        )
        grandparent_pkg = workspace / "demo-grandparent" / "src" / "demo_grandparent"
        parent_pkg = workspace / "demo-parent" / "src" / "demo_parent"
        child_project = workspace / "demo-child"
        child_pkg = child_project / "src" / "demo_child"
        for project_name, package_dir in (
            ("demo-grandparent", grandparent_pkg),
            ("demo-parent", parent_pkg),
            ("demo-child", child_pkg),
        ):
            package_dir.mkdir(parents=True)
            project = workspace / project_name
            _ = (project / "pyproject.toml").write_text(
                f"[project]\nname='{project_name}'\n", encoding="utf-8"
            )
            _ = (project / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
            _ = (package_dir / "__init__.py").write_text(
                "from .constants import c\n", encoding="utf-8"
            )
        _ = (grandparent_pkg / "constants.py").write_text(
            "from __future__ import annotations\n"
            "from flext_core import c\n\n"
            "class DemoGrandparentConstants(c):\n"
            "    pass\n\n"
            "c = DemoGrandparentConstants\n",
            encoding="utf-8",
        )
        _ = (parent_pkg / "constants.py").write_text(
            "from __future__ import annotations\n"
            "from demo_grandparent import c\n\n"
            "class DemoParentConstants(c):\n"
            "    pass\n\n"
            "c = DemoParentConstants\n",
            encoding="utf-8",
        )
        _ = (child_pkg / "constants.py").write_text(
            "from __future__ import annotations\n"
            "from demo_parent import c\n\n"
            "class DemoChildConstants(c):\n"
            "    pass\n\n"
            "c = DemoChildConstants\n",
            encoding="utf-8",
        )

        base_context = u.Infra.contextual_runtime_alias_sources(
            project_root=child_project, file_path=child_pkg / "base.py"
        )

        tm.that(base_context["s"], contains="demo_parent")
        tm.that(base_context["s"], contains="demo_grandparent")
