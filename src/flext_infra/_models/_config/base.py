"""Config models base: composes every config family via MRO in dependency order."""

from __future__ import annotations

from .artifact import FlextInfraConfigModelsArtifact
from .beads import FlextInfraConfigModelsBeads
from .contexts import FlextInfraConfigModelsContexts
from .contract import FlextInfraConfigModelsContract
from .make import FlextInfraConfigModelsMake
from .provider import FlextInfraConfigModelsProvider
from .release import FlextInfraConfigModelsRelease
from .render import FlextInfraConfigModelsRender
from .root import FlextInfraConfigModelsRoot
from .scaffold import FlextInfraConfigModelsScaffold
from .static import FlextInfraConfigModelsStatic
from .templates import FlextInfraConfigModelsTemplates
from .workspace import FlextInfraConfigModelsWorkspace


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
