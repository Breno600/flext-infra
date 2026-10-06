"""Config models base: composes every config family via MRO in dependency order.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._models import FlextInfraConfigModelsArtifact
from flext_infra._models import FlextInfraConfigModelsBeads
from flext_infra._models import FlextInfraConfigModelsContexts
from flext_infra._models import FlextInfraConfigModelsContract
from flext_infra._models import FlextInfraConfigModelsMake
from flext_infra._models import FlextInfraConfigModelsProvider
from flext_infra._models import FlextInfraConfigModelsRelease
from flext_infra._models import FlextInfraConfigModelsRender
from flext_infra._models import FlextInfraConfigModelsRoot
from flext_infra._models import FlextInfraConfigModelsScaffold
from flext_infra._models import FlextInfraConfigModelsStatic
from flext_infra._models import FlextInfraConfigModelsTemplates
from flext_infra._models import FlextInfraConfigModelsWorkspace


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
