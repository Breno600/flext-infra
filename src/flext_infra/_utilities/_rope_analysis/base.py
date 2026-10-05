"""Composed rope analysis base joining the domain responsibility classes.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra._utilities._rope_analysis.asthelpers import (
    FlextInfraUtilitiesRopeAnalysisAstHelpers,
)
from flext_infra._utilities._rope_analysis.exports import (
    FlextInfraUtilitiesRopeAnalysisExports,
)
from flext_infra._utilities._rope_analysis.importstate import (
    FlextInfraUtilitiesRopeAnalysisImportState,
)
from flext_infra._utilities._rope_analysis.sourcescan import (
    FlextInfraUtilitiesRopeAnalysisSourceScan,
)

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesRopeAnalysisBase(
    FlextInfraUtilitiesRopeAnalysisAstHelpers,
    FlextInfraUtilitiesRopeAnalysisSourceScan,
    FlextInfraUtilitiesRopeAnalysisExports,
    FlextInfraUtilitiesRopeAnalysisImportState,
):
    """Rope-backed semantic analysis composed from its domain responsibilities."""


__all__: t.VariadicTuple[str] = ("FlextInfraUtilitiesRopeAnalysisBase",)
