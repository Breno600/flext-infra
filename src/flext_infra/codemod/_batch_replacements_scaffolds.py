"""Dead type-only scaffold removal transformers for mod publication.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import override

import libcst as cst


class _DeadScaffold(cst.CSTTransformer):
    """Remove ``if TYPE_CHECKING:`` blocks whose body is only ``pass``."""

    @override
    def leave_If(
        self,
        original_node: cst.If,
        updated_node: cst.If,
    ) -> cst.If | cst.RemovalSentinel:
        test = updated_node.test
        body = updated_node.body
        if isinstance(test, cst.Name) and test.value == "TYPE_CHECKING":
            statements = (
                body.body
                if isinstance(
                    body,
                    cst.SimpleStatementSuite | cst.IndentedBlock,
                )
                else ()
            )
            if len(statements) == 1 and isinstance(
                statements[0],
                cst.SimpleStatementLine,
            ):
                inner = statements[0].body
                if len(inner) == 1 and isinstance(inner[0], cst.Pass):
                    return cst.RemoveFromParent()
        return updated_node


class _OrphanImport(cst.CSTTransformer):
    """Drop the ``TYPE_CHECKING`` name once its block is gone."""

    @override
    def leave_ImportFrom(
        self,
        original_node: cst.ImportFrom,
        updated_node: cst.ImportFrom,
    ) -> cst.ImportFrom | cst.RemovalSentinel:
        module = updated_node.module
        if not (isinstance(module, cst.Name) and module.value == "typing"):
            return updated_node
        names = updated_node.names
        if isinstance(names, cst.ImportStar):
            return updated_node
        kept = tuple(
            alias
            for alias in names
            if not (
                isinstance(alias.name, cst.Name) and alias.name.value == "TYPE_CHECKING"
            )
        )
        if len(kept) == len(names):
            return updated_node
        if not kept:
            return cst.RemoveFromParent()
        return updated_node.with_changes(names=kept)


__all__: list[str] = []
