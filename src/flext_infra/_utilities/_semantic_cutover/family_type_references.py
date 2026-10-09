"""Quoted type references resolved in the original Rope lexical scope.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from flext_infra import c, m, p, t
from flext_infra._utilities.rope_runtime_modules import (
    FlextInfraUtilitiesRopeRuntimeModules,
)
from flext_infra._utilities.rope_runtime_refactors import (
    FlextInfraUtilitiesRopeRuntimeRefactors,
)


class FlextInfraUtilitiesSemanticFamilyTypeReferences:
    """Select type positions structurally and bind every edit to Rope identity."""

    @classmethod
    def typeexpression_ranges(cls, source: str) -> frozenset[t.Pair[int, int]]:
        """Expose the same structural roots to concrete-syntax consumer adapters.

        Returns:
            The resulting ``frozenset[t.Pair[int, int]]``.

        """
        return frozenset(
            cls.expression_range(source, expression)
            for expression, _line in cls._annotation_roots(ast.parse(source))
        )

    @classmethod
    def type_payload_ranges(
        cls,
        source: str,
        project: p.Infra.RopeProject,
        module: p.Infra.RopePyModule,
    ) -> frozenset[t.Pair[int, int]]:
        """Protect Literal values and Annotated metadata in every alias form.

        Selection uses the same resolved typing identities as quoted rewrites;
        an ordinary runtime assignment is not implicitly a type declaration.

        Returns:
            The resulting ``frozenset[t.Pair[int, int]]``.
        """
        from flext_infra._utilities import FlextInfraUtilitiesRopeRuntimeModules

        protected: set[t.Pair[int, int]] = set()
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        nodes = tuple(
            node
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Subscript)
        )
        if not nodes:
            return frozenset()
        typing = project.get_module("typing")
        for node in nodes:
            offset, _end = cls.expression_range(source, node)
            scope = runtime.scope_at(module, offset)
            selected = tuple(cls._type_nodes(node, project, scope))
            arguments = (
                node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            )
            binding = runtime.resolve_symbol(scope, node.value)
            if runtime.same_name(typing.get_attribute("Literal"), binding):
                protected.update(
                    cls.expression_range(source, argument) for argument in arguments
                )
            elif runtime.same_name(typing.get_attribute("Annotated"), binding):
                protected.update(
                    cls.expression_range(source, argument)
                    for argument in arguments
                    if argument not in selected
                )
        return frozenset(protected)

    @classmethod
    def _family_quoted_rewrites(
        cls,
        resource: p.Infra.RopeResource,
        source: str,
        *,
        flatten: m.Infra.FamilyWrapperFlatten,
    ) -> t.Pair[bool, t.VariadicTuple[m.Infra.SourceRewrite]]:
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        module = flatten.project.get_pymodule(resource)
        edits: list[m.Infra.SourceRewrite] = []
        for annotation, declaration_line in cls._annotation_roots(ast.parse(source)):
            start, _end = cls.expression_range(source, annotation)
            scope = runtime.scope_at(module, start, declaration_line=declaration_line)
            for node in cls._type_nodes(annotation, flatten.project, scope):
                if not isinstance(node, ast.Constant) or not isinstance(
                    node.value,
                    str,
                ):
                    continue
                blocked, updated = cls._quoted_type_source(
                    node.value,
                    resource,
                    scope,
                    flatten=flatten,
                )
                if blocked:
                    return (True, ())
                if updated != node.value:
                    start, end = cls.expression_range(source, node)
                    edits.append(
                        m.Infra.SourceRewrite(start=start, end=end, text=repr(updated)),
                    )
        return (False, tuple(edits))

    @classmethod
    def _quoted_type_source(
        cls,
        source: str,
        resource: p.Infra.RopeResource,
        scope: p.Infra.RopeScope,
        *,
        flatten: m.Infra.FamilyWrapperFlatten,
    ) -> t.Pair[bool, str]:
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        nodes = tuple(
            cls._type_nodes(
                ast.parse(source, mode="eval").body,
                flatten.project,
                scope,
            ),
        )
        edits: list[m.Infra.SourceRewrite] = []
        for node in nodes:
            blocked, edit = cls._quoted_node_rewrite(
                node,
                source,
                resource,
                scope,
                flatten=flatten,
            )
            if blocked:
                return (True, source)
            if edit is not None:
                edits.append(edit)
        for node in nodes:
            start, end = cls.expression_range(source, node)
            if not any(
                edit.start <= start and end <= edit.end for edit in edits
            ) and runtime.same_name(
                flatten.wrapper,
                runtime.resolve_symbol(scope, node),
            ):
                return (True, source)
        change = FlextInfraUtilitiesRopeRuntimeRefactors.content_change(
            resource,
            source,
            edits,
        )
        return (False, change.new_contents)

    @classmethod
    def _quoted_node_rewrite(
        cls,
        node: ast.expr,
        source: str,
        resource: p.Infra.RopeResource,
        scope: p.Infra.RopeScope,
        *,
        flatten: m.Infra.FamilyWrapperFlatten,
    ) -> t.Pair[bool, m.Infra.SourceRewrite | None]:
        """Resolve one selected node; nested strings retain their original scope.

        Returns:
            The resulting ``t.Pair[bool, m.Infra.SourceRewrite | None]``.

        """
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        names = flatten.names
        start, end = cls.expression_range(source, node)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            blocked, updated = cls._quoted_type_source(
                node.value,
                resource,
                scope,
                flatten=flatten,
            )
            if blocked or updated == node.value:
                return (blocked, None)
            return (
                False,
                m.Infra.SourceRewrite(start=start, end=end, text=repr(updated)),
            )
        if isinstance(node, ast.Attribute) and runtime.same_name(
            flatten.wrapper,
            runtime.resolve_symbol(scope, node.value),
        ):
            if node.attr not in names:
                return (True, None)
            text = cls._promoted_attribute(
                node,
                scope,
                flatten.owner_name,
                names[node.attr],
            )
            return (False, m.Infra.SourceRewrite(start=start, end=end, text=text))
        if (
            isinstance(node, ast.Name)
            and node.id in names
            and runtime.same_name(
                flatten.wrapper.get_object().get_attribute(node.id),
                runtime.resolve_symbol(scope, node),
            )
        ):
            return (
                False,
                m.Infra.SourceRewrite(start=start, end=end, text=names[node.id]),
            )
        return (False, None)

    @staticmethod
    def _promoted_attribute(
        node: ast.Attribute,
        scope: p.Infra.RopeScope,
        owner_name: str,
        name: str,
    ) -> str:
        """Keep an explicit parent or the method's owning class after promotion.

        Returns:
            The resulting ``str``.

        """
        if isinstance(node.value, ast.Attribute):
            return f"{ast.unparse(node.value.value)}.{name}"
        if scope.get_kind() == c.Infra.RopeScopeKind.FUNCTION:
            return f"{owner_name}.{name}" if owner_name else name
        return name

    @classmethod
    def _annotation_roots(
        cls,
        module: ast.Module,
    ) -> Iterator[t.Pair[ast.expr, int | None]]:
        for node in ast.walk(module):
            if isinstance(node, ast.AnnAssign):
                yield (node.annotation, None)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                yield from cls._function_annotations(node)
            elif isinstance(node, ast.TypeAlias):
                yield (node.value, None)
            elif isinstance(node, ast.ClassDef):
                for base in node.bases:
                    yield (base, node.lineno)
            elif isinstance(node, ast.TypeVar | ast.ParamSpec | ast.TypeVarTuple):
                yield from cls._type_parameter_annotations(node)

    @staticmethod
    def _type_parameter_annotations(
        node: ast.TypeVar | ast.ParamSpec | ast.TypeVarTuple,
    ) -> Iterator[t.Pair[ast.expr, int | None]]:
        """Yield a type parameter's bound before its optional default.

        Yields:
            Each ``t.Pair[ast.expr, int | None]``.

        """
        if isinstance(node, ast.TypeVar) and node.bound is not None:
            yield (node.bound, None)
        if node.default_value is not None:
            yield (node.default_value, None)

    @staticmethod
    def _function_annotations(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> Iterator[t.Pair[ast.expr, int | None]]:
        """Yield each parameter and return annotation in declaration order.

        Yields:
            Each ``t.Pair[ast.expr, int | None]``.

        """
        arguments = (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
            node.args.vararg,
            node.args.kwarg,
        )
        for argument in arguments:
            if argument is not None and argument.annotation is not None:
                yield (argument.annotation, node.lineno)
        if node.returns is not None:
            yield (node.returns, node.lineno)

    @classmethod
    def _type_nodes(
        cls,
        node: ast.expr,
        project: p.Infra.RopeProject,
        scope: p.Infra.RopeScope,
    ) -> Iterator[ast.expr]:
        yield node
        if isinstance(node, ast.Subscript):
            yield from cls._type_nodes(node.value, project, scope)
            runtime = FlextInfraUtilitiesRopeRuntimeModules
            binding = runtime.resolve_symbol(scope, node.value)
            typing = project.get_module("typing")
            if runtime.same_name(typing.get_attribute("Literal"), binding):
                return
            arguments = (
                node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            )
            if runtime.same_name(typing.get_attribute("Annotated"), binding):
                arguments = arguments[:1]
            for argument in arguments:
                yield from cls._type_nodes(argument, project, scope)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            yield from cls._type_nodes(node.left, project, scope)
            yield from cls._type_nodes(node.right, project, scope)
        elif isinstance(node, ast.Tuple | ast.List):
            for element in node.elts:
                yield from cls._type_nodes(element, project, scope)
        elif isinstance(node, ast.Attribute | ast.Starred):
            yield from cls._type_nodes(node.value, project, scope)

    @staticmethod
    def expression_range(source: str, expression: ast.expr) -> t.Pair[int, int]:
        if expression.end_lineno is None or expression.end_col_offset is None:
            msg = "Parsed type expression has no complete source coordinates"
            raise ValueError(msg)
        lines = source.splitlines(keepends=True)
        start = sum(map(len, lines[: expression.lineno - 1])) + len(
            lines[expression.lineno - 1]
            .encode("utf-8")[: expression.col_offset]
            .decode("utf-8"),
        )
        end = sum(map(len, lines[: expression.end_lineno - 1])) + len(
            lines[expression.end_lineno - 1]
            .encode("utf-8")[: expression.end_col_offset]
            .decode("utf-8"),
        )
        return (start, end)


__all__: list[str] = ["FlextInfraUtilitiesSemanticFamilyTypeReferences"]
