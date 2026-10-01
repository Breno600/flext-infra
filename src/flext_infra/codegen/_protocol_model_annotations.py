"""Render concrete model annotations as structural protocol annotations.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from collections import abc
from enum import Enum
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from types import UnionType
from typing import (
    Annotated,
    ClassVar,
    ForwardRef,
    Literal,
    TypeAliasType,
    get_args,
    get_origin,
)

from flext_infra import m, p, t


class FlextInfraCodegenProtocolModelAnnotations:
    """Map validated runtime model types to public protocol-facade types."""

    _ORIGINS: ClassVar[t.MappingKV[p.AttributeProbe, str]] = {
        list: "list",
        tuple: "tuple",
        dict: "dict",
        set: "set",
        frozenset: "frozenset",
        type: "type",
        abc.Sequence: "Sequence",
        abc.Mapping: "Mapping",
        abc.MutableSequence: "MutableSequence",
        abc.MutableMapping: "MutableMapping",
        abc.Set: "AbstractSet",
        abc.MutableSet: "MutableSet",
        abc.Iterable: "Iterable",
        abc.Iterator: "Iterator",
        abc.Callable: "Callable",
    }
    _ANNOTATED_PREFIX = "Annotated["
    _BANNED = frozenset({"Any", "object", "typing.Any"})
    _TOKEN_RE: ClassVar[re.Pattern[str]] = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")

    class ProtocolModelTarget(m.FrozenModel):
        """The member namespace the generator renders protocols for."""

        package_name: str = m.Field(
            description="Member package name (pyproject name, underscore form)."
        )
        facade_container: str = m.Field(
            description="CamelCase member container prefix (for example AiHub)."
        )
        package_module_prefix: str = m.Field(
            description="Module prefix naming member-owned models."
        )
        protocol_ref_prefix: str = m.Field(
            description="Public protocols facade reference (for example p.AiHub)."
        )
        models_facade_name: str = m.Field(
            description="Single-letter models facade alias used in sources."
        )
        facade_probes: t.VariadicTuple[t.Pair[str, str]] = m.Field(
            description=(
                "Alias to importable facade object paths probed when mapping "
                "identical runtime types to public names."
            )
        )

        @property
        def model_ref_re(self) -> re.Pattern[str]:
            """Forward-ref pattern naming this member's model containers."""
            container = re.escape(self.facade_container)
            return re.compile(rf"{container}(?:Config)?Models\w*\.([A-Z]\w*)")

    @classmethod
    def render(
        cls, annotation: t.TypeHintSpecifier | None, target: ProtocolModelTarget
    ) -> str:
        """Render one field/property type without exposing a concrete model."""
        if isinstance(annotation, ForwardRef):
            return cls._render_forward(annotation.__forward_arg__, target)
        if isinstance(annotation, str):
            return cls._render_forward(annotation, target)
        if annotation is None or annotation is type(None):
            return "None"
        if isinstance(annotation, TypeAliasType):
            return cls.render(annotation.__value__, target)
        origin = get_origin(annotation)
        arguments = get_args(annotation)
        if isinstance(origin, TypeAliasType):
            bindings = dict(zip(origin.__type_params__, arguments, strict=True))
            value = origin.__value__
            for parameter, argument in bindings.items():
                if value is parameter:
                    return cls.render(argument, target)
            parameters = getattr(value, "__parameters__", ())
            if parameters:
                value = value[tuple(bindings[parameter] for parameter in parameters)]
            return cls.render(value, target)
        if origin is Annotated:
            return cls.render(arguments[0], target)
        if origin is UnionType:
            return " | ".join(cls.render(argument, target) for argument in arguments)
        if origin is Literal:
            return f"Literal[{', '.join(repr(argument) for argument in arguments)}]"
        if origin is abc.Callable:
            parameters, return_type = arguments
            if parameters is Ellipsis:
                rendered_parameters = "..."
            elif isinstance(parameters, list):
                rendered_parameters = ", ".join(
                    cls.render(parameter, target) for parameter in parameters
                )
            else:
                msg = f"unsupported Callable parameters: {parameters!r}"
                raise TypeError(msg)
            rendered = cls.render(return_type, target)
            return f"Callable[[{rendered_parameters}], {rendered}]"
        if origin is not None:
            rendered_origin = cls._ORIGINS.get(origin)
            if rendered_origin is None:
                rendered_origin = cls._facade_name(origin, target)
            if rendered_origin is None:
                msg = f"unsupported protocol annotation origin: {origin!r}"
                raise TypeError(msg)
            rendered_arguments = ", ".join(
                "..." if argument is Ellipsis else cls.render(argument, target)
                for argument in arguments
            )
            return (
                f"{rendered_origin}[{rendered_arguments}]"
                if rendered_arguments
                else rendered_origin
            )
        if isinstance(annotation, type):
            if issubclass(annotation, m.BaseModel):
                if annotation.__module__.startswith(target.package_module_prefix):
                    return f"{target.protocol_ref_prefix}.{annotation.__name__}"
                facade_name = cls._facade_name(annotation, target)
                if facade_name is not None:
                    return facade_name
            if issubclass(annotation, Enum):
                facade_name = cls._facade_name(annotation, target)
                if facade_name is not None:
                    return facade_name
            if annotation.__module__ in {"builtins", "datetime", "uuid"}:
                return cls._validate(annotation.__name__)
            if annotation is Path:
                return "Path"
        facade_name = cls._facade_name(annotation, target)
        if facade_name is not None:
            return facade_name
        msg = f"unsupported protocol annotation: {annotation!r}"
        raise TypeError(msg)

    @classmethod
    def _facade_name(
        cls, value: p.AttributeProbe, target: ProtocolModelTarget
    ) -> str | None:
        """Return the existing public facade path for an identical runtime type."""
        for prefix, probe in target.facade_probes:
            module_path, _, attribute = probe.rpartition(".")
            # A member without that facade surface cannot hold the value;
            # probing continues with the next surface. A surface that exists
            # but fails to import is a real defect and escapes.
            package = module_path.partition(".")[0]
            if find_spec(package) is None or find_spec(module_path) is None:
                continue
            module = import_module(module_path)
            facade = getattr(module, attribute, None)
            if facade is None:
                continue
            for name in dir(facade):
                if getattr(facade, name, None) is value:
                    return f"{prefix}.{name}"
        return None

    @classmethod
    def _render_forward(cls, annotation: str, target: ProtocolModelTarget) -> str:
        """Normalize a postponed source annotation without evaluating Field data."""
        rendered = annotation.strip()
        if rendered.startswith(cls._ANNOTATED_PREFIX):
            rendered = cls._first_annotated_argument(rendered)
        rendered = target.model_ref_re.sub(
            rf"{target.protocol_ref_prefix}.\1", rendered
        )
        rendered = rendered.replace(
            target.models_facade_name, target.protocol_ref_prefix
        )
        return cls._validate(rendered)

    @classmethod
    def _first_annotated_argument(cls, annotation: str) -> str:
        """Extract the first top-level argument from ``Annotated[...]``."""
        content = annotation[len(cls._ANNOTATED_PREFIX) : -1]
        depth = 0
        for index, character in enumerate(content):
            if character in "([{":
                depth += 1
            elif character in ")]}":
                depth -= 1
            elif character == "," and depth == 0:
                return content[:index].strip()
        msg = f"malformed Annotated protocol field: {annotation}"
        raise ValueError(msg)

    @classmethod
    def _validate(cls, rendered: str) -> str:
        """Reject escape-hatch types from generated public contracts."""
        tokens = frozenset(cls._TOKEN_RE.findall(rendered))
        banned = tokens.intersection(cls._BANNED)
        if banned:
            msg = f"forbidden generated protocol annotation: {sorted(banned)}"
            raise TypeError(msg)
        return rendered


__all__: list[str] = ["FlextInfraCodegenProtocolModelAnnotations"]
