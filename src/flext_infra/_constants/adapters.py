"""Centralized TypeAdapter constants for flext-infra.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import ClassVar

from pydantic import TypeAdapter
from flext_cli import t


class FlextInfraConstantsAdapters:
    """SSOT TypeAdapter singletons for infrastructure validation."""

    # NOTE (multi-agent): flext-i6nq.10 removes the constants-to-typings cycle.
    INFRA_MAPPING_ADAPTER: ClassVar[TypeAdapter[t.JsonMapping]] = (
        t.Cli.JSON_MAPPING_ADAPTER
    )
    "Validates t.MappingKV[str, InfraValue] - the most common infra adapter."

    MUTABLE_INFRA_MAPPING_ADAPTER: ClassVar[
        TypeAdapter[MutableMapping[str, t.JsonValue]]
    ] = TypeAdapter(MutableMapping[str, t.JsonValue])
    "Validates MutableMapping[str, InfraValue] for in-place mutation."

    STR_MAPPING_ADAPTER: ClassVar[TypeAdapter[t.StrMapping]] = TypeAdapter(
        t.StrMapping
    )
    "Validates t.StrMapping."

    CONTAINER_MAPPING_ADAPTER: ClassVar[
        TypeAdapter[t.MappingKV[str, t.Scalar | Path]]
    ] = TypeAdapter(t.MappingKV[str, t.Scalar | Path])
    "Validates flat scalar/path mappings (no nested containers)."

    INFRA_SEQ_ADAPTER: ClassVar[TypeAdapter[t.JsonList]] = t.Cli.JSON_LIST_ADAPTER
    "Validates t.SequenceOf[InfraValue]."

    CONTAINER_DICT_SEQ_ADAPTER: ClassVar[TypeAdapter[t.SequenceOf[t.JsonMapping]]] = (
        TypeAdapter(t.SequenceOf[t.JsonMapping])
    )
    "Validates t.SequenceOf[ContainerDict]."

    STR_SEQ_ADAPTER: ClassVar[TypeAdapter[t.StrSequence]] = TypeAdapter(
        t.StrSequence
    )
    "Validates t.StrSequence."

    STR_ADAPTER: ClassVar[TypeAdapter[str]] = TypeAdapter(str)
    "Validates one string at boundaries whose upstream stubs expose Any."

    BOOL_ADAPTER: ClassVar[TypeAdapter[bool]] = TypeAdapter(bool)
    "Validates one boolean at boundaries whose upstream stubs expose Any."

    PATH_ADAPTER: ClassVar[TypeAdapter[Path]] = TypeAdapter(Path)
    "Validates one filesystem path at boundaries whose upstream stubs expose Any."


__all__: list[str] = ["FlextInfraConstantsAdapters"]
