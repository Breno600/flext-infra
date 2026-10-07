"""Typed runtime boundary facade for Rope, which lacks typing metadata.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities import (
    FlextInfraUtilitiesRopeRuntimeModules,
    FlextInfraUtilitiesRopeRuntimeRefactors,
    FlextInfraUtilitiesRopeRuntimeTypes,
)


class FlextInfraUtilitiesRopeRuntime(
    FlextInfraUtilitiesRopeRuntimeModules,
    FlextInfraUtilitiesRopeRuntimeRefactors,
    FlextInfraUtilitiesRopeRuntimeTypes,
):
    """Compose typed Rope runtime boundary helpers."""


__all__: list[str] = ["FlextInfraUtilitiesRopeRuntime"]
