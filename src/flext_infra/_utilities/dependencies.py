"""Dependency parsing and inspection helpers for flext-infra utilities.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities import (
    FlextInfraUtilitiesDependenciesGraphMixin,
    FlextInfraUtilitiesDependenciesInspectionMixin,
    FlextInfraUtilitiesDependenciesProfilesMixin,
    FlextInfraUtilitiesDependenciesVersionsMixin,
)


class FlextInfraUtilitiesDependencies(
    FlextInfraUtilitiesDependenciesInspectionMixin,
    FlextInfraUtilitiesDependenciesGraphMixin,
    FlextInfraUtilitiesDependenciesVersionsMixin,
    FlextInfraUtilitiesDependenciesProfilesMixin,
):
    """Static helpers for inspecting dependency declarations in pyproject payloads."""


__all__: list[str] = ["FlextInfraUtilitiesDependencies"]
