"""Public utility facet for silent-failure AST enforcement."""

from __future__ import annotations

import ast
from collections.abc import Iterator, MutableMapping
from typing import ClassVar

from flext_infra import m, p, t


class FlextInfraUtilitiesSilentFailureAst:
    """Expose stateless silent-failure detection and fixes through ``u.Infra``.

    Analysis walks one module in the pre-order ``ast.NodeVisitor`` uses and
    threads its context explicitly: import aliases accumulate in that order (an
    import resolves only the calls after it), and the parent map and source
    lines are read-only inputs of the rules. Findings leave as
    ``m.Infra.SilentFailureFinding`` models.
    """

    # ``True`` is included deliberately: an error branch returning True is a
    # fail-open path, strictly worse than the already-flagged False. ``0`` and
    # ``""`` stay OUT: a zero count or empty string is frequently the correct
    # computed result, and the AST cannot distinguish that from a sentinel —
    # flagging them would drown the gate in false positives (flext-t5uhw).
    _SENTINEL_CONSTANTS: ClassVar[frozenset[p.AttributeProbe]] = frozenset({
        False,
        None,
        True,
    })
    _BOOLEAN_PREDICATE_PREFIXES: ClassVar[t.VariadicTuple[str]] = (
        "has_",
        "is_",
        "should_",
    )
    _BROAD_EXCEPTION_NAMES: ClassVar[frozenset[str]] = frozenset({
        "Exception",
        "BaseException",
    })

    @classmethod
    def collect_silent_failure_findings(
        cls, tree: ast.Module, source: str, *, is_test_module: bool = False
    ) -> t.VariadicTuple[m.Infra.SilentFailureFinding]:
        """Collect all silent-failure findings in one module.

        ``is_test_module`` relaxes ``contextlib.suppress`` findings: a test
        teardown legitimately suppresses lifecycle errors (a child process
        that already died) without hiding any production failure path.
        """
        lines = tuple(source.splitlines(keepends=True))
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        aliases: MutableMapping[str, str] = {}
        findings: list[m.Infra.SilentFailureFinding] = []
        for node in cls._preorder(tree):
            if isinstance(node, ast.Import):
                aliases.update(
                    (alias.asname or alias.name.split(".", maxsplit=1)[0], alias.name)
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                aliases.update(
                    (
                        alias.asname or alias.name,
                        f"{module}.{alias.name}" if module else alias.name,
                    )
                    for alias in node.names
                )
            elif isinstance(node, ast.Call):
                findings.extend(
                    cls._call_findings(node, aliases, is_test_module=is_test_module)
                )
            elif isinstance(node, ast.ExceptHandler):
                findings.extend(cls._handler_findings(node, aliases, lines, parents))
            elif isinstance(node, ast.If):
                findings.extend(cls._guard_findings(node, lines, parents))
        return tuple(findings)

    @classmethod
    def collect_silent_failure_fixes(
        cls,
        tree: ast.Module,
        source: str,
        *,
        kinds: set[str] | frozenset[str] | None = None,
        is_test_module: bool = False,
    ) -> t.VariadicTuple[t.Triple[int, int, str]]:
        """Return deterministic fixes for the selected finding kinds."""
        allowed = kinds or frozenset()
        return tuple(
            finding.replacement
            for finding in cls.collect_silent_failure_findings(
                tree, source, is_test_module=is_test_module
            )
            if finding.replacement is not None
            and (not allowed or finding.kind in allowed)
        )

    @staticmethod
    def _preorder(root: ast.AST) -> Iterator[ast.AST]:
        """Yield nodes in ``ast.NodeVisitor`` order: node, then children in field order."""
        stack: list[ast.AST] = [root]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(tuple(ast.iter_child_nodes(node))))

    @classmethod
    def _call_findings(
        cls, node: ast.Call, aliases: t.MappingKV[str, str], *, is_test_module: bool
    ) -> t.VariadicTuple[m.Infra.SilentFailureFinding]:
        if cls._resolve_call_name(node, aliases) == "contextlib.suppress":
            if is_test_module:
                return ()
            return (
                m.Infra.SilentFailureFinding(
                    line=node.lineno,
                    column=node.col_offset,
                    kind="silent-failure-suppress",
                    detail=(
                        "contextlib.suppress(...) silences exceptions without "
                        "propagation"
                    ),
                    fix_action="manual",
                ),
            )
        if cls._is_unwrap_or_call(node):
            return (
                m.Infra.SilentFailureFinding(
                    line=node.lineno,
                    column=node.col_offset,
                    kind="silent-failure-unwrap-or",
                    detail="unwrap_or(sentinel) hides a failure path",
                    fix_action="manual",
                ),
            )
        return ()

    @classmethod
    def _handler_findings(
        cls,
        node: ast.ExceptHandler,
        aliases: t.MappingKV[str, str],
        lines: t.StrSequence,
        parents: t.MappingKV[ast.AST, ast.AST],
    ) -> t.VariadicTuple[m.Infra.SilentFailureFinding]:
        if cls._is_except_pass(node):
            return (
                m.Infra.SilentFailureFinding(
                    line=node.lineno,
                    column=node.col_offset,
                    kind="silent-failure-except-pass",
                    detail="except handler with pass swallows the exception",
                    fix_action="manual",
                ),
            )
        if not cls._body_has_raise_or_fail(node.body) and cls._declares_broad_exception(
            node, aliases
        ):
            return (
                m.Infra.SilentFailureFinding(
                    line=node.lineno,
                    column=node.col_offset,
                    kind="silent-failure-broad-except",
                    detail="broad except does not re-raise or propagate with r.fail",
                    fix_action="manual",
                ),
            )
        if cls._is_except_sentinel(node, aliases):
            return cls._except_sentinel_findings(node, lines, parents)
        return ()

    @classmethod
    def _is_except_sentinel(
        cls, node: ast.ExceptHandler, aliases: t.MappingKV[str, str]
    ) -> bool:
        if node.type is not None and cls._declares_broad_exception(node, aliases):
            return False
        if cls._body_has_raise_or_fail(node.body):
            return False
        returned = cls._first_sentinel_return(node.body)
        if returned is None:
            return False
        # A ``True`` return inside a narrow except branch is a fail-closed
        # predicate decision ("treat as broken / has behavior"), not a
        # swallowed failure. Guards keep ``True`` flagged: a failure branch
        # returning True is fail-open.
        return not (
            isinstance(returned.value, ast.Constant) and returned.value.value is True
        )

    @classmethod
    def _guard_findings(
        cls,
        node: ast.If,
        lines: t.StrSequence,
        parents: t.MappingKV[ast.AST, ast.AST],
    ) -> t.VariadicTuple[m.Infra.SilentFailureFinding]:
        result_name = cls._guard_info(node)
        if result_name is None:
            return ()
        function = cls._enclosing_function(node, parents)
        if function is not None and cls._is_findings_collector(function):
            return ()
        if cls._body_records_failure(node.body):
            return ()
        returned = cls._first_sentinel_return(node.body)
        if returned is None:
            return ()
        inner = cls._result_inner_type(function) if function is not None else None
        replacement: t.Triple[int, int, str] | None = None
        action = "manual"
        if inner is not None:
            label = result_name.removesuffix("_result").replace("_", " ").strip()
            failure = f"{label} failed" if label else "operation failed"
            start, end = cls._return_line_span(lines, returned.lineno)
            replacement = (
                start,
                end,
                (
                    f"{cls._return_indent(lines, returned)}return r[{inner}].fail("
                    f"{result_name}.error or {failure!r})\n"
                ),
            )
            action = "fix_silent_failure_sentinels"
        return (
            m.Infra.SilentFailureFinding(
                line=returned.lineno,
                column=returned.col_offset,
                kind="silent-failure-guard",
                detail=f"failure branch for {result_name!r} returns a sentinel",
                fix_action=action,
                replacement=replacement,
            ),
        )

    @classmethod
    def _except_sentinel_findings(
        cls,
        node: ast.ExceptHandler,
        lines: t.StrSequence,
        parents: t.MappingKV[ast.AST, ast.AST],
    ) -> t.VariadicTuple[m.Infra.SilentFailureFinding]:
        function = cls._enclosing_function(node, parents)
        if function is not None and cls._is_boolean_predicate(function):
            return ()
        if cls._body_records_failure(node.body):
            return ()
        returned = cls._first_sentinel_return(node.body)
        if returned is None:
            return ()
        inner = cls._result_inner_type(function) if function is not None else None
        replacement: t.Triple[int, int, str] | None = None
        action = "manual"
        if inner is not None and node.name is not None:
            start, end = cls._return_line_span(lines, returned.lineno)
            replacement = (
                start,
                end,
                (
                    f"{cls._return_indent(lines, returned)}return r[{inner}].fail("
                    f"str({node.name}), exception={node.name})\n"
                ),
            )
            action = "fix_silent_failure_sentinels"
        return (
            m.Infra.SilentFailureFinding(
                line=returned.lineno,
                column=returned.col_offset,
                kind="silent-failure-except",
                detail="exception branch returns a sentinel instead of propagating",
                fix_action=action,
                replacement=replacement,
            ),
        )

    @staticmethod
    def _is_except_pass(node: ast.ExceptHandler) -> bool:
        return any(isinstance(statement, ast.Pass) for statement in node.body) and all(
            isinstance(statement, ast.Pass)
            or (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Constant)
            )
            for statement in node.body
        )

    @staticmethod
    def _guard_info(node: ast.If) -> str | None:
        test = node.test
        if isinstance(test, ast.Attribute) and isinstance(test.value, ast.Name):
            return test.value.id if test.attr in {"failure", "success"} else None
        if (
            isinstance(test, ast.UnaryOp)
            and isinstance(test.op, ast.Not)
            and isinstance(test.operand, ast.Attribute)
            and isinstance(test.operand.value, ast.Name)
            and test.operand.attr in {"failure", "success"}
        ):
            return test.operand.value.id
        return None

    @staticmethod
    def _enclosing_function(
        node: ast.AST, parents: t.MappingKV[ast.AST, ast.AST]
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        current: ast.AST | None = node
        while current is not None:
            if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
                return current
            current = parents.get(current)
        return None

    @staticmethod
    def _is_findings_collector(
        function: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        """Return whether ``function`` is a findings collector.

        Why (cosmos-3flk9): a collector's contract returns the list of
        findings it found; an empty list in a success branch means "no
        findings", not a swallowed failure.
        """
        return function.name.endswith("_findings") or function.name.startswith(
            "collect_"
        )

    @classmethod
    def _is_boolean_predicate(
        cls, function: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> bool:
        """Return whether ``function`` is a boolean predicate.

        Why (cosmos-3flk9): a ``has_*``/``is_*``/``should_*`` predicate maps
        a specific, expected exception to ``False`` — that is the predicate's
        meaning, not a hidden failure.
        """
        return function.name.startswith(cls._BOOLEAN_PREDICATE_PREFIXES)

    @staticmethod
    def _result_inner_type(
        function: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> str | None:
        returns = function.returns
        if not isinstance(returns, ast.Subscript):
            return None
        value = returns.value
        is_result = (isinstance(value, ast.Name) and value.id in {"r", "Result"}) or (
            isinstance(value, ast.Attribute) and value.attr == "Result"
        )
        return ast.unparse(returns.slice) if is_result else None

    @staticmethod
    def _return_line_span(lines: t.StrSequence, line_number: int) -> t.Pair[int, int]:
        start = sum(len(lines[index]) for index in range(line_number - 1))
        return start, start + len(lines[line_number - 1])

    @staticmethod
    def _return_indent(lines: t.StrSequence, node: ast.Return) -> str:
        line = lines[node.lineno - 1]
        return line[: len(line) - len(line.lstrip())]

    @classmethod
    def _is_sentinel_value(cls, node: ast.expr | None) -> bool:
        if node is None:
            return True
        if isinstance(node, ast.Constant) and node.value in cls._SENTINEL_CONSTANTS:
            return True
        if isinstance(node, (ast.List, ast.Tuple)) and not node.elts:
            return True
        if isinstance(node, ast.Dict) and not node.keys:
            return True
        # set()/frozenset() carry the same "no result" semantics as [] and {}.
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"set", "frozenset"}
            and not node.args
            and not node.keywords
        )

    @classmethod
    def _first_sentinel_return(cls, body: t.SequenceOf[ast.stmt]) -> ast.Return | None:
        return next(
            (
                child
                for statement in body
                for child in ast.walk(statement)
                if isinstance(child, ast.Return) and cls._is_sentinel_value(child.value)
            ),
            None,
        )

    @staticmethod
    def _body_has_raise_or_fail(body: t.SequenceOf[ast.stmt]) -> bool:
        return any(
            isinstance(child, ast.Raise)
            or (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr.startswith("fail")
            )
            for statement in body
            for child in ast.walk(statement)
        )

    @staticmethod
    def _body_records_failure(body: t.SequenceOf[ast.stmt]) -> bool:
        """Whether the branch records the failure through an explicit skip.

        Gate and fixer flows own a loud skip channel (recorded with the error
        and rendered in reports) — a branch that skips is not silent.
        """
        return any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "skip"
            for statement in body
            for child in ast.walk(statement)
        )

    @staticmethod
    def _resolve_call_name(node: ast.Call, aliases: t.MappingKV[str, str]) -> str:
        function = node.func
        if isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name):
            base = aliases.get(function.value.id, function.value.id)
            return f"{base}.{function.attr}"
        if isinstance(function, ast.Name):
            return aliases.get(function.id, function.id)
        return ""

    @classmethod
    def _expression_name(
        cls, node: ast.expr | None, aliases: t.MappingKV[str, str]
    ) -> str:
        if node is None:
            return ""
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            base = cls._expression_name(node.value, aliases)
            if base:
                return f"{base}.{node.attr}"
        return ""

    @classmethod
    def _declares_broad_exception(
        cls, node: ast.ExceptHandler, aliases: t.MappingKV[str, str]
    ) -> bool:
        """Whether the clause declares no exception, or any broad one.

        A bare ``except:`` declares none. ``except (A, B):`` declares both --
        the tuple form is exactly as narrow as the single form. An
        unresolvable expression keeps its conservative broad reading: the rule
        cannot prove it narrow, so it does not claim it is.
        """
        if node.type is None:
            return True
        declared = (
            tuple(node.type.elts) if isinstance(node.type, ast.Tuple) else (node.type,)
        )
        names = tuple(cls._expression_name(element, aliases) for element in declared)
        return not names or any(
            not name or name in cls._BROAD_EXCEPTION_NAMES for name in names
        )

    @classmethod
    def _is_unwrap_or_call(cls, node: ast.Call) -> bool:
        function = node.func
        return (
            isinstance(function, ast.Attribute)
            and function.attr == "unwrap_or"
            and bool(node.args)
            and cls._is_sentinel_value(node.args[0])
        )


__all__: t.VariadicTuple[str] = ("FlextInfraUtilitiesSilentFailureAst",)
