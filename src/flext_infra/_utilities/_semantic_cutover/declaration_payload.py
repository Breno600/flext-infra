"""Resolve declaration roles through the immutable Rope identity graph.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from pathlib import Path

from flext_infra import p, t
from flext_infra._utilities import (
    FlextInfraUtilitiesRopeRuntimeModules,
    FlextInfraUtilitiesRopeRuntimeTypes,
)


class FlextInfraUtilitiesDeclarationPayload:
    """Identify data-only payloads by ancestry, never a base-name heuristic."""

    @staticmethod
    def _class_ancestry(
        value: p.Infra.RopePyObject,
    ) -> t.SequenceOf[p.Infra.RopePyObject]:
        pending = [value]
        found: list[p.Infra.RopePyObject] = []
        while pending:
            current = pending.pop()
            if current in found:
                continue
            found.append(current)
            if FlextInfraUtilitiesRopeRuntimeTypes.abstract_class(current):
                pending.extend(current.get_superclasses())
        return found

    @classmethod
    def payload_declaration(
        cls,
        project: p.Infra.RopeProject,
        path: Path,
        declaration: ast.ClassDef,
    ) -> p.Infra.RopePyName | None:
        """Prove payload shape and real Pydantic ancestry, not base spelling.

        Returns:
            The resulting ``p.Infra.RopePyName | None``.
        """
        if declaration.decorator_list or not any(
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and not node.target.id.startswith("_")
            for node in declaration.body
        ):
            return None
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        resource = FlextInfraUtilitiesRopeRuntimeTypes.require_file_resource(
            project.get_resource(
                path.relative_to(Path(project.root.real_path)).as_posix(),
            ),
            path,
        )
        module = project.get_pymodule(resource)
        scope = runtime.scope_at(
            module,
            runtime.source_offset(resource.read(), declaration),
            declaration_line=declaration.lineno,
        )
        if not all(
            cls._payload_statement(project, scope, node) for node in declaration.body
        ):
            return None
        binding = scope.get_names().get(declaration.name)
        if binding is None or not FlextInfraUtilitiesRopeRuntimeTypes.abstract_class(
            binding.get_object(),
        ):
            return None
        if len(binding.get_object().get_superclasses()) != len(declaration.bases):
            return None
        ancestry = cls._class_ancestry(binding.get_object())
        base = project.get_module("pydantic").get_attribute("BaseModel").get_object()
        settings = (
            project
            .get_module("pydantic_settings")
            .get_attribute("BaseSettings")
            .get_object()
        )
        if base not in ancestry or settings in ancestry:
            return None
        payload = any(
            cls._payload_field(project, scope, node) for node in declaration.body
        )
        return binding if payload else None

    @staticmethod
    def _payload_field(
        project: p.Infra.RopeProject,
        scope: p.Infra.RopeScope,
        node: ast.stmt,
    ) -> bool:
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            return False
        annotation = (
            node.annotation.value
            if isinstance(node.annotation, ast.Subscript)
            else node.annotation
        )
        qualifier = FlextInfraUtilitiesRopeRuntimeModules.resolve_symbol(
            scope,
            annotation,
        )
        return node.target.id != "model_config" and not any(
            FlextInfraUtilitiesRopeRuntimeModules.same_name(
                project.get_module("typing").get_attribute(name),
                qualifier,
            )
            for name in ("ClassVar", "Final")
        )

    @classmethod
    def _payload_statement(
        cls,
        project: p.Infra.RopeProject,
        scope: p.Infra.RopeScope,
        node: ast.stmt,
    ) -> bool:
        if isinstance(node, ast.AnnAssign | ast.Assign | ast.Pass):
            return True
        if isinstance(node, ast.Expr):
            return isinstance(node.value, ast.Constant) and isinstance(
                node.value.value,
                str,
            )
        if not isinstance(node, ast.FunctionDef):
            return False
        known = False
        for decorator in node.decorator_list:
            expression = (
                decorator.func if isinstance(decorator, ast.Call) else decorator
            )
            identity = FlextInfraUtilitiesRopeRuntimeModules.resolve_symbol(
                scope,
                expression,
            )
            if any(
                FlextInfraUtilitiesRopeRuntimeModules.same_name(
                    project.get_module("pydantic").get_attribute(name),
                    identity,
                )
                for name in ("field_validator", "model_validator", "computed_field")
            ):
                known = True
            elif not cls._builtin_declaration_decorator(identity):
                return False
        return known

    @staticmethod
    def _builtin_declaration_decorator(identity: p.Infra.RopePyName | None) -> bool:
        if identity is None:
            return False
        value = identity.get_object()
        return isinstance(value, p.Infra.RopeBuiltinClass) and (
            value.builtin.__module__ == "builtins"
            and value.builtin.__qualname__
            in {"classmethod", "staticmethod", "property"}
        )


__all__: list[str] = ["FlextInfraUtilitiesDeclarationPayload"]
