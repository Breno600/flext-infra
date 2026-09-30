"""Resolve container mutation against lexical bindings before type widening."""

from __future__ import annotations

from typing import override

import libcst as cst
from libcst.metadata import (
    ExpressionContext,
    ExpressionContextProvider,
    ParentNodeProvider,
    Scope,
    ScopeProvider,
)


class FlextInfraTypingMutation(cst.CSTVisitor):
    """Prove reads through indexing, iteration, membership, truth and builtin len.

    Direct aliases share the complete use proof. Every other access retains the
    concrete parameter contract, including method calls and escaped references.
    """

    METADATA_DEPENDENCIES = (
        ScopeProvider,
        ParentNodeProvider,
        ExpressionContextProvider,
    )

    def __init__(self) -> None:
        self.mutated: set[str] = set()
        self.aliases: set[tuple[str, str]] = set()
        self.parameters: set[str] = set()

    def _names(self, expression: cst.BaseExpression) -> frozenset[str]:
        while isinstance(expression, (cst.Attribute, cst.Subscript)):
            expression = expression.value
        if not isinstance(expression, cst.Name):
            return frozenset()
        scope = self.get_metadata(ScopeProvider, expression)
        if not isinstance(scope, Scope):
            msg = "container mutation has no lexical scope"
            raise TypeError(msg)
        return frozenset(
            name.name for name in scope.get_qualified_names_for(expression)
        )

    def _assignment(
        self, target: cst.BaseAssignTargetExpression, value: cst.BaseExpression | None
    ) -> None:
        if isinstance(target, cst.Subscript):
            self.mutated.update(self._names(target))
        elif isinstance(target, cst.Name) and isinstance(value, cst.Name):
            self.aliases.update(
                (alias, source)
                for alias in self._names(target)
                for source in self._names(value)
            )

    @override
    def visit_Assign(self, node: cst.Assign) -> None:
        for target in node.targets:
            self._assignment(target.target, node.value)

    @override
    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        self._assignment(node.target, node.value)

    @override
    def visit_AugAssign(self, node: cst.AugAssign) -> None:
        self.mutated.update(self._names(node.target))

    @override
    def visit_Param(self, node: cst.Param) -> None:
        self.parameters.update(self._names(node.name))

    @override
    def visit_Subscript(self, node: cst.Subscript) -> None:
        if self.get_metadata(ExpressionContextProvider, node, None) in {
            ExpressionContext.STORE,
            ExpressionContext.DEL,
        }:
            self.mutated.update(self._names(node))

    @override
    def visit_Name(self, node: cst.Name) -> None:
        if (
            self.get_metadata(ExpressionContextProvider, node, None)
            != ExpressionContext.LOAD
        ):
            return
        if self.get_metadata(ScopeProvider, node, None) is None:
            return
        if not self._readonly_access(node):
            self.mutated.update(self._names(node))

    def _readonly_access(self, node: cst.Name) -> bool:
        parent = self.get_metadata(ParentNodeProvider, node)
        proven = False
        if isinstance(parent, cst.Subscript) and parent.value is node:
            proven = all(
                isinstance(element.slice, cst.Index) for element in parent.slice
            )
        elif isinstance(parent, (cst.For, cst.CompFor)):
            proven = parent.iter is node
        elif isinstance(parent, cst.ComparisonTarget):
            proven = parent.comparator is node and isinstance(
                parent.operator, (cst.In, cst.NotIn)
            )
        elif isinstance(parent, cst.UnaryOperation):
            proven = isinstance(parent.operator, cst.Not)
        elif isinstance(parent, cst.Assign) and parent.value is node:
            proven = all(
                isinstance(target.target, cst.Name) for target in parent.targets
            )
        elif isinstance(parent, cst.AnnAssign) and parent.value is node:
            proven = isinstance(parent.target, cst.Name)
        elif isinstance(parent, cst.Arg):
            proven = self._readonly_argument(parent)
        return proven

    def _readonly_argument(self, argument: cst.Arg) -> bool:
        if argument.star or argument.keyword is not None:
            return False
        call = self.get_metadata(ParentNodeProvider, argument)
        if not isinstance(call, cst.Call) or len(call.args) != 1:
            return False
        scope = self.get_metadata(ScopeProvider, call.func, None)
        if not isinstance(scope, Scope):
            return False
        names = {name.name for name in scope.get_qualified_names_for(call.func)}
        return names == {"builtins.len"}

    def readonly_bindings(self) -> frozenset[str]:
        """Return parameters whose references and direct aliases are all proven."""
        pending = set(self.mutated)
        while pending:
            sources = {
                source
                for alias, source in self.aliases
                if alias in pending and source not in self.mutated
            }
            self.mutated.update(sources)
            pending = sources
        return frozenset(self.parameters.difference(self.mutated))


__all__: list[str] = ["FlextInfraTypingMutation"]
