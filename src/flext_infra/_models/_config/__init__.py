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
    from flext_infra._models import FlextInfraConfigModelsArtifact
    from flext_infra._models import FlextInfraConfigModels
    from flext_infra._models import FlextInfraConfigModelsBeads
    from flext_infra._models import FlextInfraConfigModelsContexts
    from flext_infra._models import FlextInfraConfigModelsContract
    from flext_infra._models import FlextInfraExternalCacheDirectorySpec
    from flext_infra._models import FlextInfraConfigModelsMake
    from flext_infra._models import FlextInfraConfigModelsProvider
    from flext_infra._models import FlextInfraConfigModelsRelease
    from flext_infra._models import FlextInfraConfigModelsRender
    from flext_infra._models import FlextInfraConfigModelsRepository
    from flext_infra._models import FlextInfraConfigModelsRoot
    from flext_infra._models import FlextInfraConfigModelsScaffold
    from flext_infra._models import FlextInfraConfigModelsStatic
    from flext_infra._models import FlextInfraConfigModelsTemplates
    from flext_infra._models import FlextInfraConfigModelsWorkspace


__all__: tuple[str, ...] = (
    "FlextInfraConfigModels",
    "FlextInfraConfigModelsArtifact",
    "FlextInfraConfigModelsBeads",
    "FlextInfraConfigModelsContexts",
    "FlextInfraConfigModelsContract",
    "FlextInfraConfigModelsMake",
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
