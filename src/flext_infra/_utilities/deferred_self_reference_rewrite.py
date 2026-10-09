"""Semantic normalization of nested-model definition-time references.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from operator import itemgetter

from flext_infra import t


class FlextInfraUtilitiesDeferredSelfReferenceRewrite:
    """Qualify nested-model sibling annotations through their public owner."""

    @classmethod
    def normalize_deferred_self_references(cls, source: str) -> str:
        """Return source with bare sibling annotations qualified by their owner.

        Returns:
            Source with bare sibling annotations qualified by their owner.

        """
        tree = ast.parse(source)
        cls._reject_model_rebuild(tree)
        edits = tuple(
            edit
            for outer in tree.body
            if isinstance(outer, ast.ClassDef)
            for edit in (
                *cls._base_edits(source, outer),
                *cls._annotation_edits(source, outer),
            )
        )
        return cls._apply_edits(source, edits)

    @classmethod
    def _base_edits(
        cls,
        source: str,
        outer: ast.ClassDef,
    ) -> t.SequenceOf[t.Triple[int, int, str]]:
        """Make already-defined sibling bases executable inside the owner body.

        Returns:
            The resulting ``t.SequenceOf[t.Triple[int, int, str]]``.

        Raises:
            ValueError: If definition-time base.

        """
        siblings = tuple(node for node in outer.body if isinstance(node, ast.ClassDef))
        sibling_names = frozenset(node.name for node in siblings)
        available: set[str] = set()
        offsets = cls._line_offsets(source)
        edits: list[t.Triple[int, int, str]] = []
        for sibling in siblings:
            for base in sibling.bases:
                if not (
                    isinstance(base, ast.Attribute)
                    and isinstance(base.value, ast.Name)
                    and base.value.id == outer.name
                    and base.attr in sibling_names
                ):
                    continue
                if base.attr not in available:
                    msg = (
                        f"definition-time base {outer.name}.{base.attr} is not "
                        f"available before {sibling.name} at line {base.lineno}"
                    )
                    raise ValueError(msg)
                start, end = cls._node_span(offsets, base)
                edits.append((start, end, base.attr))
            available.add(sibling.name)
        return tuple(edits)

    @staticmethod
    def _reject_model_rebuild(tree: ast.Module) -> None:
        """Reject runtime schema repair in favor of definition-time correctness.

        Raises:
            ValueError: If model_rebuild is prohibited at line(s).

        """
        rebuilds = tuple(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "model_rebuild"
        )
        if rebuilds:
            lines = ", ".join(str(node.lineno) for node in rebuilds)
            msg = f"model_rebuild is prohibited at line(s): {lines}"
            raise ValueError(msg)

    @classmethod
    def _annotation_edits(
        cls,
        source: str,
        outer: ast.ClassDef,
    ) -> t.SequenceOf[t.Triple[int, int, str]]:
        """Plan owner-qualified sibling references inside deferred annotations.

        Returns:
            The resulting ``t.SequenceOf[t.Triple[int, int, str]]``.

        Raises:
            ValueError: If ambiguous self-qualified annotation.

        """
        siblings = tuple(node for node in outer.body if isinstance(node, ast.ClassDef))
        owned_names = frozenset({
            *(node.name for node in outer.body if isinstance(node, ast.ClassDef)),
            *(node.name.id for node in outer.body if isinstance(node, ast.TypeAlias)),
        })
        declared_names = set(owned_names)
        for statement in outer.body:
            if isinstance(statement, ast.Assign):
                targets = statement.targets
            elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                targets = [statement.target]
            else:
                continue
            declared_names.update(
                node.id
                for target in targets
                for node in ast.walk(target)
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
            )
        offsets = cls._line_offsets(source)
        edits: MutableMapping[t.Pair[int, int], str] = {}
        for sibling in siblings:
            for expression in cls._annotation_expressions(sibling):
                edits.update(
                    cls._call_value_edits(offsets, outer.name, owned_names, expression),
                )
                for node in cls._deferred_type_nodes(expression):
                    if (
                        isinstance(node, ast.Attribute)
                        and isinstance(node.value, ast.Name)
                        and node.value.id == outer.name
                    ):
                        if node.attr not in declared_names and not outer.bases:
                            msg = (
                                "ambiguous self-qualified annotation "
                                f"{outer.name}.{node.attr} at line {node.lineno}"
                            )
                            raise ValueError(msg)
                        continue
                    if not (
                        isinstance(node, ast.Name)
                        and node.id in owned_names
                        and node.id != sibling.name
                    ):
                        continue
                    span = cls._node_span(offsets, node)
                    edits[span] = f"{outer.name}.{node.id}"
        return tuple((*span, replacement) for span, replacement in edits.items())

    @staticmethod
    def _deferred_type_nodes(expression: ast.expr) -> t.SequenceOf[ast.expr]:
        """Walk one deferred annotation without descending into call arguments.

        Names inside nested calls (``u.Field(default_factory=...)``,
        ``m.BeforeValidator(...)``) are runtime value positions, not type
        positions: pydantic resolves them through the parent frame locals at
        deferred-evaluation time, and static checkers evaluate them in the
        class-body scope where the owner class is not yet bound. Qualifying
        those through the owner produced ``reportUndefinedVariable`` and
        unknown-member findings on every consumer.

        Returns:
            The resulting type-position nodes of the annotation.

        """
        stack = [expression]
        nodes: list[ast.expr] = []
        while stack:
            node = stack.pop()
            nodes.append(node)
            if isinstance(node, ast.Call):
                continue
            stack.extend(
                child
                for child in ast.iter_child_nodes(node)
                if isinstance(child, ast.expr)
            )
        return tuple(nodes)

    @classmethod
    def _call_value_edits(
        cls,
        offsets: t.VariadicTuple[int],
        owner: str,
        owned_names: frozenset[str],
        expression: ast.expr,
    ) -> t.MappingKV[t.Pair[int, int], str]:
        """Repair owner-qualified siblings in one annotation's value positions.

        Every call reached through the annotation's type positions carries
        value arguments (``u.Field(default_factory=...)``); a sibling there
        must stay bare, so ``Owner.X`` is rewritten back to the ``X`` the
        parent-frame locals resolve.

        Returns:
            The span-to-replacement edits for those references.

        """
        return {
            cls._node_span(offsets, node): node.attr
            for call in cls._deferred_type_nodes(expression)
            if isinstance(call, ast.Call)
            for argument in (
                *call.args,
                *(keyword.value for keyword in call.keywords),
            )
            for node in ast.walk(argument)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == owner
            and node.attr in owned_names
        }

    @classmethod
    def _collect_annotation_expressions(
        cls,
        expressions: list[ast.expr],
        statement: ast.stmt,
    ) -> None:
        """Append one statement's deferred annotations, then descend.

        Names inside nested calls (``u.Field(default_factory=...)``,
        ``m.BeforeValidator(...)``) are runtime value positions, not type
        positions: pydantic resolves them through the parent frame locals at
        deferred-evaluation time, and static checkers evaluate them in the
        class-body scope where the owner class is not yet bound.

        """
        if isinstance(statement, ast.AnnAssign):
            expressions.append(statement.annotation)
            return
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            expressions.extend(cls._evaluated_function_annotations(statement))
        if isinstance(
            statement,
            ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        ):
            children: t.SequenceOf[ast.stmt] = statement.body
        elif isinstance(statement, ast.TypeAlias):
            expressions.append(statement.value)
            return
        else:
            children = tuple(
                child
                for child in ast.iter_child_nodes(statement)
                if isinstance(child, ast.stmt)
            )
        for child in children:
            cls._collect_annotation_expressions(expressions, child)

    @classmethod
    def _annotation_expressions(cls, node: ast.ClassDef) -> t.SequenceOf[ast.expr]:
        """Collect deferred annotations while excluding executable class bases.

        Returns:
            The resulting ``t.SequenceOf[ast.expr]``.

        """
        expressions: list[ast.expr] = []
        for statement in node.body:
            cls._collect_annotation_expressions(expressions, statement)
        return tuple(expressions)

    @staticmethod
    def _evaluated_function_annotations(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> t.SequenceOf[ast.expr]:
        """Return annotations evaluated when one function is defined.

        Returns:
            Annotations evaluated when one function is defined.

        """
        arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
        annotations = [
            arg.annotation for arg in arguments if arg.annotation is not None
        ]
        annotations.extend(
            arg.annotation
            for arg in (node.args.vararg, node.args.kwarg)
            if arg is not None and arg.annotation is not None
        )
        if node.returns is not None:
            annotations.append(node.returns)
        return tuple(annotations)

    @staticmethod
    def _line_offsets(source: str) -> t.VariadicTuple[int]:
        """Return the character offset of each source line.

        Returns:
            The character offset of each source line.

        """
        offsets = [0]
        for line in source.splitlines(keepends=True):
            offsets.append(offsets[-1] + len(line))
        return tuple(offsets)

    @staticmethod
    def _node_span(offsets: t.VariadicTuple[int], node: ast.expr) -> t.Pair[int, int]:
        """Return one expression's exact source character span.

        Returns:
            One expression's exact source character span.

        """
        end_line = node.end_lineno or node.lineno
        end_column = node.end_col_offset or node.col_offset
        return (
            offsets[node.lineno - 1] + node.col_offset,
            offsets[end_line - 1] + end_column,
        )

    @staticmethod
    def _apply_edits(source: str, edits: t.SequenceOf[t.Triple[int, int, str]]) -> str:
        """Apply non-overlapping source edits from the end of the file.

        Returns:
            The resulting ``str``.

        Raises:
            ValueError: If overlapping deferred-reference edits.

        """
        updated = source
        previous_start = len(source)
        for start, end, replacement in sorted(edits, key=itemgetter(0), reverse=True):
            if end > previous_start:
                msg = f"overlapping deferred-reference edits: {start}:{end}"
                raise ValueError(msg)
            updated = updated[:start] + replacement + updated[end:]
            previous_start = start
        return updated


__all__: list[str] = ["FlextInfraUtilitiesDeferredSelfReferenceRewrite"]
