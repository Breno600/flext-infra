"""Remove redundant inner namespace classes (ENFORCE-048).

An inner class whose first base is the enclosing class itself and whose body
declares nothing (``pass``, ``...`` or a docstring only) re-exposes a namespace
the parent already provides. Deleting it is behaviour-preserving.
"""

from __future__ import annotations

from typing import override

import libcst as cst

from flext_infra import t

from .rope_transformer import FlextInfraRopeTransformer


class FlextInfraRefactorMroRemover(FlextInfraRopeTransformer):
    """Delete empty inner classes that re-inherit their enclosing class."""

    _description = "remove redundant inner namespace classes"

    class _RedundantInnerRemover(cst.CSTTransformer):
        """libcst pass: track the class nesting and drop redundant inner classes."""

        def __init__(self) -> None:
            super().__init__()
            self._enclosing: list[str] = []
            self.removed: list[str] = []

        @override
        def visit_ClassDef(self, node: cst.ClassDef) -> bool:
            self._enclosing.append(node.name.value)
            return True

        @override
        def leave_ClassDef(
            self,
            original_node: cst.ClassDef,
            updated_node: cst.ClassDef,
        ) -> cst.BaseStatement | cst.RemovalSentinel:
            self._enclosing.pop()
            if not self._enclosing or not self._is_redundant(
                updated_node,
                self._enclosing[-1],
            ):
                return updated_node
            self.removed.append(f"{self._enclosing[-1]}.{updated_node.name.value}")
            return cst.RemoveFromParent()

        @override
        def leave_IndentedBlock(
            self,
            original_node: cst.IndentedBlock,
            updated_node: cst.IndentedBlock,
        ) -> cst.BaseSuite:
            # A body emptied by the removal above must stay valid Python.
            if updated_node.body:
                return updated_node
            return updated_node.with_changes(
                body=[cst.SimpleStatementLine(body=[cst.Pass()])],
            )

        @staticmethod
        def _is_redundant(node: cst.ClassDef, outer_name: str) -> bool:
            if not node.bases:
                return False
            first_base = node.bases[0].value
            if not isinstance(first_base, cst.Name) or first_base.value != outer_name:
                return False
            statements = (
                node.body.body
                if isinstance(node.body, cst.IndentedBlock)
                else (node.body,)
            )
            small: list[cst.BaseSmallStatement] = []
            for statement in statements:
                if not isinstance(
                    statement,
                    cst.SimpleStatementLine | cst.SimpleStatementSuite,
                ):
                    return False
                small.extend(statement.body)
            return all(
                isinstance(item, cst.Pass)
                or (
                    isinstance(item, cst.Expr)
                    and isinstance(item.value, cst.Ellipsis | cst.SimpleString)
                )
                for item in small
            )

    @override
    def apply_to_source(self, source: str) -> t.Infra.TransformResult:
        """Return ``source`` without its redundant inner namespace classes."""
        remover = self._RedundantInnerRemover()
        updated = cst.parse_module(source).visit(remover)
        for qualname in remover.removed:
            self._record_change(f"Removed redundant inner namespace class {qualname}")
        if not remover.removed:
            return source, list(self.changes)
        return updated.code, list(self.changes)


__all__: list[str] = ["FlextInfraRefactorMroRemover"]
