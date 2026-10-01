"""Composed rope analysis base joining the domain responsibility classes."""

from __future__ import annotations

from flext_infra import t

from .asthelpers import FlextInfraUtilitiesRopeAnalysisAstHelpers
from .exports import FlextInfraUtilitiesRopeAnalysisExports
from .importstate import FlextInfraUtilitiesRopeAnalysisImportState
from .sourcescan import FlextInfraUtilitiesRopeAnalysisSourceScan


class FlextInfraUtilitiesRopeAnalysisBase(
    FlextInfraUtilitiesRopeAnalysisAstHelpers,
    FlextInfraUtilitiesRopeAnalysisSourceScan,
    FlextInfraUtilitiesRopeAnalysisExports,
    FlextInfraUtilitiesRopeAnalysisImportState,
):
    """Rope-backed semantic analysis composed from its domain responsibilities."""


__all__: t.VariadicTuple[str] = ("FlextInfraUtilitiesRopeAnalysisBase",)
