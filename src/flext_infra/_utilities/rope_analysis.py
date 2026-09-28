"""Semantic Rope analysis helpers, composed from private domain partials."""

from __future__ import annotations

from ._rope_analysis.base import FlextInfraUtilitiesRopeAnalysisBase


class FlextInfraUtilitiesRopeAnalysis(FlextInfraUtilitiesRopeAnalysisBase):
    """Rope-backed semantic analysis helpers."""


__all__: list[str] = ["FlextInfraUtilitiesRopeAnalysis"]
