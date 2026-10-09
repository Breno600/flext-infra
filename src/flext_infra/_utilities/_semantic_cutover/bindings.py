"""Shared lexical binding discovery for conservative semantic migrations.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesSemanticCutoverBindings:
    """Enumerate language bindings without guessing their runtime values."""

    @staticmethod
    def bound_identifiers(node: ast.AST) -> t.VariadicTuple[str]:
        """Include match, exception, import, type-parameter and scope targets.

        Returns:
            The resulting ``t.VariadicTuple[str]``.

        """
        match node:
            case ast.Name(id=name, ctx=ast.Store() | ast.Del()):
                return (name,)
            case (
                ast.arg(arg=name)
                | ast.FunctionDef(name=name)
                | ast.AsyncFunctionDef(name=name)
                | ast.ClassDef(name=name)
            ):
                return (name,)
            case (
                ast.ExceptHandler(name=str() as name)
                | ast.MatchAs(name=str() as name)
                | ast.MatchStar(name=str() as name)
                | ast.MatchMapping(rest=str() as name)
            ):
                return (name,)
            case (
                ast.TypeVar(name=name)
                | ast.ParamSpec(name=name)
                | ast.TypeVarTuple(name=name)
            ):
                return (name,)
            case ast.Global(names=names) | ast.Nonlocal(names=names):
                return tuple(names)
            case ast.Import(names=aliases):
                return tuple(
                    alias.asname or alias.name.split(".")[0] for alias in aliases
                )
            case ast.ImportFrom(names=aliases):
                return tuple(alias.asname or alias.name for alias in aliases)
            case _:
                return ()


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverBindings"]
