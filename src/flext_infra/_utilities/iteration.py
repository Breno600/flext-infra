"""Workspace Python file iteration helpers.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities.iteration_directory import (
    FlextInfraUtilitiesIterationDirectory,
)
from flext_infra._utilities.iteration_matching import (
    FlextInfraUtilitiesIterationMatching,
)
from flext_infra._utilities.iteration_workspace import (
    FlextInfraUtilitiesIterationWorkspace,
)


class FlextInfraUtilitiesIteration(
    FlextInfraUtilitiesIterationMatching,
    FlextInfraUtilitiesIterationWorkspace,
    FlextInfraUtilitiesIterationDirectory,
):
    """Static helpers for discovering and iterating Python files in workspace."""


__all__: list[str] = ["FlextInfraUtilitiesIteration"]
