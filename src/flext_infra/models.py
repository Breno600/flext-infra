"""Domain models for flext-infra.

Defines data models and domain entities for infrastructure services including
configuration, validation results, and workspace state.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import FlextCliModels

from flext_infra._models import FlextInfraCodegen
from flext_infra._models import FlextInfraConfigModels
from flext_infra._models import FlextInfraModelsBase
from flext_infra._models import FlextInfraModelsCensus
from flext_infra._models import FlextInfraModelsCheck
from flext_infra._models import FlextInfraModelsCodemod
from flext_infra._models import FlextInfraModelsDeps
from flext_infra._models import FlextInfraModelsDocs
from flext_infra._models import FlextInfraModelsGates
from flext_infra._models import FlextInfraModelsGit
from flext_infra._models import FlextInfraModelsLayout
from flext_infra._models import FlextInfraModelsMiseToolchain
from flext_infra._models import FlextInfraModelsMixins
from flext_infra._models import FlextInfraModelsPromoted
from flext_infra._models import FlextInfraModelsRefactor
from flext_infra._models import FlextInfraModelsRelease
from flext_infra._models import FlextInfraModelsRope
from flext_infra._models import FlextInfraModelsRopeMove
from flext_infra._models import FlextInfraModelsScan
from flext_infra._models import FlextInfraModelsSonarcloud
from flext_infra._models import FlextInfraModelsTestmon
from flext_infra._models import FlextInfraModelsTransformers
from flext_infra._models import FlextInfraModelsCore
from flext_infra._models import FlextInfraModelsWorkspace
from flext_infra._models import FlextInfraModelsWorktree


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
