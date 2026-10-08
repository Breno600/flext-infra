"""Export-binding inventory for the rope analysis exports part.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast

from flext_infra import c, t


class _ExportBindingInventory:
    """Inventory one statement list's exports, definitions, and ``__all__``."""

    def __init__(self) -> None:
        """Initialize the empty inventory."""
        self.assignments: t.MutableSequenceOf[str] = []
        self.definitions: t.MutableSequenceOf[t.Pair[str, bool]] = []
        self.explicit_all = False

    def collect(self, statements: t.SequenceOf[ast.stmt]) -> None:
        """Inventory each statement in declaration order.

        Parameters:
            statements: The module or block statements to inventory.

        """
        for statement in statements:
            self._dispatch(statement)

    def _dispatch(self, statement: ast.stmt) -> None:
        """Route one statement to its inventory handler."""
        if isinstance(statement, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            self._define(statement)
        elif isinstance(statement, (ast.Import, ast.ImportFrom)):
            return
        elif isinstance(statement, ast.If):
            self._if(statement)
        elif isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
            self._collect_branches(statement)
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            self.collect(statement.body)
        elif isinstance(statement, (ast.Try, ast.TryStar)):
            self._try(statement)
        elif isinstance(statement, ast.Match):
            self._match(statement)
        else:
            self._assign(statement)

    def _define(
        self,
        statement: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        """Record one definition and whether it declares a class."""
        self.definitions.append((
            statement.name,
            isinstance(statement, ast.ClassDef),
        ))

    def _assign(self, statement: ast.stmt) -> None:
        """Record one assignment statement's bound names."""
        names = self._bound_statement_names(statement)
        if not names:
            return
        self.explicit_all = self.explicit_all or c.Infra.DUNDER_ALL in names
        self.assignments.extend(name for name in names if name != c.Infra.DUNDER_ALL)

    def _bound_statement_names(self, statement: ast.stmt) -> t.StrSequence:
        """Return the names one assignment statement binds.

        Returns:
            The resulting ``t.StrSequence``.

        """
        if isinstance(statement, ast.Assign):
            return tuple(
                name
                for target in statement.targets
                for name in self._bound_names(target)
            )
        if isinstance(statement, (ast.AnnAssign, ast.AugAssign)):
            return self._bound_names(statement.target)
        return ()

    def _if(self, statement: ast.If) -> None:
        """Inventory one conditional statement's statically executed branches."""
        if self._main_guard(statement):
            return
        self.collect(statement.body)
        self.collect(statement.orelse)

    def _collect_branches(
        self,
        statement: ast.For | ast.AsyncFor | ast.While,
    ) -> None:
        """Inventory one loop statement's body and else branch."""
        self.collect(statement.body)
        self.collect(statement.orelse)

    def _try(self, statement: ast.Try | ast.TryStar) -> None:
        """Inventory one try statement's handlers, else, and finally blocks."""
        self.collect(statement.body)
        for handler in statement.handlers:
            self.collect(handler.body)
        self.collect(statement.orelse)
        self.collect(statement.finalbody)

    def _match(self, statement: ast.Match) -> None:
        """Inventory one match statement's case bodies."""
        for case in statement.cases:
            self.collect(case.body)

    @staticmethod
    def _main_guard(statement: ast.If) -> bool:
        """Return whether one if statement is the ``__main__`` guard.

        Returns:
            Whether one if statement is the ``__main__`` guard.

        """
        test = statement.test
        sides = (
            (test.left, test.comparators[0])
            if isinstance(test, ast.Compare)
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
            else ()
        )
        names_in_test = {side.id for side in sides if isinstance(side, ast.Name)}
        values_in_test = {
            side.value for side in sides if isinstance(side, ast.Constant)
        }
        return names_in_test == {"__name__"} and values_in_test == {"__main__"}

    def _bound_names(self, target: ast.expr) -> t.StrSequence:
        """Return the names one assignment target binds.

        Returns:
            The resulting ``t.StrSequence``.

        """
        if isinstance(target, ast.Name):
            return (target.id,)
        if isinstance(target, (ast.List, ast.Tuple)):
            return tuple(
                name for element in target.elts for name in self._bound_names(element)
            )
        return ()
