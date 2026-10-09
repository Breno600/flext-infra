"""Typed requests for Rope-backed class moves.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar

from flext_cli import m

from flext_infra import t
from flext_infra._models import FlextInfraModelsMixins as mm


class FlextInfraModelsRopeMove:
    """Data-only contracts for semantic class relocation."""

    class ClassMoveRequest(mm.PositiveLineMixin, m.ArbitraryTypesModel):
        """One exact, prevalidated Rope class-move request."""

        rope_project: Annotated[
            t.Infra.RopeProject,
            m.Field(description="Active Rope project that owns both files"),
        ]
        source_file: Annotated[
            Path,
            m.Field(description="Existing module that declares the class"),
        ]
        target_file: Annotated[
            Path,
            m.Field(description="Canonical destination module for the class"),
        ]
        class_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Top-level class selected by Rope"),
        ]
        apply: Annotated[
            bool,
            m.Field(description="Whether to execute the validated move"),
        ]

    class ResolvedClassMove(m.ArbitraryTypesModel):
        """One class move whose Rope identities are resolved before any rewrite."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        request: Annotated[
            FlextInfraModelsRopeMove.ClassMoveRequest,
            m.Field(description="Prevalidated class-move request being planned"),
        ]
        declaration: Annotated[
            t.Infra.RopePyName,
            m.Field(description="Original Rope identity of the moved declaration"),
        ]
        origin_module: Annotated[
            str,
            m.Field(description="Rope module declaring the class before the move"),
        ]
        target_module: Annotated[
            str,
            m.Field(description="Rope module receiving the moved class"),
        ]


__all__: list[str] = ["FlextInfraModelsRopeMove"]
