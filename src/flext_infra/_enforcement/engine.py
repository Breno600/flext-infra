"""Shared catalog-backed enforcement rule engine."""

from __future__ import annotations

from .collection_sources import FlextInfraEnforcementSourceCollectors


class FlextInfraEnforcementEngine(FlextInfraEnforcementSourceCollectors):
    """Single SSOT-backed collector for validation, census, and fix flows."""


__all__: list[str] = ["FlextInfraEnforcementEngine"]
