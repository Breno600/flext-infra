"""Generic helper mixin for Rope-backed refactors.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast

from flext_infra import t
from flext_infra._utilities import FlextInfraUtilitiesRopeMethodOrderMixin


class FlextInfraUtilitiesRopeHelpers(FlextInfraUtilitiesRopeMethodOrderMixin):
    """AST definition spans and method-order helpers."""

    @staticmethod
    def statement_line_span(statement: ast.stmt) -> t.IntPair:
        """Return the 1-based inclusive line span of one statement, decorators included.

        Returns:
            The 1-based inclusive line span of one statement, decorators included.

        """
        decorators: t.SequenceOf[ast.expr] = (
            statement.decorator_list
            if isinstance(
                statement,
                ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
            )
            else ()
        )
        start = min((statement.lineno, *(node.lineno for node in decorators)))
        return start, statement.end_lineno or statement.lineno

    @staticmethod
    def top_level_definition_span(
        source: str,
        name: str,
        *,
        kind: str,
    ) -> t.IntPair | None:
        """Return the line span of the top-level ``kind`` definition named ``name``.

        Returns:
            The line span of the top-level ``kind`` definition named ``name``.

        Raises:
            ValueError: If unsupported definition kind.

        """
        if kind == "function":
            node_types: t.VariadicTuple[type[ast.stmt]] = (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            )
        elif kind == "class":
            node_types = (ast.ClassDef,)
        else:
            msg = f"unsupported definition kind: {kind}"
            raise ValueError(msg)
        for statement in ast.parse(source).body:
            if (
                isinstance(
                    statement,
                    ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
                )
                and isinstance(statement, node_types)
                and statement.name == name
            ):
                return FlextInfraUtilitiesRopeHelpers.statement_line_span(statement)
        return None

    @staticmethod
    def extract_definition(
        source: str,
        name: str,
        *,
        kind: str = "function",
    ) -> str | None:
        """Return the top-level def/class block named ``name``, decorators included.

        Returns:
            The full top-level def/class block named ``name``, decorators included.

        """
        span = FlextInfraUtilitiesRopeHelpers.top_level_definition_span(
            source,
            name,
            kind=kind,
        )
        if span is None:
            return None
        start, end = span
        return "\n".join(source.splitlines()[start - 1 : end])


__all__: list[str] = ["FlextInfraUtilitiesRopeHelpers"]
