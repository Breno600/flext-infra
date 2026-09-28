"""Typed runtime boundary facade for Rope, which lacks typing metadata."""

from __future__ import annotations

from .rope_runtime_modules import FlextInfraUtilitiesRopeRuntimeModules
from .rope_runtime_refactors import FlextInfraUtilitiesRopeRuntimeRefactors
from .rope_runtime_types import FlextInfraUtilitiesRopeRuntimeTypes


class FlextInfraUtilitiesRopeRuntime(
    FlextInfraUtilitiesRopeRuntimeModules,
    FlextInfraUtilitiesRopeRuntimeRefactors,
    FlextInfraUtilitiesRopeRuntimeTypes,
):
    """Compose typed Rope runtime boundary helpers."""


__all__: list[str] = ["FlextInfraUtilitiesRopeRuntime"]
