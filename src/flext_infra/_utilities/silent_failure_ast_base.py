"""Shared AST state for silent-failure enforcement."""
from __future__ import annotations
import ast
from collections.abc import MutableMapping
from typing import ClassVar, NamedTuple
from flext_infra import p, t

class FlextInfraUtilitiesSilentFailureAstBase(ast.NodeVisitor):
    """Own AST traversal state and structural predicates."""

    class Finding(NamedTuple):
        """One silent-failure occurrence and its optional structural fix."""
        line: int
        column: int
        kind: str
        detail: str
        fix_action: str
        replacement: t.Triple[int, int, str] | None = None
    _SENTINEL_CONSTANTS: ClassVar[frozenset[p.AttributeProbe]] = frozenset({False, None, True})
    _BOOLEAN_PREDICATE_PREFIXES: ClassVar[t.VariadicTuple[str]] = ('has_', 'is_', 'should_')
    _BROAD_EXCEPTION_NAMES: ClassVar[frozenset[str]] = frozenset({'Exception', 'BaseException'})

    def __init__(self, source: str, *, is_test_module: bool=False) -> None:
        self._lines = source.splitlines(keepends=True)
        self._findings: list[FlextInfraUtilitiesSilentFailureAstBase.Finding] = []
        self._import_aliases: MutableMapping[str, str] = {}
        self._parents: MutableMapping[ast.AST, ast.AST] = {}
        self._is_test_module = is_test_module

    def analyze(self, tree: ast.Module) -> t.VariadicTuple[Finding]:
        """Build the parent map and collect findings from one module."""
        self._parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        self.visit(tree)
        return tuple(self._findings)

    def _enclosing_function(self, node: ast.AST) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        current: ast.AST | None = node
        while current is not None:
            if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
                return current
            current = self._parents.get(current)
        return None

    def _is_findings_collector(self, function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Return whether ``function`` is a findings collector.

        Why (cosmos-3flk9): a collector's contract returns the list of
        findings it found; an empty list in a success branch means "no
        findings", not a swallowed failure.
        """
        return function.name.endswith('_findings') or function.name.startswith('collect_')

    def _is_boolean_predicate(self, function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Return whether ``function`` is a boolean predicate.

        Why (cosmos-3flk9): a ``has_*``/``is_*``/``should_*`` predicate maps
        a specific, expected exception to ``False`` — that is the predicate's
        meaning, not a hidden failure.
        """
        return function.name.startswith(self._BOOLEAN_PREDICATE_PREFIXES)

    @staticmethod
    def _result_inner_type(function: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
        returns = function.returns
        if not isinstance(returns, ast.Subscript):
            return None
        value = returns.value
        is_result = isinstance(value, ast.Name) and value.id in {'r', 'Result'} or (isinstance(value, ast.Attribute) and value.attr == 'Result')
        return ast.unparse(returns.slice) if is_result else None

    def _line_offsets(self, line_number: int) -> t.Pair[int, int]:
        start = sum((len(self._lines[index]) for index in range(line_number - 1)))
        return (start, start + len(self._lines[line_number - 1]))

    def _indent_of(self, node: ast.Return) -> str:
        line = self._lines[node.lineno - 1]
        return line[:len(line) - len(line.lstrip())]

    def _add(self, *, line: int, column: int, kind: str, detail: str, fix_action: str='manual', replacement: t.Triple[int, int, str] | None=None) -> None:
        self._findings.append(self.Finding(line=line, column=column, kind=kind, detail=detail, fix_action=fix_action, replacement=replacement))

    @classmethod
    def _is_sentinel_value(cls, node: ast.expr | None) -> bool:
        if node is None:
            return True
        if isinstance(node, ast.Constant) and node.value in cls._SENTINEL_CONSTANTS:
            return True
        if isinstance(node, (ast.List, ast.Tuple)) and (not node.elts):
            return True
        if isinstance(node, ast.Dict) and (not node.keys):
            return True
        return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and (node.func.id in {'set', 'frozenset'}) and (not node.args) and (not node.keywords)

    def _first_sentinel_return(self, body: t.SequenceOf[ast.stmt]) -> ast.Return | None:
        return next((child for statement in body for child in ast.walk(statement) if isinstance(child, ast.Return) and self._is_sentinel_value(child.value)), None)

    @staticmethod
    def _body_has_raise_or_fail(body: t.SequenceOf[ast.stmt]) -> bool:
        return any((isinstance(child, ast.Raise) or (isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr.startswith('fail')) for statement in body for child in ast.walk(statement)))

    @staticmethod
    def _body_records_failure(body: t.SequenceOf[ast.stmt]) -> bool:
        """Whether the branch records the failure through an explicit skip.

        Gate and fixer flows own a loud skip channel (recorded with the error
        and rendered in reports) — a branch that skips is not silent.
        """
        return any((isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and (child.func.attr == 'skip') for statement in body for child in ast.walk(statement)))

    def _resolve_call_name(self, node: ast.Call) -> str:
        function = node.func
        if isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
            base = self._import_aliases.get(function.value.id, function.value.id)
            return f'{base}.{function.attr}'
        if isinstance(function, ast.Name):
            return self._import_aliases.get(function.id, function.id)
        return ''

    def _expression_name(self, node: ast.expr | None) -> str:
        if node is None:
            return ''
        if isinstance(node, ast.Name):
            return self._import_aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            base = self._expression_name(node.value)
            if base:
                return f'{base}.{node.attr}'
        return ''

    def _handler_exception_names(self, node: ast.ExceptHandler) -> t.VariadicTuple[str]:
        """Return the exception names one ``except`` clause declares.

        Single owner for every handler rule. A bare ``except:`` declares none.
        ``except (A, B):`` declares both -- the tuple form is exactly as narrow
        as the single form. Resolving only ``ast.Name``/``ast.Attribute``
        collapsed a tuple to the empty name, which is also what an unresolvable
        expression yields, so narrow handlers were indistinguishable from bare
        ones and were all reported broad.
        """
        if node.type is None:
            return ()
        declared = tuple(node.type.elts) if isinstance(node.type, ast.Tuple) else (node.type,)
        return tuple((self._expression_name(element) for element in declared))

    def _declares_broad_exception(self, node: ast.ExceptHandler) -> bool:
        """Whether the clause declares no exception, or any broad one.

        An unresolvable expression keeps its conservative broad reading: the
        rule cannot prove it narrow, so it does not claim it is.
        """
        names = self._handler_exception_names(node)
        return not names or any((not name or name in self._BROAD_EXCEPTION_NAMES for name in names))

    @classmethod
    def _is_unwrap_or_call(cls, node: ast.Call) -> bool:
        function = node.func
        return isinstance(function, ast.Attribute) and function.attr == 'unwrap_or' and bool(node.args) and cls._is_sentinel_value(node.args[0])
__all__: t.VariadicTuple[str] = ('FlextInfraUtilitiesSilentFailureAstBase',)