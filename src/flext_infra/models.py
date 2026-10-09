"""Domain models for flext-infra.

Defines data models and domain entities for infrastructure services including
configuration, validation results, and workspace state.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import FlextCliModels

from flext_infra._models import (
    FlextInfraCodegen,
    FlextInfraConfigModels,
    FlextInfraModelsBase,
    FlextInfraModelsCensus,
    FlextInfraModelsCheck,
    FlextInfraModelsCodemod,
    FlextInfraModelsCore,
    FlextInfraModelsDeps,
    FlextInfraModelsDocs,
    FlextInfraModelsGates,
    FlextInfraModelsGit,
    FlextInfraModelsLayout,
    FlextInfraModelsMiseToolchain,
    FlextInfraModelsMixins,
    FlextInfraModelsPromoted,
    FlextInfraModelsRefactor,
    FlextInfraModelsRelease,
    FlextInfraModelsRope,
    FlextInfraModelsRopeMove,
    FlextInfraModelsScan,
    FlextInfraModelsSonarcloud,
    FlextInfraModelsTestmon,
    FlextInfraModelsTransformers,
    FlextInfraModelsWorkspace,
    FlextInfraModelsWorktree,
)


class FlextInfraModels(FlextCliModels):
    """Merged model namespace for flext-infra domain objects."""

    class Infra(
        FlextInfraModelsCensus,
        FlextInfraModelsCheck,
        FlextInfraConfigModels,
        # FlextInfraCodegen already linearizes CodegenRender and
        # CodegenToolchain (its MRO contains both): listing the ancestors
        # beside their own subclass makes the C3 merge inconsistent.
        FlextInfraCodegen,
        FlextInfraModelsCodemod,
        FlextInfraModelsDeps,
        FlextInfraModelsDocs,
        FlextInfraModelsGates,
        FlextInfraModelsLayout,
        FlextInfraModelsPromoted,
        FlextInfraModelsRefactor,
        FlextInfraModelsRelease,
        FlextInfraModelsMixins,
        FlextInfraModelsTransformers,
        FlextInfraModelsWorkspace,
        FlextInfraModelsWorktree,
        FlextInfraModelsGit,
        FlextInfraModelsRope,
        FlextInfraModelsRopeMove,
        FlextInfraModelsScan,
        FlextInfraModelsSonarcloud,
        FlextInfraModelsTestmon,
        FlextInfraModelsCore,
        FlextInfraModelsBase,
        FlextInfraModelsMiseToolchain,
    ):
        """Infrastructure-domain models - all classes exposed directly."""


m = FlextInfraModels

__all__: list[str] = ["FlextInfraModels", "m"]
