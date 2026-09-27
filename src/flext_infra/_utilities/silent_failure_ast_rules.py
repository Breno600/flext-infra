"""Structural rules for silent-failure AST enforcement."""
from __future__ import annotations
import ast
from typing import override
from flext_infra import t
from .._utilities.silent_failure_ast_base import FlextInfraUtilitiesSilentFailureAstBase

class FlextInfraUtilitiesSilentFailureAstRules(FlextInfraUtilitiesSilentFailureAstBase):
    """Collect exception suppression and sentinel-return violations."""

    @override
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            bound = alias.asname or alias.name.split('.', maxsplit=1)[0]
            self._import_aliases[bound] = alias.name
        self.generic_visit(node)

    @override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ''
        for alias in node.names:
            bound = alias.asname or alias.name
            self._import_aliases[bound] = f'{module}.{alias.name}' if module else alias.name
        self.generic_visit(node)

    @override
    def visit_Call(self, node: ast.Call) -> None:
        call_name = self._resolve_call_name(node)
        if call_name == 'contextlib.suppress' and (not self._is_test_module):
            self._add(line=node.lineno, column=node.col_offset, kind='silent-failure-suppress', detail='contextlib.suppress(...) silences exceptions without propagation')
        elif self._is_unwrap_or_call(node):
            self._add(line=node.lineno, column=node.col_offset, kind='silent-failure-unwrap-or', detail='unwrap_or(sentinel) hides a failure path')
        self.generic_visit(node)

    @override
    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if self._is_except_pass(node):
            self._add(line=node.lineno, column=node.col_offset, kind='silent-failure-except-pass', detail='except handler with pass swallows the exception')
        elif self._is_broad_unhandled_except(node):
            self._add(line=node.lineno, column=node.col_offset, kind='silent-failure-broad-except', detail='broad except does not re-raise or propagate with r.fail')
        elif self._is_except_sentinel(node):
            self._add_except_sentinel(node)
        self.generic_visit(node)

    @override
    def visit_If(self, node: ast.If) -> None:
        guard = self._guard_info(node)
        if guard is not None:
            self._add_guard(node, guard)
        self.generic_visit(node)

    @staticmethod
    def _is_except_pass(node: ast.ExceptHandler) -> bool:
        return any((isinstance(statement, ast.Pass) for statement in node.body)) and all((isinstance(statement, ast.Pass) or (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)) for statement in node.body))

    def _is_broad_unhandled_except(self, node: ast.ExceptHandler) -> bool:
        if self._body_has_raise_or_fail(node.body):
            return False
        return self._declares_broad_exception(node)

    def _is_except_sentinel(self, node: ast.ExceptHandler) -> bool:
        if node.type is not None and self._declares_broad_exception(node):
            return False
        if self._body_has_raise_or_fail(node.body):
            return False
        returned = self._first_sentinel_return(node.body)
        if returned is None:
            return False
        is_true_constant = isinstance(returned.value, ast.Constant) and returned.value.value is True
        return not is_true_constant

    @staticmethod
    def _guard_info(node: ast.If) -> str | None:
        test = node.test
        if isinstance(test, ast.Attribute) and isinstance(test.value, ast.Name):
            return test.value.id if test.attr in {'failure', 'success'} else None
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) and isinstance(test.operand, ast.Attribute) and isinstance(test.operand.value, ast.Name) and (test.operand.attr in {'failure', 'success'}):
            return test.operand.value.id
        return None

    def _sentinel_return_context(self, node: ast.If | ast.ExceptHandler) -> t.Pair[ast.Return, str | None] | None:
        """Return the first sentinel return in ``node`` with its Result inner type.

        ``None`` when the branch returns no sentinel, so the caller emits nothing.
        """
        returned = self._first_sentinel_return(node.body)
        if returned is None:
            return None
        function = self._enclosing_function(node)
        inner = self._result_inner_type(function) if function is not None else None
        return (returned, inner)

    def _add_guard(self, node: ast.If, result_name: str) -> None:
        function = self._enclosing_function(node)
        if function is not None and self._is_findings_collector(function):
            return
        if self._body_records_failure(node.body):
            return
        context = self._sentinel_return_context(node)
        if context is None:
            return
        returned, inner = context
        replacement: t.Triple[int, int, str] | None = None
        action = 'manual'
        if inner is not None:
            label = result_name.removesuffix('_result').replace('_', ' ').strip()
            failure = f'{label} failed' if label else 'operation failed'
            start, end = self._line_offsets(returned.lineno)
            replacement = (start, end, f'{self._indent_of(returned)}return r[{inner}].fail({result_name}.error or {failure!r})\n')
            action = 'fix_silent_failure_sentinels'
        self._add(line=returned.lineno, column=returned.col_offset, kind='silent-failure-guard', detail=f'failure branch for {result_name!r} returns a sentinel', fix_action=action, replacement=replacement)

    def _add_except_sentinel(self, node: ast.ExceptHandler) -> None:
        function = self._enclosing_function(node)
        if function is not None and self._is_boolean_predicate(function):
            return
        if self._body_records_failure(node.body):
            return
        context = self._sentinel_return_context(node)
        if context is None:
            return
        returned, inner = context
        replacement: t.Triple[int, int, str] | None = None
        action = 'manual'
        if inner is not None and node.name is not None:
            start, end = self._line_offsets(returned.lineno)
            replacement = (start, end, f'{self._indent_of(returned)}return r[{inner}].fail(str({node.name}), exception={node.name})\n')
            action = 'fix_silent_failure_sentinels'
        self._add(line=returned.lineno, column=returned.col_offset, kind='silent-failure-except', detail='exception branch returns a sentinel instead of propagating', fix_action=action, replacement=replacement)
__all__: t.VariadicTuple[str] = ('FlextInfraUtilitiesSilentFailureAstRules',)