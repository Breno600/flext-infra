"""Config models base: composes every config family via MRO in dependency order."""

from __future__ import annotations

from flext_infra._models._config.artifact import FlextInfraConfigModelsArtifact
from flext_infra._models._config.beads import FlextInfraConfigModelsBeads
from flext_infra._models._config.contexts import FlextInfraConfigModelsContexts
from flext_infra._models._config.contract import FlextInfraConfigModelsContract
from flext_infra._models._config.make import FlextInfraConfigModelsMake
from flext_infra._models._config.provider import FlextInfraConfigModelsProvider
from flext_infra._models._config.release import FlextInfraConfigModelsRelease
from flext_infra._models._config.render import FlextInfraConfigModelsRender
from flext_infra._models._config.root import FlextInfraConfigModelsRoot
from flext_infra._models._config.scaffold import FlextInfraConfigModelsScaffold
from flext_infra._models._config.static import FlextInfraConfigModelsStatic
from flext_infra._models._config.templates import FlextInfraConfigModelsTemplates
from flext_infra._models._config.workspace import FlextInfraConfigModelsWorkspace


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
