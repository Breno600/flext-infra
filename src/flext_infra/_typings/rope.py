"""Rope-specific type aliases for flext-infra.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from ast import Import, ImportFrom
from collections.abc import Callable

from flext_core import t

from .._protocols.rope_runtime import FlextInfraProtocolsRopeRuntime


class FlextInfraTypesRope:
    """Rope type aliases — accessed via t.Infra.*."""

    type PythonImportNode = Import | ImportFrom

    type RopeProject = FlextInfraProtocolsRopeRuntime.RopeProject
    type RopeResource = FlextInfraProtocolsRopeRuntime.RopeResource
    type RopeLocation = FlextInfraProtocolsRopeRuntime.RopeLocation
    type RopePyModule = FlextInfraProtocolsRopeRuntime.RopePyModule
    type RopePyName = FlextInfraProtocolsRopeRuntime.RopePyName
    type RopeAssignedName = FlextInfraProtocolsRopeRuntime.RopeAssignedName
    type RopePyObject = FlextInfraProtocolsRopeRuntime.RopePyObject
    type RopeAstNode = FlextInfraProtocolsRopeRuntime.RopeAstNode
    type RopeScope = FlextInfraProtocolsRopeRuntime.RopeScope
    type RopeFromImport = FlextInfraProtocolsRopeRuntime.RopeFromImport
    type RopeNormalImport = FlextInfraProtocolsRopeRuntime.RopeNormalImport
    type RopeImportInfo = FlextInfraProtocolsRopeRuntime.RopeImportInfo
    type RopeImportStatement = FlextInfraProtocolsRopeRuntime.RopeImportStatement
    type RopeModuleImports = FlextInfraProtocolsRopeRuntime.RopeModuleImports
    type RopeChangeSet = FlextInfraProtocolsRopeRuntime.RopeChangeSet
    type RopeMoveGlobal = FlextInfraProtocolsRopeRuntime.RopeMoveGlobal
    type RopeOccurrence = FlextInfraProtocolsRopeRuntime.RopeOccurrence
    type RopeOccurrenceFinder = FlextInfraProtocolsRopeRuntime.RopeOccurrenceFinder

    type RopeTransformFn = Callable[
        [RopeProject, RopeResource], t.Pair[str, t.StrSequence]
    ]


__all__: list[str] = ["FlextInfraTypesRope"]
