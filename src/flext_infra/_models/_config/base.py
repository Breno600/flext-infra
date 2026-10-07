"""Config models base: composes every config family via MRO in dependency order.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._models import (
    FlextInfraConfigModelsArtifact,
    FlextInfraConfigModelsBeads,
    FlextInfraConfigModelsContexts,
    FlextInfraConfigModelsContract,
    FlextInfraConfigModelsMake,
    FlextInfraConfigModelsProvider,
    FlextInfraConfigModelsRelease,
    FlextInfraConfigModelsRender,
    FlextInfraConfigModelsRoot,
    FlextInfraConfigModelsScaffold,
    FlextInfraConfigModelsStatic,
    FlextInfraConfigModelsTemplates,
    FlextInfraConfigModelsWorkspace,
)


class FlextInfraConfigModels(
    FlextInfraConfigModelsContract,
    FlextInfraConfigModelsProvider,
    FlextInfraConfigModelsRender,
    FlextInfraConfigModelsRoot,
    FlextInfraConfigModelsScaffold,
    FlextInfraConfigModelsStatic,
    FlextInfraConfigModelsMake,
    FlextInfraConfigModelsBeads,
    FlextInfraConfigModelsTemplates,
    FlextInfraConfigModelsContexts,
    FlextInfraConfigModelsWorkspace,
    FlextInfraConfigModelsRelease,
    FlextInfraConfigModelsArtifact,
):
    """Every config family joined in dependency order, foundations first."""
