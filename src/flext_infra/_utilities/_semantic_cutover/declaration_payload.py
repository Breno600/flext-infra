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
    def _class_ancestry(value: p.Infra.RopePyObject) -> t.SequenceOf[p.Infra.RopePyObject]:
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
        """Prove payload shape and real Pydantic ancestry, not base spelling."""
        if declaration.decorator_list or not any(
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and not node.target.id.startswith("_")
            for node in declaration.body
        ):
            return None
        if any(
            not isinstance(node, ast.AnnAssign | ast.Assign | ast.Pass)
            and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                     and isinstance(node.value.value, str))
            for node in declaration.body
        ):
            return None
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        resource = project.get_resource(path.relative_to(Path(project.root.real_path)).as_posix())
        module = project.get_pymodule(resource)
        scope = runtime.scope_at(module, runtime.source_offset(resource.read(), declaration),
                                 declaration_line=declaration.lineno)
        binding = scope.get_names().get(declaration.name)
        if binding is None or not FlextInfraUtilitiesRopeRuntimeTypes.abstract_class(binding.get_object()):
            return None
        ancestry = cls._class_ancestry(binding.get_object())
        base = project.get_module("pydantic").get_attribute("BaseModel").get_object()
        settings = project.get_module("pydantic_settings").get_attribute("BaseSettings").get_object()
        return binding if base in ancestry and settings not in ancestry else None


__all__: list[str] = ["FlextInfraUtilitiesDeclarationPayload"]
