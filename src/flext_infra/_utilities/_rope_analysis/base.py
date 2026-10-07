"""Composed rope analysis base joining the domain responsibility classes.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra import t
from flext_infra._utilities import (
    FlextInfraUtilitiesRopeAnalysisAstHelpers,
    FlextInfraUtilitiesRopeAnalysisExports,
    FlextInfraUtilitiesRopeAnalysisImportState,
    FlextInfraUtilitiesRopeAnalysisSourceScan,
)


class FlextInfraUtilitiesRopeAnalysisBase(
    FlextInfraUtilitiesRopeAnalysisAstHelpers,
    FlextInfraUtilitiesRopeAnalysisSourceScan,
    FlextInfraUtilitiesRopeAnalysisExports,
    FlextInfraUtilitiesRopeAnalysisImportState,
):
    """Rope-backed semantic analysis composed from its domain responsibilities."""


__all__: t.VariadicTuple[str] = ("FlextInfraUtilitiesRopeAnalysisBase",)
