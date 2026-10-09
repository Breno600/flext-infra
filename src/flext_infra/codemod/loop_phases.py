"""Mod loop repair phases invoked as callbacks of the joint fixed point.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

from flext_infra.codemod._loop_phase_accessor_rename import (
    FlextInfraAccessorRenamePhase,
)
from flext_infra.codemod._loop_phase_import_normalization import (
    FlextInfraImportNormalizationPhase,
)
from flext_infra.codemod._loop_phase_namespace_relocation import (
    FlextInfraNamespaceRelocationPhase,
)

__all__: list[str] = [
    "FlextInfraAccessorRenamePhase",
    "FlextInfraImportNormalizationPhase",
    "FlextInfraNamespaceRelocationPhase",
]
