"""Render structural protocol classes for the generated ``p`` layer.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from inspect import getattr_static
from types import FunctionType

from flext_infra import m, t

from ._protocol_model_annotations import FlextInfraCodegenProtocolModelAnnotations

Target = FlextInfraCodegenProtocolModelAnnotations.ProtocolModelTarget
LineBudget = 170
MinimalBodyLines = 3


class FlextInfraCodegenProtocolModelRender:
    """Render structural protocols and their generated-file modules."""

    Annotations = FlextInfraCodegenProtocolModelAnnotations

    @classmethod
    def render_member_modules(
        cls, models: t.SequenceOf[type[m.BaseModel]], target: Target
    ) -> t.MappingKV[str, str]:
        """Render every generated module (path -> content) for a member."""
        grouped: dict[str, list[type[m.BaseModel]]] = {}
        for model in sorted(models, key=cls._model_sort_key):
            grouped.setdefault(cls._owner_name(model), []).append(model)
        modules: dict[str, str] = {}
        part_names: list[str] = []
        for owner, owner_models in sorted(grouped.items()):
            for index, chunk in enumerate(cls._chunks(owner_models, target), 1):
                part_name = cls._part_name(owner, index)
                part_names.append(part_name)
                modules[cls._module_path(target, owner, index)] = (
                    cls._module_header(target)
                    + f"class {part_name}:\n"
                    + cls._indent(chunk)
                )
        modules[cls._aggregate_path(target)] = cls._render_aggregate(part_names, target)
        return modules

    @classmethod
    def _chunks(
        cls, models: t.SequenceOf[type[m.BaseModel]], target: Target
    ) -> t.SequenceOf[str]:
        """Split one owner's protocol bodies under the line budget."""
        chunks: list[str] = []
        current = ""
        for model in models:
            body = cls._render_protocol(model, target)
            if current and current.count("\n") + body.count("\n") > LineBudget:
                chunks.append(current)
                current = ""
            current += body
        if current:
            chunks.append(current)
        return chunks

    @classmethod
    def _render_protocol(cls, model: type[m.BaseModel], target: Target) -> str:
        """Render one runtime-checkable structural protocol for ``model``."""
        lines = [
            "@runtime_checkable",
            f"class {model.__name__}(Protocol):",
            '    """Structural contract generated from a validated model."""',
            "",
        ]
        for name, field in model.model_fields.items():
            rendered = cls._render_annotation(
                name, getattr(field, "annotation", None), target
            )
            lines.extend((
                "    @property",
                f"    def {name}(self) -> {rendered}:",
                "        ...",
                "",
            ))
        for name in cls._owned_public_properties(model):
            rendered = cls._render_owned(name, model, target)
            lines.extend((
                "    @property",
                f"    def {name}(self) -> {rendered}:",
                "        ...",
                "",
            ))
        while lines and not lines[-1]:
            lines.pop()
        if len(lines) <= MinimalBodyLines:
            lines.append("    pass")
        return "\n".join(lines) + "\n\n"

    @classmethod
    def _render_annotation(
        cls, name: str, annotation: t.TypeHintSpecifier | None, target: Target
    ) -> str:
        """Render one pydantic field annotation through the facade mapper."""
        if annotation is None:
            msg = f"field {name!r} has no annotation; close it at the model owner"
            raise TypeError(msg)
        return cls.Annotations.render(annotation, target)

    @classmethod
    def _owned_public_properties(cls, model: type[m.BaseModel]) -> list[str]:
        """Return property/function names owned by the model itself."""
        names: list[str] = []
        for name, value in vars(model).items():
            if name.startswith(("_", "model_")):
                continue
            if isinstance(value, (property, FunctionType)):
                names.append(name)
        return sorted(names)

    @classmethod
    def _render_owned(cls, name: str, model: type[m.BaseModel], target: Target) -> str:
        """Render one owned property return annotation, failing when missing."""
        descriptor = getattr_static(model, name)
        getter = descriptor.fget if isinstance(descriptor, property) else descriptor
        if getter is None:
            msg = f"owned member {name!r} has no getter on {model.__name__}"
            raise TypeError(msg)
        annotations: dict[str, t.TypeHintSpecifier | None] = getattr(
            getter, "__annotations__", {}
        )
        annotation = annotations.get("return")
        if annotation is None:
            msg = f"property {name!r} on {model.__name__} lacks a return annotation"
            raise TypeError(msg)
        return cls.Annotations.render(annotation, target)

    @classmethod
    def _render_aggregate(cls, part_names: t.SequenceOf[str], target: Target) -> str:
        """Render the aggregate owner composing every generated part."""
        container = f"{target.facade_container}ProtocolsGeneratedModels"
        lines = [cls._module_header(target), f"class {container}:", ""]
        lines.extend(f"    {name}" for name in sorted(part_names))
        lines.append("")
        return "\n".join(lines)

    @classmethod
    def _part_name(cls, owner: str, index: int) -> str:
        """Return the PascalCase owner-part class name."""
        camel = "".join(
            part.capitalize() for part in owner.replace("-", "_").split("_")
        )
        return f"{camel}ProtocolsGeneratedPart{index:02d}"

    @classmethod
    def _module_path(cls, target: Target, owner: str, index: int) -> str:
        """Return the generated part module path for an owner chunk."""
        return (
            f"src/{target.package_name}/_protocols/"
            f"generated_models_{owner}_{index:02d}.py"
        )

    @classmethod
    def _aggregate_path(cls, target: Target) -> str:
        """Return the generated aggregate module path."""
        return f"src/{target.package_name}/_protocols/generated_models.py"

    @classmethod
    def _owner_name(cls, model: type[m.BaseModel]) -> str:
        """Return the owning module's short name for grouping."""
        return model.__module__.rsplit(".", 1)[-1]

    @classmethod
    def _model_sort_key(cls, model: type[m.BaseModel]) -> str:
        """Sort models by owner then declared name for stable output."""
        return f"{model.__module__}.{model.__name__}"

    @classmethod
    def _indent(cls, body: str) -> str:
        """Indent rendered protocol bodies into their owner class."""
        return (
            "\n".join(f"    {line}" if line else line for line in body.splitlines())
            + "\n"
        )

    @staticmethod
    def _module_header(target: Target) -> str:
        """Return the generated-file header with regeneration instruction."""
        return (
            "# AUTO-GENERATED FILE — Regenerate with: make gen\n"
            "# Structural protocols assembled from the member's validated models.\n"
            "from __future__ import annotations\n\n"
            "from typing import TYPE_CHECKING, Protocol, runtime_checkable\n\n"
            "if TYPE_CHECKING:\n"
            f"    from {target.package_name} import p\n\n"
        )


__all__: list[str] = ["FlextInfraCodegenProtocolModelRender"]
