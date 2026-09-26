"""Behavior tests for the rope signature patched-AST handlers."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, cast

from flext_tests import tm
from rope.refactor import patchedast

from flext_infra.workspace.rope import FlextInfraRopeWorkspace
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class _PatchableNode(ast.Name):
    """AST node carrying the fields the patched-AST writer attaches at runtime.

    The fork's ``patch_ast`` sets ``sorted_children`` as a dynamic field, so
    the test declares that contract locally instead of reviving the deleted
    monkeypatch protocols.
    """

    sorted_children: list[ast.expr | str]


class TestsFlextInfraRopeSignaturePatch:
    """Validate signature token walking against annotated call parameters."""

    def test_objects_walk_annotated_call_parameters(self, tmp_path: Path) -> None:
        """Two multiline annotated parameters no longer break the AST walk.

        rope 1.14 skipped annotation tokens and failed loudly once a second
        annotation carried a call (bead flext-4frn5).
        """
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "command.py"
        module_path.write_text(
            (
                "from typing import Annotated\n"
                "\n"
                "\n"
                "def command(\n"
                "    *,\n"
                "    log_level: Annotated[\n"
                '        str, create_option("cli_log_level")\n'
                '    ] = "INFO",\n'
                "    output_format: Annotated[\n"
                '        str, create_option("output_format")\n'
                '    ] = "TABLE",\n'
                ") -> None:\n"
                '    print(f"Command: {log_level}")\n'
            ),
            encoding="utf-8",
        )

        with FlextInfraRopeWorkspace.open_workspace(repository_root) as rope:
            objects = rope.objects(module_path)

        tm.that([item.name for item in objects], has="command")

    def test_objects_walk_full_signature_shapes(self, tmp_path: Path) -> None:
        """Positional-only, vararg, keyword-only and kwargs walk in order."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "shapes.py"
        module_path.write_text(
            (
                "def shapes(\n"
                "    first,\n"
                "    second: int,\n"
                "    /,\n"
                "    third: int = 1,\n"
                "    *rest: int,\n"
                "    flag: bool = True,\n"
                "    tagged: int,\n"
                "    **extra: int,\n"
                ") -> None:\n"
                "    print(first, second, third, rest, flag, tagged, extra)\n"
            ),
            encoding="utf-8",
        )

        with FlextInfraRopeWorkspace.open_workspace(repository_root) as rope:
            objects = rope.objects(module_path)

        tm.that([item.name for item in objects], has="shapes")

    def test_scope_at_walks_pep701_nested_quotes(self, tmp_path: Path) -> None:
        """Rope resolves scope when an f-string expression reuses quote style."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "quoted.py"
        source = (
            "def render(values: dict[str, str]) -> str:\n"
            '    return f"value={values["name"]}"\n'
        )
        module_path.write_text(source, encoding="utf-8")

        with FlextInfraRopeWorkspace.open_workspace(repository_root) as rope:
            pymodule = u.Infra.get_string_module(
                rope.rope_project, source, resource=rope.resource(module_path)
            )
            scope = u.Infra.scope_at(pymodule, source.index("values["))

        # A Rope scope is not a payload value; its observable identity is the
        # enclosing function's scope kind.
        assert scope is not None
        tm.that(scope.get_kind(), eq=c.Infra.RopeScopeKind.FUNCTION)

    def test_rename_writes_pep701_nested_quote_expression(self, tmp_path: Path) -> None:
        """Rope preserves f-string fragments while writing a renamed AST child."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "quoted_rename.py"
        source = (
            "def render(values: dict[str, str]) -> str:\n"
            '    return f"value={values["name"].upper()}"\n'
        )
        expected = (
            "def render(items: dict[str, str]) -> str:\n"
            '    return f"value={items["name"].upper()}"\n'
        )
        module_path.write_text(source, encoding="utf-8")

        with FlextInfraRopeWorkspace.open_workspace(repository_root) as rope:
            resource = rope.resource(module_path)
            if resource is None:
                msg = "Rope did not resolve the PEP 701 regression resource"
                raise AssertionError(msg)
            changes = u.Infra.rename_changes(
                rope.rope_project,
                resource,
                source.index("values["),
                "items",
                resources=(resource,),
            )
            rope.rope_project.do(changes)
            rewritten = resource.read()

        tm.that(rewritten, eq=expected)

    def test_rename_writes_generator_inside_format_spec(self, tmp_path: Path) -> None:
        """Rope patches generator scopes nested in an f-string format spec."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "format_spec.py"
        source = (
            "def render(value: int, widths: list[int]) -> str:\n"
            '    return f"{value:{next(width for width in widths)}}"\n'
        )
        expected = (
            "def render(value: int, sizes: list[int]) -> str:\n"
            '    return f"{value:{next(width for width in sizes)}}"\n'
        )
        module_path.write_text(source, encoding="utf-8")

        with FlextInfraRopeWorkspace.open_workspace(repository_root) as rope:
            resource = rope.resource(module_path)
            if resource is None:
                msg = "Rope did not resolve the format-spec regression resource"
                raise AssertionError(msg)
            changes = u.Infra.rename_changes(
                rope.rope_project,
                resource,
                source.index("widths:"),
                "sizes",
                resources=(resource,),
            )
            rope.rope_project.do(changes)
            rewritten = resource.read()

        tm.that(rewritten, eq=expected)

    def test_write_ast_keeps_nested_generator_name_mutation(self) -> None:
        """Sorted children expose names below positionless comprehension nodes."""
        source = 'rendered = f"{next(width for width in widths)}"\n'
        tree = patchedast.get_patched_ast(source, sorted_children=True)
        widths = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id == "widths"
        )
        # The patched AST carries `sorted_children` as a dynamically attached
        # field: the fork's patch_ast sets it at runtime, so the test writes
        # it the same way instead of through a typing-only wrapper.
        patchable = cast("_PatchableNode", widths)
        patchable.sorted_children = ["sizes"]

        rendered = patchedast.write_ast(tree)

        tm.that(rendered, eq=source.replace("widths", "sizes"))
