"""Narrow untrusted model-class boundaries before required field access.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import libcst as cst
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor

from flext_infra._utilities._semantic_cutover.edits import (
    FlextInfraUtilitiesSemanticCutoverEdits,
)
from flext_infra._utilities._semantic_cutover.model_fields_bindings import (
    FlextInfraUtilitiesSemanticCutoverModelFieldsBindings,
)

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import m, p, t


class FlextInfraUtilitiesSemanticCutoverModelFields(
    FlextInfraUtilitiesSemanticCutoverEdits,
    FlextInfraUtilitiesSemanticCutoverModelFieldsBindings,
):
    """Keep existing invalid-input errors while proving model-class identity."""

    @classmethod
    def _plan_model_fields(
        cls,
        sources: t.MappingKV[Path, str],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Inspect all sources, including direct access emitted by older rules.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]``.

        """
        return cls._semantic_edits(cls._editable_sources(sources), cls._rewrite_fields)

    @classmethod
    def _rewrite_fields(cls, path: Path, source: str) -> t.Infra.TransformResult:
        tree = ast.parse(source, filename=str(path))
        replacements: list[t.Triple[int, int, str]] = []
        lines = source.splitlines(keepends=True)
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            replacements.extend(
                cls._function_field_replacements(path, function, lines),
            )
        if not replacements:
            return source, ()
        cls._require_unshadowed_guard(tree)
        for start, end, replacement in sorted(replacements, reverse=True):
            lines[start:end] = [replacement]
        context = CodemodContext()
        AddImportsVisitor.add_needed_import(context, "flext_core", "u")
        updated = (
            cst.parse_module("".join(lines)).visit(AddImportsVisitor(context)).code
        )
        return updated, ("narrowed untrusted model-class boundaries",)

    @classmethod
    def _function_field_replacements(
        cls,
        path: Path,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: t.SequenceOf[str],
    ) -> t.SequenceOf[t.Triple[int, int, str]]:
        """Plan the narrowed model-fields boundary of one function body.

        Returns:
            The resulting ``t.SequenceOf[t.Triple[int, int, str]]``.

        Raises:
            ValueError: If a model field guard has no complete source span.

        """
        untrusted = {
            arg.arg
            for arg in (
                *function.args.posonlyargs,
                *function.args.args,
                *function.args.kwonlyargs,
            )
            if isinstance(arg.annotation, ast.Name) and arg.annotation.id == "object"
        }
        replacements: list[t.Triple[int, int, str]] = []
        for index, statement in enumerate(function.body):
            receiver = cls._field_receiver(statement)
            if receiver not in untrusted or not isinstance(statement, ast.Assign):
                continue
            guard = function.body[index + 1] if index + 1 < len(function.body) else None
            target = statement.targets[0]
            if not isinstance(target, ast.Name):
                continue
            guard = cls._validated_field_boundary(
                path,
                function,
                statement,
                guard,
                target,
            )
            indent = lines[statement.lineno - 1][: statement.col_offset]
            comments = "".join(lines[statement.end_lineno : guard.lineno - 1])
            condition = (
                f"{indent}if (\n"
                f"{indent}    not isinstance({receiver}, type)\n"
                f"{indent}    or not u.model_type({receiver})\n"
                f"{indent}    or not {receiver}.model_fields\n"
                f"{indent}):\n"
            )
            test_end = guard.test.end_lineno
            if test_end is None:
                msg = (
                    f"model field guard has no complete source span in "
                    f"{path}:{statement.lineno}"
                )
                raise ValueError(msg)
            replacements.append((
                statement.lineno - 1,
                test_end,
                comments + condition,
            ))
        return replacements

    @classmethod
    def _validated_field_boundary(
        cls,
        path: Path,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        statement: ast.Assign,
        guard: ast.stmt | None,
        target: ast.Name,
    ) -> ast.If:
        """Require one complete, guarded, singly used model-fields boundary.

        Returns:
            The validated rejecting guard statement.

        Raises:
            TypeError: If the model field rejection is not an if statement.
            ValueError: If the boundary lacks a rejecting guard, carries
                additional uses, spans invalid source, or rebinds the
                receiver.

        """
        if not cls._rejecting_guard(guard, target.id):
            msg = (
                f"untrusted model_fields access lacks a rejecting "
                f"guard in {path}:{statement.lineno}"
            )
            raise ValueError(msg)
        if not isinstance(guard, ast.If):
            msg = "model field rejection must be an if statement"
            raise TypeError(msg)
        uses = {
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Name) and node.id == target.id
        }
        guarded_uses = {
            node
            for node in ast.walk(guard.test)
            if isinstance(node, ast.Name) and node.id == target.id
        }
        if uses != guarded_uses | {target}:
            msg = f"model_fields local has additional uses in {path}:{statement.lineno}"
            raise ValueError(msg)
        if statement.end_lineno is None or guard.test.end_lineno is None:
            msg = "model field boundary has no complete source span"
            raise ValueError(msg)
        if (
            statement.end_lineno >= guard.lineno
            or guard.body[0].lineno <= guard.test.end_lineno
        ):
            msg = (
                f"model field boundary requires separate indented "
                f"statements in {path}:{statement.lineno}"
            )
            raise ValueError(msg)
        receiver = cls._field_receiver(statement)
        if any(
            receiver in cls._bound_identifiers(node)
            for body in function.body
            for node in ast.walk(body)
        ):
            msg = f"model field receiver is rebound in {path}:{statement.lineno}"
            raise ValueError(msg)
        return guard

    @staticmethod
    def _field_receiver(statement: ast.stmt) -> str | None:
        """Identify a single field assignment without evaluating its receiver.

        Returns:
            The resulting ``str | None``.

        """
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            return None
        value = statement.value
        if isinstance(value, ast.Attribute) and value.attr == "model_fields":
            return value.value.id if isinstance(value.value, ast.Name) else None
        if not isinstance(value, ast.Call) or value.keywords:
            return None
        if not isinstance(value.func, ast.Name) or value.func.id != "getattr":
            return None
        return FlextInfraUtilitiesSemanticCutoverModelFields._getattr_fields_receiver(
            value,
        )

    @staticmethod
    def _getattr_fields_receiver(value: ast.Call) -> str | None:
        """Return the receiver of a ``getattr(x, "model_fields", ...)`` call.

        Returns:
            The resulting ``str | None``.

        """
        match value.args:
            case [ast.Name(id=receiver), ast.Constant(value="model_fields")]:
                return receiver
            case [
                ast.Name(id=receiver),
                ast.Constant(value="model_fields"),
                ast.Constant(),
            ]:
                return receiver
            case [
                ast.Name(id=receiver),
                ast.Constant(value="model_fields"),
                ast.Dict(keys=[]),
            ]:
                return receiver
            case _:
                return None

    @staticmethod
    def _rejecting_guard(statement: ast.stmt | None, target: str) -> bool:
        """Require exactly the original shape error and an unconditional raise.

        Returns:
            The resulting ``bool``.

        """
        if not isinstance(statement, ast.If) or statement.orelse:
            return False
        expected = ast.parse(
            f"not isinstance({target}, dict) or not {target}",
            mode="eval",
        ).body
        return (
            ast.dump(statement.test) == ast.dump(expected)
            and bool(statement.body)
            and isinstance(statement.body[-1], ast.Raise)
        )


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverModelFields"]
