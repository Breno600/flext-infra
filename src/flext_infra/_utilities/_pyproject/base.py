"""Pyproject conform utility base joining its responsibility classes via MRO."""

from __future__ import annotations

from .document import FlextInfraUtilitiesPyprojectDocument
from .overlay import FlextInfraUtilitiesPyprojectOverlay
from .toml_phases import FlextInfraUtilitiesPyprojectTomlPhases


class FlextInfraUtilitiesPyprojectConformBase(
    FlextInfraUtilitiesPyprojectDocument,
    FlextInfraUtilitiesPyprojectOverlay,
    FlextInfraUtilitiesPyprojectTomlPhases,
):
    """Canonical pyproject conformance, overlay preservation, and TOML phases."""


__all__: list[str] = ["FlextInfraUtilitiesPyprojectConformBase"]
