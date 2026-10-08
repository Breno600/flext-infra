"""Shared AST, layer-rank and line-edit helpers of import normalization.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import operator
from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import c, t


class FlextInfraImportNormalizationAstMixin:
    """Parse, scope, rank and edit module sources for import rewrites."""

    @staticmethod
    def _use_sites(tree: ast.Module, name: str) -> list[ast.Name]:
        """Return every load of one binding in the module.

        Returns:
            The resulting ``list[ast.Name]``.

        """
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and node.id == name
            and isinstance(node.ctx, ast.Load)
        ]

    @classmethod
    def _demotable(
        cls,
        site: ast.Name,
        parents: t.MappingKV[int, ast.AST],
        frozen: frozenset[int],
    ) -> bool:
        """Return whether one use site can move inside its using function.

        Returns:
            Whether one use site can move inside its using function.

        """
        if id(site) in frozen:
            return False
        node: ast.AST | None = site
        while node is not None:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                return True
            node = parents.get(id(node))
        return False

    @staticmethod
    def _freeze_function_decorators(
        frozen: set[int],
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        """Freeze one function's decorators, defaults, and annotations."""
        for decorator in node.decorator_list:
            frozen.update(id(sub) for sub in ast.walk(decorator))
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                frozen.update(id(sub) for sub in ast.walk(default))
        if node.returns is not None:
            frozen.update(id(sub) for sub in ast.walk(node.returns))
        for argument in (
            *node.args.args,
            *node.args.posonlyargs,
            *node.args.kwonlyargs,
        ):
            if argument.annotation is not None:
                frozen.update(id(sub) for sub in ast.walk(argument.annotation))

    @classmethod
    def _frozen_node_ids(cls, tree: ast.Module) -> set[int]:
        """Mark every subtree that must stay at module definition time.

        Class bases and keywords, decorators, signature defaults and
        annotations all evaluate when their statement executes, so a name
        used there can never move inside a function body.

        Returns:
            The resulting ``set[int]`` of frozen node ids.

        """
        frozen: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    frozen.update(id(sub) for sub in ast.walk(base))
                for keyword in node.keywords:
                    frozen.update(id(sub) for sub in ast.walk(keyword.value))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cls._freeze_function_decorators(frozen, node)
        return frozen

    @classmethod
    def _function_anchors(
        cls,
        sites: t.SequenceOf[ast.Name],
        parents: t.MappingKV[int, ast.AST],
    ) -> list[int]:
        """Return the body-insertion line of each site's outermost function.

        Returns:
            The resulting ``list[int]``.

        """
        anchors: set[int] = set()
        for site in sites:
            outermost: ast.FunctionDef | ast.AsyncFunctionDef | None = None
            node: ast.AST | None = site
            while node is not None:
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    outermost = node
                node = parents.get(id(node))
            if outermost is not None:
                anchors.add(cls._body_insert_line(outermost))
        return sorted(anchors)

    @staticmethod
    def _body_insert_line(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        """Return the first body line after a docstring, when one exists.

        Returns:
            The resulting ``int``.

        """
        body = function_node.body
        lead = body[0]
        is_docstring = (
            isinstance(lead, ast.Expr)
            and isinstance(lead.value, ast.Constant)
            and isinstance(lead.value.value, str)
        )
        if is_docstring and len(body) > 1:
            return body[1].lineno
        if is_docstring:
            return (lead.end_lineno or lead.lineno) + 1
        return lead.lineno

    @classmethod
    def _function_body_indent(cls, lines: t.StrSequence, insert_line: int) -> str:
        """Return the body indent implied by one function insertion line.

        Returns:
            The resulting ``str``.

        """
        if insert_line <= len(lines):
            reference = lines[insert_line - 1]
            if reference.strip():
                return cls._line_indent(reference)
        for offset in range(1, 8):
            index = insert_line - 1 - offset
            if index >= 0 and lines[index].strip():
                return f"{cls._line_indent(lines[index])}    "
        return "    "

    @classmethod
    def _declared_family_rank(cls, file_path: Path) -> int | None:
        """Return the family rank one file's path declares, when it lives in one.

        Returns:
            The resulting ``int | None``.

        """
        for part in file_path.parts:
            rank = c.Infra.IMPORT_NORMALIZATION_FAMILY_RANK.get(part.lstrip("_"))
            if rank is not None and (
                part.startswith("_") or part in c.Infra.IMPORT_NORMALIZATION_FAMILY_RANK
            ):
                return rank
        return None

    @classmethod
    def _module_layer_rank(cls, file_path: Path) -> int:
        """Return the module's own layer rank over the declared order.

        Returns:
            The resulting ``int``.

        """
        family_rank = cls._declared_family_rank(file_path)
        if family_rank is not None:
            return family_rank
        name = file_path.name
        settings_here = "_settings" in file_path.parts
        config_here = "_config" in file_path.parts
        layers: t.SequenceOf[tuple[bool, int]] = (
            (name in {"settings.py", "_settings.py"} or settings_here, 0),
            (name in {"config.py", "_config.py"} or config_here, 1),
            (name == "base.py", 8),
            ("services" in file_path.parts, 9),
            (name == "api.py", 10),
            (name == "cli.py", 11),
        )
        return next(
            (rank for matched, rank in layers if matched),
            c.Infra.IMPORT_NORMALIZATION_DEFAULT_LAYER_RANK,
        )

    # -- shared helpers -------------------------------------------------

    @staticmethod
    def _parse(source: str) -> ast.Module | None:
        """Parse one source text, tolerating syntax the engine cannot own.

        Returns:
            The resulting ``ast.Module | None``.

        """
        try:
            return ast.parse(source)
        except SyntaxError:
            return None

    @staticmethod
    def _iter_imports(tree: ast.Module) -> t.SequenceOf[ast.stmt]:
        """Return every import statement anywhere in the module.

        Returns:
            The resulting ``t.SequenceOf[ast.stmt]``.

        """
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]

    @staticmethod
    def _parent_map(tree: ast.Module) -> t.MappingKV[int, ast.AST]:
        """Map every node id to its parent node.

        Returns:
            The resulting ``t.MappingKV[int, ast.AST]``.

        """
        parents: MutableMapping[int, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[id(child)] = node
        return parents

    @classmethod
    def _owning_block(
        cls,
        node: ast.AST,
        parents: t.MappingKV[int, ast.AST],
    ) -> ast.AST:
        """Return the module or ``if`` block that owns one import statement.

        Returns:
            The resulting ``ast.AST``.

        """
        current: ast.AST | None = node
        while current is not None:
            parent = parents.get(id(current))
            if isinstance(parent, ast.Module | ast.If):
                return parent
            current = parent
        return node

    @classmethod
    def _at_module_level(
        cls,
        node: ast.AST,
        parents: t.MappingKV[int, ast.AST],
    ) -> bool:
        """Return whether one import statement executes at module import time.

        Only statements whose scope chain reaches the module (optionally
        through ``if`` blocks) run at import time; a class-body or
        function-body import owns a narrower scope and is never merged or
        demoted across it.

        Returns:
            Whether one import statement executes at module import time.

        """
        current: ast.AST | None = node
        while current is not None:
            if isinstance(
                current,
                ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef,
            ):
                return False
            current = parents.get(id(current))
        return True

    @classmethod
    def _inside_type_checking(
        cls,
        node: ast.AST,
        parents: t.MappingKV[int, ast.AST],
    ) -> bool:
        """Return whether the statement sits under an ``if TYPE_CHECKING:``.

        Returns:
            Whether the statement sits under an ``if TYPE_CHECKING:``.

        """
        current: ast.AST | None = node
        while current is not None:
            if isinstance(current, ast.If):
                names = " ".join(
                    getattr(sub, "id", "")
                    for sub in ast.walk(current.test)
                    if isinstance(sub, ast.Name)
                )
                if "TYPE_CHECKING" in names:
                    return True
            current = parents.get(id(current))
        return False

    @staticmethod
    def _end_line(node: ast.stmt) -> int:
        """Return one statement's inclusive end line.

        Returns:
            The resulting ``int``.

        """
        return getattr(node, "end_lineno", None) or getattr(node, "lineno", 1)

    @staticmethod
    def _line_indent(line: str) -> str:
        """Return one line's leading whitespace.

        Returns:
            The resulting ``str``.

        """
        return line[: len(line) - len(line.lstrip())]

    @classmethod
    def _apply_edits(
        cls,
        source: str,
        edits: t.SequenceOf[tuple[int, int, t.StrSequence]],
    ) -> str | None:
        """Apply non-overlapping line edits; ``None`` when they collide.

        A span ``(n, n - 1)`` inserts BEFORE line ``n``; a span ``(a, b)``
        with ``b >= a`` replaces lines ``a..b``; a span with an empty
        replacement deletes its lines.

        Returns:
            The resulting ``str | None``.

        """
        lines = source.splitlines()
        ordered = sorted(edits, key=operator.itemgetter(0, 1), reverse=True)
        last_start: int | None = None
        for start, end, replacement in ordered:
            if last_start is not None and end >= last_start:
                return None
            last_start = start
            if not replacement:
                if end >= start:
                    lines[start - 1 : end] = ()
                continue
            if end < start:
                lines[start - 1 : start - 1] = list(replacement)
                continue
            lines[start - 1 : end] = list(replacement)
        return "\n".join(lines).rstrip() + "\n"

    @classmethod
    def _locate(cls, project_root: Path, file_path: Path) -> tuple[str, str] | None:
        """Return the (package, dotted module) of one source file.

        Returns:
            The resulting ``tuple[str, str] | None``.

        """
        base = project_root / "src"
        if not base.is_dir():
            return None
        try:
            relative = file_path.resolve().relative_to(base.resolve())
        except ValueError:
            return None
        parts = relative.with_suffix("").parts
        if not parts or parts[-1] == "__init__":
            parts = parts[:-1]
        if len(parts) < 1 or not (base / parts[0] / "__init__.py").is_file():
            return None
        return parts[0], ".".join(parts)


__all__: list[str] = ["FlextInfraImportNormalizationAstMixin"]
