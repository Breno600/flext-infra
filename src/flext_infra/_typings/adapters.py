"""Centralized TypeAdapter instances for flext-infra.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import Annotated, ClassVar

from flext_cli import t

from flext_core import m, u


class FlextInfraTypesAdapters:
    """SSOT TypeAdapter singletons for infrastructure validation."""

    # This alias removes the constants-to-typings cycle.
    INFRA_MAPPING_ADAPTER: ClassVar[m.TypeAdapter[t.JsonMapping]] = (
        t.Cli.JSON_MAPPING_ADAPTER
    )
    "Validates t.MappingKV[str, InfraValue] - the most common infra adapter."

    MUTABLE_INFRA_MAPPING_ADAPTER: ClassVar[
        m.TypeAdapter[MutableMapping[str, t.JsonValue]]
    ] = u.type_adapter(MutableMapping[str, t.JsonValue])
    "Validates MutableMapping[str, InfraValue] for in-place mutation."

    STR_MAPPING_ADAPTER: ClassVar[m.TypeAdapter[t.StrMapping]] = u.type_adapter(
        Annotated[t.MappingKV[str, str], None],
    )
    "Validates t.StrMapping."

    CONTAINER_MAPPING_ADAPTER: ClassVar[
        m.TypeAdapter[t.MappingKV[str, t.Scalar | Path]]
    ] = u.type_adapter(Annotated[t.MappingKV[str, t.Scalar | Path], None])
    "Validates flat scalar/path mappings (no nested containers)."

    INFRA_SEQ_ADAPTER: ClassVar[m.TypeAdapter[t.JsonList]] = t.Cli.JSON_LIST_ADAPTER
    "Validates t.SequenceOf[InfraValue]."

    CONTAINER_DICT_SEQ_ADAPTER: ClassVar[m.TypeAdapter[t.SequenceOf[t.JsonMapping]]] = (
        u.type_adapter(Annotated[t.SequenceOf[t.JsonMapping], None])
    )
    "Validates t.SequenceOf[ContainerDict]."

    STR_SEQ_ADAPTER: ClassVar[m.TypeAdapter[t.StrSequence]] = u.type_adapter(
        Annotated[t.SequenceOf[str], None],
    )
    "Validates t.StrSequence."

    STR_ADAPTER: ClassVar[m.TypeAdapter[str]] = u.type_adapter(str)
    "Validates one string at boundaries whose upstream stubs expose Any."

    BOOL_ADAPTER: ClassVar[m.TypeAdapter[bool]] = u.type_adapter(bool)
    "Validates one boolean at boundaries whose upstream stubs expose Any."

    PATH_ADAPTER: ClassVar[m.TypeAdapter[Path]] = u.type_adapter(Path)
    "Validates one filesystem path at boundaries whose upstream stubs expose Any."


__all__: list[str] = ["FlextInfraTypesAdapters"]
