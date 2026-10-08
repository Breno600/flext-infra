"""Module-level placement of imports under the FLEXT import law.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import textwrap
from collections.abc import MutableMapping

from flext_infra import c, m, t
from flext_infra._utilities.import_law import FlextInfraUtilitiesImportLaw
from flext_infra.refactor._import_ast import FlextInfraImportNormalizationAstMixin


class FlextInfraImportNormalizationPlacementMixin(
    FlextInfraImportNormalizationAstMixin,
):
    """Place every import at module level, reverse edges under TYPE_CHECKING.

    An import inside a function or class body moves to the module import
    block. An import against the layer order (a lower module binding a higher
    one) moves under ``if TYPE_CHECKING:`` when every read of its binding is
    typing-only; a reverse binding read at runtime keeps its place, so its
    finding stays visible for the manual repair the law requires. A
    ``try/except ImportError`` guard around imports becomes the plain imports:
    a missing dependency fails loud at import time.
    """

    # -- import guards ---------------------------------------------------------------

    @classmethod
    def _guard_edits(
        cls,
        tree: ast.Module,
        lines: t.StrSequence,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Replace every module-level import guard with its plain imports.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        for node in tree.body:
            if not (
                isinstance(node, ast.Try)
                and node.handlers
                and all(
                    isinstance(handler.type, ast.Name)
                    and handler.type.id in {"ImportError", "ModuleNotFoundError"}
                    for handler in node.handlers
                )
                and node.body
                and all(
                    isinstance(statement, ast.Import | ast.ImportFrom)
                    for statement in node.body
                )
            ):
                continue
            imports = [
                textwrap.dedent(
                    "\n".join(
                        lines[statement.lineno - 1 : cls._end_line(statement)],
                    ),
                )
                for statement in node.body
            ]
            edits.append((node.lineno, cls._end_line(node), tuple(imports)))
        return edits

    # -- hoisting and direction ------------------------------------------------------

    @classmethod
    def _placement_edits(
        cls,
        tree: ast.Module,
        lines: t.StrSequence,
        scope: m.Infra.ImportLawScope,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Hoist inline imports and move typing-only reverse imports.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        parents = cls._parent_map(tree)
        bindings = cls._module_bindings(tree)
        root_exports = FlextInfraUtilitiesImportLaw.lazy_exports(
            scope.namespace_dir,
            scope.namespace,
        )
        runtime_lines: list[str] = []
        typing_lines: list[str] = []
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        for node in cls._iter_imports(tree):
            if cls._inside_type_checking(node, parents):
                continue
            inline = cls._enclosing_scope(node, parents) is not None
            if inline and cls._sole_body_statement(node, parents):
                continue
            kept: list[ast.alias] = []
            moved = False
            for alias in node.names:
                placement = cls._alias_placement(
                    node,
                    alias,
                    scope=scope,
                    tree=tree,
                    parents=parents,
                    bindings=bindings,
                    root_exports=root_exports,
                    inline=inline,
                )
                match placement:
                    case c.Infra.ImportPlacement.RUNTIME:
                        runtime_lines.append(cls._render(node, (alias,)))
                        moved = True
                    case c.Infra.ImportPlacement.TYPING:
                        typing_lines.append(cls._render(node, (alias,)))
                        moved = True
                    case c.Infra.ImportPlacement.BOUND:
                        moved = True
                    case c.Infra.ImportPlacement.STAY:
                        kept.append(alias)
            if not moved:
                continue
            indent = cls._line_indent(lines[node.lineno - 1])
            replacement = (f"{indent}{cls._render(node, kept)}",) if kept else ()
            edits.append((node.lineno, cls._end_line(node), replacement))
        if not edits:
            return ()
        edits.extend(
            cls._insertion_edits(
                tree,
                bindings,
                cls._unique(runtime_lines),
                cls._unique(typing_lines),
            ),
        )
        return edits

    @classmethod
    def _alias_placement(
        cls,
        node: ast.Import | ast.ImportFrom,
        alias: ast.alias,
        *,
        scope: m.Infra.ImportLawScope,
        tree: ast.Module,
        parents: t.MappingKV[int, ast.AST],
        bindings: t.MappingKV[str, ast.stmt],
        root_exports: t.StrMapping,
        inline: bool,
    ) -> c.Infra.ImportPlacement:
        """Decide where one imported binding belongs.

        Returns:
            The binding's placement under the import law.

        """
        bound = alias.asname or alias.name.partition(".")[0]
        reverse = cls._is_reverse(node, alias, scope, root_exports)
        if reverse and cls._runtime_uses(tree, bound, parents):
            return c.Infra.ImportPlacement.STAY
        target = (
            c.Infra.ImportPlacement.TYPING if reverse else c.Infra.ImportPlacement.RUNTIME
        )
        if not inline and target is c.Infra.ImportPlacement.RUNTIME:
            return c.Infra.ImportPlacement.STAY
        existing = bindings.get(bound)
        if existing is None or existing is node:
            return target
        if cls._binds_same(existing, node, alias):
            return c.Infra.ImportPlacement.BOUND
        return c.Infra.ImportPlacement.STAY

    @classmethod
    def _is_reverse(
        cls,
        node: ast.Import | ast.ImportFrom,
        alias: ast.alias,
        scope: m.Infra.ImportLawScope,
        root_exports: t.StrMapping,
    ) -> bool:
        """Return whether one binding reaches a later layer of its namespace.

        Returns:
            Whether the import binds a module of a later layer.

        """
        if isinstance(node, ast.Import):
            target = alias.name
        elif node.module == scope.namespace:
            target = root_exports.get(alias.name, scope.namespace)
        else:
            target = node.module or ""
            package_dir = FlextInfraUtilitiesImportLaw.package_dir(
                scope.project_root,
                target,
            )
            if package_dir is not None:
                target = FlextInfraUtilitiesImportLaw.lazy_exports(
                    package_dir,
                    target,
                ).get(alias.name, target)
        if target.split(".")[0] != scope.namespace:
            return False
        return FlextInfraUtilitiesImportLaw.module_import_layer(target) > scope.layer

    @staticmethod
    def _binds_same(
        existing: ast.stmt,
        node: ast.Import | ast.ImportFrom,
        alias: ast.alias,
    ) -> bool:
        """Return whether a module-level import already binds the same object.

        Returns:
            Whether ``existing`` imports the same name from the same module.

        """
        if type(existing) is not type(node):
            return False
        if isinstance(existing, ast.ImportFrom) and isinstance(node, ast.ImportFrom):
            if (existing.module, existing.level) != (node.module, node.level):
                return False
        names = existing.names if isinstance(existing, ast.Import | ast.ImportFrom) else []
        return any(
            (other.name, other.asname) == (alias.name, alias.asname) for other in names
        )

    @classmethod
    def _sole_body_statement(
        cls,
        node: ast.stmt,
        parents: t.MappingKV[int, ast.AST],
    ) -> bool:
        """Return whether moving one import would leave its body empty.

        Returns:
            Whether the import is the only statement past the docstring.

        """
        parent = parents.get(id(node))
        body = getattr(parent, "body", None)
        if not isinstance(body, list):
            return False
        statements = [
            statement
            for statement in body
            if not (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Constant)
                and isinstance(statement.value.value, str)
            )
        ]
        return statements == [node]

    @classmethod
    def _render(
        cls,
        node: ast.Import | ast.ImportFrom,
        aliases: t.SequenceOf[ast.alias],
    ) -> str:
        """Render one import statement over the given aliases.

        Returns:
            The single-line import statement.

        """
        clauses = ", ".join(cls._clause(alias) for alias in aliases)
        if isinstance(node, ast.Import):
            return f"import {clauses}"
        return f"from {'.' * node.level}{node.module or ''} import {clauses}"

    @staticmethod
    def _unique(statements: t.StrSequence) -> t.StrSequence:
        """Return the statements once each, first occurrence first.

        Returns:
            The de-duplicated statements.

        """
        return tuple(dict.fromkeys(statements))

    @classmethod
    def _insertion_edits(
        cls,
        tree: ast.Module,
        bindings: t.MappingKV[str, ast.stmt],
        runtime_lines: t.StrSequence,
        typing_lines: t.StrSequence,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Insert hoisted runtime and typing-only imports at module level.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        anchor = cls._header_end(tree) + 1
        guard = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.If) and cls._is_type_checking_test(node.test)
            ),
            None,
        )
        inserts: MutableMapping[int, list[str]] = {}
        if runtime_lines:
            inserts.setdefault(anchor, []).extend(runtime_lines)
        if typing_lines and guard is not None:
            indent = " " * guard.body[0].col_offset
            inserts.setdefault(cls._end_line(guard) + 1, []).extend(
                f"{indent}{line}" for line in typing_lines
            )
        elif typing_lines:
            block = inserts.setdefault(anchor, [])
            if "TYPE_CHECKING" not in bindings:
                block.insert(0, "from typing import TYPE_CHECKING")
            block.extend(("", "if TYPE_CHECKING:"))
            block.extend(f"    {line}" for line in typing_lines)
            block.append("")
        return tuple((line, line - 1, tuple(added)) for line, added in inserts.items())

    @classmethod
    def _header_end(cls, tree: ast.Module) -> int:
        """Return the last line of the module's leading import block.

        The block runs past the docstring through every import and
        ``TYPE_CHECKING`` guard that precedes the first other statement.

        Returns:
            The last line of the leading import block (0 for an empty module).

        """
        end = 0
        for index, node in enumerate(tree.body):
            docstring = (
                index == 0
                and isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
            if docstring or isinstance(node, ast.Import | ast.ImportFrom):
                end = cls._end_line(node)
                continue
            if isinstance(node, ast.If) and cls._is_type_checking_test(node.test):
                continue
            break
        return end


__all__: list[str] = ["FlextInfraImportNormalizationPlacementMixin"]
