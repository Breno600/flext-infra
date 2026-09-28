"""Workspace Python file iteration helpers.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from .iteration_directory import FlextInfraUtilitiesIterationDirectory
from .iteration_matching import FlextInfraUtilitiesIterationMatching
from .iteration_project import FlextInfraUtilitiesIterationProject
from .iteration_workspace import FlextInfraUtilitiesIterationWorkspace


class FlextInfraUtilitiesIteration(
    FlextInfraUtilitiesIterationMatching,
    FlextInfraUtilitiesIterationWorkspace,
    FlextInfraUtilitiesIterationDirectory,
    FlextInfraUtilitiesIterationProject,
):
    """Static helpers for discovering and iterating Python files in workspace."""


__all__: list[str] = ["FlextInfraUtilitiesIteration"]
