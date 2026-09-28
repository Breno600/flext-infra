"""Domain models for flext-infra.

Defines data models and domain entities for infrastructure services including
configuration, validation results, and workspace state.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import m as cli_m

from flext_core import m

from ._models.base import FlextInfraModelsBase
from ._models.census import FlextInfraModelsCensus
from ._models.check import FlextInfraModelsCheck
from ._models.codegen import FlextInfraModelsCodegen
from ._models.codemod import FlextInfraModelsCodemod
from ._models.config import FlextInfraConfigModels
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
from ._models.rope_rules import FlextInfraModelsRopeRules
from ._models.scan import FlextInfraModelsScan
from ._models.testmon import FlextInfraModelsTestmon
from ._models.transformers import FlextInfraModelsTransformers
from ._models.validate import FlextInfraModelsCore
from ._models.workspace import FlextInfraModelsWorkspace
from ._models.worktree import FlextInfraModelsWorktree


class FlextInfraModels(m):
    """Merged model namespace for flext-infra domain objects."""

    # NOTE (multi-agent): keep CLI route contracts available as FlextInfraModels.Cli
    # for legacy facade usage from CLI service route declarations.
    Cli = cli_m.Cli

    class Infra(
        FlextInfraModelsCensus,
        FlextInfraModelsCheck,
        # NOTE (multi-agent, flext-wkii.17 / agent: codex): conform contracts are
        # isolated from the active detector work in _models/codegen.py while
        # remaining exposed through the single public m.Infra facade.
        FlextInfraConfigModels,
        FlextInfraModelsCodegen,
        FlextInfraModelsCodemod,
        FlextInfraModelsDeps,
        FlextInfraModelsDocs,
        # NOTE (multi-agent): enforcement/transformers model
        # facades added for the deep-FLEXT dataclass -> m.Infra migration.
        FlextInfraModelsEnforcement,
        FlextInfraModelsGates,
        FlextInfraModelsLayout,
        FlextInfraModelsPromoted,
        FlextInfraModelsRefactor,
        FlextInfraModelsRelease,
        FlextInfraModelsMixins,
        FlextInfraModelsTransformers,
        FlextInfraModelsWorkspace,
        # flext-wkii.17.26 (codex): all fix/codegen mutations share one typed
        # worktree transaction report rather than command-local backup shapes.
        FlextInfraModelsWorktree,
        FlextInfraModelsGit,
        FlextInfraModelsRope,
        FlextInfraModelsRopeMove,
        FlextInfraModelsRopeRules,
        FlextInfraModelsScan,
        FlextInfraModelsTestmon,
        FlextInfraModelsCore,
        FlextInfraModelsBase,
    ):
        """Infrastructure-domain models - all classes exposed directly."""


m = FlextInfraModels

__all__: list[str] = ["FlextInfraModels", "m"]
