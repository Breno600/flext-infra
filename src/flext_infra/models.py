"""Domain models for flext-infra.

Defines data models and domain entities for infrastructure services including
configuration, validation results, and workspace state.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import FlextCliModels

from ._models._config import FlextInfraConfigModels
from ._models.base import FlextInfraModelsBase
from ._models.census import FlextInfraModelsCensus
from ._models.check import FlextInfraModelsCheck
from ._models.codegen import FlextInfraCodegen
from ._models.codemod import FlextInfraModelsCodemod
from ._models.deps import FlextInfraModelsDeps
from ._models.docs import FlextInfraModelsDocs
from ._models.enforcement import FlextInfraModelsEnforcement
from ._models.gates import FlextInfraModelsGates
from ._models.git import FlextInfraModelsGit
from ._models.layout import FlextInfraModelsLayout
from ._models.mixins import FlextInfraModelsMixins
from ._models.promoted import FlextInfraModelsPromoted
from ._models.refactor import FlextInfraModelsRefactor
from ._models.release import FlextInfraModelsRelease
from ._models.rope import FlextInfraModelsRope
from ._models.rope_move import FlextInfraModelsRopeMove
from ._models.scan import FlextInfraModelsScan
from ._models.settings import FlextInfraSettingsModels
from ._models.sonarcloud import FlextInfraModelsSonarcloud
from ._models.testmon import FlextInfraModelsTestmon
from ._models.transformers import FlextInfraModelsTransformers
from ._models.validate import FlextInfraModelsCore
from ._models.workspace import FlextInfraModelsWorkspace
from ._models.worktree import FlextInfraModelsWorktree


class FlextInfraModels(FlextCliModels):
    """Merged model namespace for flext-infra domain objects."""

    class Infra(
        FlextInfraModelsCensus,
        FlextInfraModelsCheck,
        FlextInfraConfigModels,
        FlextInfraCodegen,
        FlextInfraModelsCodemod,
        FlextInfraModelsDeps,
        FlextInfraModelsDocs,
        FlextInfraModelsEnforcement,
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
        FlextInfraSettingsModels,
        FlextInfraModelsCore,
        FlextInfraModelsBase,
    ):
        """Infrastructure-domain models - all classes exposed directly."""


m = FlextInfraModels

__all__: list[str] = ["FlextInfraModels", "m"]
