# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Models. Config package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._models._config.artifact import FlextInfraConfigModelsArtifact
    from flext_infra._models._config.base import FlextInfraConfigModels
    from flext_infra._models._config.beads import FlextInfraConfigModelsBeads
    from flext_infra._models._config.contexts import FlextInfraConfigModelsContexts
    from flext_infra._models._config.contract import FlextInfraConfigModelsContract
    from flext_infra._models._config.external_cache import (
        FlextInfraExternalCacheDirectorySpec,
    )
    from flext_infra._models._config.make import FlextInfraConfigModelsMake
    from flext_infra._models._config.make_clean import FlextInfraConfigModelsMakeClean
    from flext_infra._models._config.make_docs import FlextInfraConfigModelsMakeDocs
    from flext_infra._models._config.provider import FlextInfraConfigModelsProvider
    from flext_infra._models._config.release import FlextInfraConfigModelsRelease
    from flext_infra._models._config.render import FlextInfraConfigModelsRender
    from flext_infra._models._config.repository import FlextInfraConfigModelsRepository
    from flext_infra._models._config.root import FlextInfraConfigModelsRoot
    from flext_infra._models._config.scaffold import FlextInfraConfigModelsScaffold
    from flext_infra._models._config.static import FlextInfraConfigModelsStatic
    from flext_infra._models._config.templates import FlextInfraConfigModelsTemplates
    from flext_infra._models._config.workspace import FlextInfraConfigModelsWorkspace


__all__: tuple[str, ...] = (
    "FlextInfraConfigModels",
    "FlextInfraConfigModelsArtifact",
    "FlextInfraConfigModelsBeads",
    "FlextInfraConfigModelsContexts",
    "FlextInfraConfigModelsContract",
    "FlextInfraConfigModelsMake",
    "FlextInfraConfigModelsMakeClean",
    "FlextInfraConfigModelsMakeDocs",
    "FlextInfraConfigModelsProvider",
    "FlextInfraConfigModelsRelease",
    "FlextInfraConfigModelsRender",
    "FlextInfraConfigModelsRepository",
    "FlextInfraConfigModelsRoot",
    "FlextInfraConfigModelsScaffold",
    "FlextInfraConfigModelsStatic",
    "FlextInfraConfigModelsTemplates",
    "FlextInfraConfigModelsWorkspace",
    "FlextInfraExternalCacheDirectorySpec",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraConfigModels": ".base",
        "FlextInfraConfigModelsArtifact": ".artifact",
        "FlextInfraConfigModelsBeads": ".beads",
        "FlextInfraConfigModelsContexts": ".contexts",
        "FlextInfraConfigModelsContract": ".contract",
        "FlextInfraConfigModelsMake": ".make",
        "FlextInfraConfigModelsMakeClean": ".make_clean",
        "FlextInfraConfigModelsMakeDocs": ".make_docs",
        "FlextInfraConfigModelsProvider": ".provider",
        "FlextInfraConfigModelsRelease": ".release",
        "FlextInfraConfigModelsRender": ".render",
        "FlextInfraConfigModelsRepository": ".repository",
        "FlextInfraConfigModelsRoot": ".root",
        "FlextInfraConfigModelsScaffold": ".scaffold",
        "FlextInfraConfigModelsStatic": ".static",
        "FlextInfraConfigModelsTemplates": ".templates",
        "FlextInfraConfigModelsWorkspace": ".workspace",
        "FlextInfraExternalCacheDirectorySpec": ".external_cache",
    }),
    public_exports=__all__,
)
