"""Shared catalog-backed enforcement rule engine."""

from __future__ import annotations

from .metadata import FlextInfraEnforcementMetadata
from .selection import FlextInfraEnforcementSelection


class FlextInfraEnforcementEngine(
    FlextInfraEnforcementMetadata, FlextInfraEnforcementSelection
):
    """Single SSOT-backed selection and rendering for catalog-driven census."""


__all__: list[str] = ["FlextInfraEnforcementEngine"]
