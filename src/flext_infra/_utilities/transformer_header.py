"""Canonical Python module header analysis and import injection.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping

from flext_infra import c, t
from flext_infra._utilities import FlextInfraUtilitiesTransformerHeaderParser


class FlextInfraUtilitiesTransformerHeader(FlextInfraUtilitiesTransformerHeaderParser):
    """Inject canonical aliases only when the source actually uses them."""

    @classmethod
    def ensure_future_annotations(cls, source: str) -> str:
        """Return source with exactly one correctly positioned future import.

        Returns:
            Source with exactly one correctly positioned future import.

        """
        module = ast.parse(source)
        imports = [
            node
            for node in ast.walk(module)
            if isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
        ]
        if len(imports) == 1:
            header = (
                module.body[1:]
                if ast.get_docstring(module) is not None
                else module.body
            )
            for node in header:
                if not isinstance(node, ast.ImportFrom) or node.module != "__future__":
                    break
                if node is imports[0]:
                    return source
        normalized = cls._remove_future_annotations_lines(source)
        body = normalized.splitlines(keepends=True)
        info = cls._parse_header(normalized)
        offset = max(
            info.span.shebang_end,
            info.span.encoding_end,
            info.span.comments_end,
            info.span.docstring_end,
        )
        line_index = normalized[:offset].count("\n")
        future_line = f"{c.Infra.FUTURE_ANNOTATIONS}\n"
        if info.span.docstring_end:
            while line_index < len(body) and not body[line_index].strip():
                del body[line_index]
            insert_lines = ["\n", future_line]
            if line_index < len(body):
                insert_lines.append("\n")
            body[line_index:line_index] = insert_lines
        else:
            body.insert(line_index, future_line)
        return "".join(body)

    @classmethod
    def ensure_alias_import(
        cls,
        source: str,
        module: str,
        alias: str,
        *,
        runtime_required: bool = False,
    ) -> str:
        """Honor the consumer's runtime requirement when introducing an alias.

        Returns:
            The resulting ``str``.

        Raises:
            ValueError: If canonical import alias must be non-empty; or if canonical
                alias.

        """
        if not alias:
            msg = "canonical import alias must be non-empty"
            raise ValueError(msg)
        if not cls.alias_used(source, alias):
            return source
        if cls.has_alias_import(source, alias):
            deferred = (
                not runtime_required
                and "from __future__ import annotations" in source
                and cls._alias_is_annotation_only(source, alias)
            )
            if cls.has_runtime_alias_import(source, alias) or deferred:
                return source
            msg = (
                f"canonical alias {alias!r} has only deferred or conditional imports "
                "but its consumer requires a runtime binding"
            )
            raise ValueError(msg)
        if cls.alias_locally_bound(source, alias):
            return source
        if not runtime_required:
            typed = cls._alias_import_under_type_checking(source, module, alias)
            if typed is not None:
                return typed
        info = cls._parse_header(source)
        offset = info.span.last_import_end or max(
            info.span.shebang_end,
            info.span.encoding_end,
            info.span.comments_end,
            info.span.docstring_end,
        )
        line = f"from {module} import {alias}\n"
        if offset < len(source) and not source[offset:].startswith("\n"):
            line = f"{line}\n"
        return f"{source[:offset]}{line}{source[offset:]}"

    @staticmethod
    def has_runtime_alias_import(source: str, alias: str | None = None) -> bool:
        """Prove one or any canonical facade alias in the runtime import header.

        Returns:
            The resulting ``bool``.

        """
        module = ast.parse(source)
        header = (
            module.body[1:] if ast.get_docstring(module) is not None else module.body
        )
        expected = (
            frozenset({alias}) if alias is not None else c.ENFORCEMENT_CANONICAL_ALIASES
        )
        for node in header:
            if not isinstance(node, ast.ImportFrom | ast.Import):
                return False
            if any((name.asname or name.name) in expected for name in node.names):
                return True
        return False

    @classmethod
    def _alias_import_under_type_checking(
        cls,
        source: str,
        module: str,
        alias: str,
    ) -> str | None:
        """Place an annotation-only facade import inside ``if TYPE_CHECKING:``.

        A module that the package imports while initialising itself cannot
        import that same package at runtime: injecting the facade at module
        level made ``__version__.py`` raise ImportError on a partially
        initialised ``flext_infra``. With deferred annotations the alias is only
        ever read by a type checker, so the import belongs in the type-checking
        block, which is also what the facade law prescribes. Returns None when
        the module has no such block to extend.

        Returns:
            The resulting ``str | None``.

        """
        if "from __future__ import annotations" not in source:
            return None
        if not cls._alias_is_annotation_only(source, alias):
            return None
        lines = source.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if line.rstrip() != "if TYPE_CHECKING:":
                continue
            following = lines[index + 1 :]
            indent = next(
                (
                    item[: len(item) - len(item.lstrip())]
                    for item in following
                    if item.strip()
                ),
                "    ",
            )
            lines.insert(index + 1, f"{indent}from {module} import {alias}\n")
            return "".join(lines)
        return cls._create_type_checking_block(source, module, alias)

    @classmethod
    def _create_type_checking_block(cls, source: str, module: str, alias: str) -> str:
        """Create the type-checking block an annotation-only import needs.

        Without a block to extend, the injector fell through to a module-level
        import, which is exactly what breaks a module the package imports while
        initialising itself: ``__version__.py`` then raised
        ImportError on a partially initialised package. Deferred annotations
        make the alias a type-checker-only read, so the block is the correct
        destination and the facade law prescribes it.

        Returns:
            The resulting ``str``.

        """
        info = cls._parse_header(source)
        offset = info.span.last_import_end or max(
            info.span.shebang_end,
            info.span.encoding_end,
            info.span.comments_end,
            info.span.docstring_end,
        )
        prefix = source[:offset]
        if prefix and not prefix.endswith("\n"):
            prefix = f"{prefix}\n"
        if not prefix.endswith("\n\n"):
            prefix = f"{prefix}\n"
        guard = ""
        if not cls._imports_type_checking(source):
            guard = "from typing import TYPE_CHECKING\n\n"
        block = f"if TYPE_CHECKING:\n    from {module} import {alias}\n"
        return f"{prefix}{guard}{block}{source[offset:]}"

    @staticmethod
    def _imports_type_checking(source: str) -> bool:
        """Return whether the module already imports ``TYPE_CHECKING``.

        Returns:
            Whether the module already imports ``TYPE_CHECKING``.

        """
        module = ast.parse(source)
        for node in ast.walk(module):
            if not isinstance(node, ast.ImportFrom) or node.module != "typing":
                continue
            if any(entry.name == "TYPE_CHECKING" for entry in node.names):
                return True
        return False

    @staticmethod
    def alias_used(source: str, alias: str) -> bool:
        """Return whether ``alias`` is used as a standalone dotted identifier.

        Returns:
            Whether ``alias`` is used as a standalone dotted identifier.

        """
        return (
            c.Infra.compile(rf"\b{c.Infra.escape(alias)}\.(?![0-9])").search(source)
            is not None
        )

    @classmethod
    def has_alias_import(cls, source: str, alias: str) -> bool:
        """Return whether ``alias`` is already bound by a ``from`` import.

        Every binding counts, including one inside ``if TYPE_CHECKING:``. The
        header scan stops at the first non-header statement, so an alias
        imported in that block read as absent and a duplicate was injected
        next to it. This proves a lexical declaration only; callers requiring
        runtime availability use ``has_runtime_alias_import``. Source that does
        not parse raises its ``SyntaxError``.

        Returns:
            Whether ``alias`` is already bound by a ``from`` import.

        """
        return any(
            (name.asname or name.name) == alias
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom | ast.Import)
            for name in node.names
        )

    @staticmethod
    def _runtime_model_annotation_ids(module: ast.Module) -> frozenset[int]:
        """Return ids of class-body annotations a model resolves at runtime.

        A pydantic model evaluates its field annotations while the class is
        built, so an alias used there is a runtime dependency even though the
        syntax is an annotation. Deferring such an alias under
        ``if TYPE_CHECKING:`` made ``_SmellData.model_validate_json`` raise
        ``PydanticUserError`` during package import.

        Returns:
            Ids of class-body annotations a model resolves at runtime.

        """
        parents: MutableMapping[int, ast.AST] = {}
        for parent in ast.walk(module):
            for child in ast.iter_child_nodes(parent):
                parents[id(child)] = parent
        runtime_ids: set[int] = set()
        for node in ast.walk(module):
            if not isinstance(node, ast.AnnAssign):
                continue
            owner = parents.get(id(node))
            if not isinstance(owner, ast.ClassDef):
                continue
            if not any(
                (isinstance(base, ast.Name) and base.id in c.Infra.RUNTIME_MODEL_BASES)
                or (
                    isinstance(base, ast.Attribute)
                    and base.attr in c.Infra.RUNTIME_MODEL_BASES
                )
                for base in owner.bases
            ):
                continue
            runtime_ids.add(id(node.annotation))
        return frozenset(runtime_ids)

    @staticmethod
    def _alias_is_annotation_only(source: str, alias: str) -> bool:
        """Report whether every use of ``alias`` sits inside an annotation.

        Class-body annotations on a runtime model are excluded from that set:
        the model resolves them at import time, so the alias must stay
        importable at runtime.

        Returns:
            The resulting ``bool``.

        """
        module = ast.parse(source)
        runtime_ids = (
            FlextInfraUtilitiesTransformerHeader._runtime_model_annotation_ids(module)
        )
        spans: list[t.Quad[int, int, int, int]] = []
        for node in ast.walk(module):
            annotations: t.MutableSequenceOf[ast.expr | None] = []
            if isinstance(node, ast.AnnAssign | ast.arg):
                annotations.append(node.annotation)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                annotations.append(node.returns)
            for annotation in annotations:
                if annotation is None or annotation.end_lineno is None:
                    continue
                if id(annotation) in runtime_ids:
                    continue
                spans.append((
                    annotation.lineno,
                    annotation.col_offset,
                    annotation.end_lineno,
                    annotation.end_col_offset or 0,
                ))

        def inside(node: ast.expr) -> bool:
            position = (node.lineno, node.col_offset)
            return any(
                (start_line, start_col) <= position <= (end_line, end_col)
                for start_line, start_col, end_line, end_col in spans
            )

        uses = [
            node
            for node in ast.walk(module)
            if isinstance(node, ast.Name) and node.id == alias
        ]
        return bool(uses) and all(inside(node) for node in uses)

    @staticmethod
    def alias_locally_bound(source: str, alias: str) -> bool:
        """Return whether a module-level definition or assignment owns an alias.

        Returns:
            Whether a module-level definition or assignment owns an alias.

        """
        escaped = c.Infra.escape(alias)
        pattern = c.Infra.compile(
            rf"^(?:{escaped}\s*(?::[^=\n]+)?=(?!=)|(?:class|def)\s+{escaped}\b)",
            multiline=True,
        )
        return pattern.search(source) is not None

    @staticmethod
    def _remove_future_annotations_lines(source: str) -> str:
        """Strip every ``from __future__ import annotations`` line.

        Returns:
            The resulting ``str``.

        """
        return "".join(
            line
            for line in source.splitlines(keepends=True)
            if line.strip() != c.Infra.FUTURE_ANNOTATIONS
        )


__all__: t.MutableSequenceOf[str] = ["FlextInfraUtilitiesTransformerHeader"]
