"""Pyproject conform utility base joining its responsibility classes via MRO.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities._pyproject.document import FlextInfraUtilitiesPyprojectDocument
from flext_infra._utilities._pyproject.overlay import FlextInfraUtilitiesPyprojectOverlay
from flext_infra._utilities._pyproject.toml_phases import FlextInfraUtilitiesPyprojectTomlPhases


class FlextInfraUtilitiesPyprojectConformBase(
    FlextInfraUtilitiesPyprojectDocument,
    FlextInfraUtilitiesPyprojectOverlay,
    FlextInfraUtilitiesPyprojectTomlPhases,
):
    """Canonical pyproject conformance, overlay preservation, and TOML phases."""


__all__: list[str] = ["FlextInfraUtilitiesPyprojectConformBase"]
