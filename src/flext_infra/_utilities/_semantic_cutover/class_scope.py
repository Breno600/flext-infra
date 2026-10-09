"""Definition-time name resolution inside class suites.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import builtins

from flext_infra import t


class FlextInfraUtilitiesSemanticCutoverClassScope:
    """Model the names a class suite reads while its class is being built."""

    @staticmethod
    def _comprehension_parts(
        node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp,
    ) -> tuple[t.VariadicTuple[ast.AST], frozenset[str]]:
        """Return a comprehension's evaluated parts and the targets it binds.

        Returns:
            The element, key/value and generator nodes, with the target names.

        """
        elements: t.VariadicTuple[ast.AST] = (
            (node.key, node.value) if isinstance(node, ast.DictComp) else (node.elt,)
        )
        targets = frozenset(
            name.id
            for generator in node.generators
            for name in ast.walk(generator.target)
            if isinstance(name, ast.Name)
        )
        return (*elements, *node.generators), targets

    @staticmethod
    def _type_param_names(node: ast.ClassDef) -> frozenset[str]:
        """Return the PEP 695 type parameter names a class declares.

        Returns:
            The names of the class's own type parameters.

        """
        return frozenset(
            parameter.name
            for parameter in node.type_params
            if isinstance(parameter, ast.TypeVar | ast.ParamSpec | ast.TypeVarTuple)
        )

    @classmethod
    def _evaluated_parts(
        cls,
        node: ast.AST,
    ) -> t.VariadicTuple[tuple[t.VariadicTuple[ast.AST], frozenset[str]]]:
        """Return the children a suite evaluates now, each with names it binds.

        Function, lambda and nested class bodies run in their own scope, and a
        type alias value is lazy. Their headers do not: decorators, defaults,
        bases and class keywords are evaluated by the enclosing suite, bases
        and keywords with the class's own type parameters in scope. A
        comprehension never loads the targets it binds itself. Annotations are
        stored, not evaluated.

        Returns:
            ``(children, bound)`` pairs whose loads minus ``bound`` escape.

        """
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            decorators = () if isinstance(node, ast.Lambda) else node.decorator_list
            defaults = (item for item in node.args.kw_defaults if item is not None)
            return (((*node.args.defaults, *defaults, *decorators), frozenset()),)
        if isinstance(node, ast.ClassDef):
            header = (*node.bases, *(keyword.value for keyword in node.keywords))
            params = cls._type_param_names(node)
            return ((tuple(node.decorator_list), frozenset()), (header, params))
        if isinstance(
            node,
            ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp,
        ):
            return (cls._comprehension_parts(node),)
        if isinstance(node, ast.TypeAlias | ast.AnnAssign):
            value = node.value if isinstance(node, ast.AnnAssign) else None
            return (((value,) if value is not None else (), frozenset()),)
        return ((tuple(ast.iter_child_nodes(node)), frozenset()),)

    @classmethod
    def _immediate_suite_loads(cls, statement: ast.stmt) -> frozenset[str]:
        """Return names a class suite evaluates while the class is being built.

        Returns:
            The names loaded immediately by ``statement``.

        """

        def visit(node: ast.AST) -> set[str]:
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                return {node.id}
            loads: set[str] = set()
            for children, bound in cls._evaluated_parts(node):
                loads.update(
                    {name for child in children for name in visit(child)} - bound,
                )
            return loads

        return frozenset(visit(statement))

    @staticmethod
    def _scope_bindings(statement: ast.stmt) -> frozenset[str]:
        """Return the names one statement binds in the scope that runs it.

        Returns:
            The bound names, without descending into nested scopes.

        """
        names: set[str] = set()

        def visit(node: ast.AST) -> None:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                names.add(node.name)
                return
            if isinstance(node, ast.Lambda):
                return
            if isinstance(node, ast.Import | ast.ImportFrom):
                names.update(
                    (alias.asname or alias.name).split(".", maxsplit=1)[0]
                    for alias in node.names
                )
                return
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.add(node.id)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                names.add(node.name)
            for child in ast.iter_child_nodes(node):
                visit(child)

        visit(statement)
        return frozenset(names)

    @staticmethod
    def _suite_classes(statement: ast.stmt) -> t.VariadicTuple[ast.ClassDef]:
        """Return the classes one statement defines in the scope that runs it.

        Returns:
            The class statements reachable without entering a nested scope.

        """
        found: list[ast.ClassDef] = []

        def visit(node: ast.AST) -> None:
            if isinstance(node, ast.ClassDef):
                found.append(node)
                return
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
                return
            for child in ast.iter_child_nodes(node):
                visit(child)

        visit(statement)
        return tuple(found)

    @classmethod
    def _suite_name_errors(
        cls,
        node: ast.ClassDef,
        qualname: str,
        module_bound: frozenset[str],
    ) -> t.VariadicTuple[str]:
        """Return the unresolved immediate loads of one suite and its nested suites.

        Returns:
            One ``qualname: name`` entry per unresolved load.

        """
        local = {"__module__", "__qualname__", *cls._type_param_names(node)}
        for statement in node.body:
            local.update(cls._scope_bindings(statement))
        errors = [
            f"{qualname}: {name}"
            for name in sorted({
                name
                for statement in node.body
                for name in cls._immediate_suite_loads(statement)
            })
            if name not in local and name not in module_bound
        ]
        for statement in node.body:
            for inner in cls._suite_classes(statement):
                errors.extend(
                    cls._suite_name_errors(
                        inner,
                        f"{qualname}.{inner.name}",
                        module_bound,
                    ),
                )
        return tuple(errors)

    @classmethod
    def definition_time_name_errors(cls, source: str) -> t.VariadicTuple[str]:
        """Return class-suite loads that raise NameError while the module imports.

        A class suite resolves a name in its own namespace, then in the module
        globals bound so far, then in builtins. An enclosing class namespace
        is never visible, and no class name is bound until its statement ends,
        so a suite that names its own class or reads an enclosing class member
        fails at import. A star import makes the module globals unknowable, so
        such a module reports nothing.

        Returns:
            One ``qualname: name`` entry per unresolved load, in source order.

        """
        tree = ast.parse(source)
        if any(
            isinstance(node, ast.ImportFrom)
            and any(alias.name == "*" for alias in node.names)
            for node in ast.walk(tree)
        ):
            return ()
        module_bound = {*dir(builtins), "__file__", "__path__", "__builtins__"}
        errors: list[str] = []
        for statement in tree.body:
            for node in cls._suite_classes(statement):
                errors.extend(
                    cls._suite_name_errors(node, node.name, frozenset(module_bound)),
                )
            module_bound.update(cls._scope_bindings(statement))
        return tuple(errors)


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverClassScope"]
