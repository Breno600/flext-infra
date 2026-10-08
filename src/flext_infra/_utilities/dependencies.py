"""Dependency parsing and inspection helpers for flext-infra utilities.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities._dependencies_graph import (
    FlextInfraUtilitiesDependenciesGraphMixin,
)
from flext_infra._utilities._dependencies_inspection import (
    FlextInfraUtilitiesDependenciesInspectionMixin,
)
from flext_infra._utilities._dependencies_profiles import (
    FlextInfraUtilitiesDependenciesProfilesMixin,
)
from flext_infra._utilities._dependencies_versions import (
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
