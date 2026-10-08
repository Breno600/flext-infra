"""Drop empty TYPE_CHECKING blocks from published sources.

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
