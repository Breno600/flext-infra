"""Module-level placement of imports under the FLEXT import law.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import textwrap
from collections.abc import MutableMapping

from flext_infra import c, m, t, u
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
        return tuple(
            (
                node.lineno,
                cls._end_line(node),
                tuple(
                    textwrap.dedent(
                        "\n".join(
                            lines[statement.lineno - 1 : cls._end_line(statement)],
                        ),
                    )
                    for statement in node.body
                ),
            )
            for node in tree.body
            if isinstance(node, ast.Try) and cls._is_import_guard(node)
        )

    @staticmethod
    def _is_import_guard(node: ast.Try) -> bool:
        """Return whether one ``try`` only imports and only catches import errors.

        Returns:
            Whether the statement is an import guard.

        """
        return (
            bool(node.handlers)
            and all(
                isinstance(handler.type, ast.Name)
                and handler.type.id in c.Infra.IMPORT_LAW_GUARD_ERRORS
                for handler in node.handlers
            )
            and bool(node.body)
            and all(
                isinstance(statement, ast.Import | ast.ImportFrom)
                for statement in node.body
            )
        )

    # -- hoisting and direction ------------------------------------------------------

    @classmethod
    def _placement_edits(
        cls,
        state: m.Infra.ImportLawPass,
        lines: t.StrSequence,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Hoist inline imports and move typing-only reverse imports.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        placed: MutableMapping[c.Infra.ImportPlacement, list[str]] = {
            placement: [] for placement in c.Infra.ImportPlacement
        }
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        for node in cls._iter_imports(state.tree):
            edit = cls._statement_edit(state, node, lines, placed)
            if edit is not None:
                edits.append(edit)
        if not edits:
            return ()
        edits.extend(
            cls._insertion_edits(
                state,
                tuple(dict.fromkeys(placed[c.Infra.ImportPlacement.RUNTIME])),
                tuple(dict.fromkeys(placed[c.Infra.ImportPlacement.TYPING])),
            ),
        )
        return edits

    @classmethod
    def _statement_edit(
        cls,
        state: m.Infra.ImportLawPass,
        node: ast.Import | ast.ImportFrom,
        lines: t.StrSequence,
        placed: MutableMapping[c.Infra.ImportPlacement, list[str]],
    ) -> tuple[int, int, t.StrSequence] | None:
        """Plan one import statement's move, recording where its aliases go.

        Returns:
            The rewrite of the statement's own lines, or ``None`` when every
            alias keeps its place.

        """
        if cls._inside_type_checking(node, state.parents):
            return None
        inline = cls._enclosing_scope(node, state.parents) is not None
        if inline and cls._sole_body_statement(node, state.parents):
            return None
        kept: list[ast.alias] = []
        for alias in node.names:
            placement = cls._alias_placement(state, node, alias, inline=inline)
            if placement is c.Infra.ImportPlacement.STAY:
                kept.append(alias)
            else:
                placed[placement].append(cls._render(node, (alias,)))
        if len(kept) == len(node.names):
            return None
        indent = cls._line_indent(lines[node.lineno - 1])
        replacement = (f"{indent}{cls._render(node, kept)}",) if kept else ()
        return (node.lineno, cls._end_line(node), replacement)

    @classmethod
    def _alias_placement(
        cls,
        state: m.Infra.ImportLawPass,
        node: ast.Import | ast.ImportFrom,
        alias: ast.alias,
        *,
        inline: bool,
    ) -> c.Infra.ImportPlacement:
        """Decide where one imported binding belongs.

        Returns:
            The binding's placement under the import law.

        """
        bound = alias.asname or alias.name.partition(".")[0]
        reverse = cls._is_reverse(state, node, alias)
        if reverse and cls._runtime_uses(state.tree, bound, state.parents):
            return c.Infra.ImportPlacement.STAY
        if not reverse and not inline:
            return c.Infra.ImportPlacement.STAY
        existing = state.bindings.get(bound)
        if existing is not None and existing is not node:
            return (
                c.Infra.ImportPlacement.BOUND
                if cls._binds_same(existing, node, alias)
                else c.Infra.ImportPlacement.STAY
            )
        return (
            c.Infra.ImportPlacement.TYPING
            if reverse
            else c.Infra.ImportPlacement.RUNTIME
        )

    @classmethod
    def _is_reverse(
        cls,
        state: m.Infra.ImportLawPass,
        node: ast.Import | ast.ImportFrom,
        alias: ast.alias,
    ) -> bool:
        """Return whether one binding reaches a later layer of its namespace.

        Returns:
            Whether the import binds a module of a later layer.

        """
        scope = state.scope
        if isinstance(node, ast.Import):
            target = alias.name
        elif node.module == scope.namespace:
            target = state.root_exports.get(alias.name, scope.namespace)
        else:
            target = node.module or ""
            package_dir = u.Infra.import_package_dir(scope.project_root, target)
            if package_dir is not None:
                target = u.Infra.import_lazy_exports(package_dir, target).get(
                    alias.name,
                    target,
                )
        if target.split(".")[0] != scope.namespace:
            return False
        return u.Infra.module_import_layer(target) > scope.layer

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
        match existing, node:
            case ast.Import(names=names), ast.Import():
                pass
            case ast.ImportFrom(
                names=names, module=module, level=level
            ), ast.ImportFrom(
                module=node_module,
                level=node_level,
            ) if (module, level) == (node_module, node_level):
                pass
            case _:
                return False
        return any(
            (other.name, other.asname) == (alias.name, alias.asname) for other in names
        )

    @staticmethod
    def _sole_body_statement(
        node: ast.stmt,
        parents: t.MappingKV[int, ast.AST],
    ) -> bool:
        """Return whether moving one import would leave its body empty.

        Returns:
            Whether the import is the only statement past a docstring.

        """
        parent = parents.get(id(node))
        if not isinstance(
            parent,
            ast.FunctionDef
            | ast.AsyncFunctionDef
            | ast.ClassDef
            | ast.If
            | ast.For
            | ast.While
            | ast.With
            | ast.Try,
        ):
            return False
        if node in parent.body:
            body: t.SequenceOf[ast.stmt] = parent.body
        elif isinstance(parent, ast.If | ast.For | ast.While | ast.Try):
            body = parent.orelse
        else:
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

    @classmethod
    def _insertion_edits(
        cls,
        state: m.Infra.ImportLawPass,
        runtime_lines: t.StrSequence,
        typing_lines: t.StrSequence,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Insert hoisted runtime and typing-only imports at module level.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        anchor = cls._header_end(state.tree) + 1
        guard = next(
            (
                node
                for node in state.tree.body
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
            if "TYPE_CHECKING" not in state.bindings:
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
