# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Models. Config package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports
from flext_infra._models._config.artifact import FlextInfraConfigModelsArtifact
from flext_infra._models._config.base import FlextInfraConfigModels
from flext_infra._models._config.beads import FlextInfraConfigModelsBeads
from flext_infra._models._config.contexts import FlextInfraConfigModelsContexts
from flext_infra._models._config.contract import FlextInfraConfigModelsContract
from flext_infra._models._config.make import (
    ExternalCacheDirectorySpec,
    FlextInfraConfigModelsMake,
)
from flext_infra._models._config.provider import FlextInfraConfigModelsProvider
from flext_infra._models._config.release import FlextInfraConfigModelsRelease
from flext_infra._models._config.render import FlextInfraConfigModelsRender
from flext_infra._models._config.root import FlextInfraConfigModelsRoot
from flext_infra._models._config.scaffold import FlextInfraConfigModelsScaffold
from flext_infra._models._config.static import FlextInfraConfigModelsStatic
from flext_infra._models._config.templates import FlextInfraConfigModelsTemplates
from flext_infra._models._config.workspace import FlextInfraConfigModelsWorkspace

__all__: tuple[str, ...] = (
    "ExternalCacheDirectorySpec",
    "FlextInfraConfigModels",
    "FlextInfraConfigModelsArtifact",
    "FlextInfraConfigModelsBeads",
    "FlextInfraConfigModelsContexts",
    "FlextInfraConfigModelsContract",
    "FlextInfraConfigModelsMake",
    "FlextInfraConfigModelsProvider",
    "FlextInfraConfigModelsRelease",
    "FlextInfraConfigModelsRender",
    "FlextInfraConfigModelsRoot",
    "FlextInfraConfigModelsScaffold",
    "FlextInfraConfigModelsStatic",
    "FlextInfraConfigModelsTemplates",
    "FlextInfraConfigModelsWorkspace",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".artifact": ("FlextInfraConfigModelsArtifact",),
            ".base": ("FlextInfraConfigModels",),
            ".beads": ("FlextInfraConfigModelsBeads",),
            ".contexts": ("FlextInfraConfigModelsContexts",),
            ".contract": ("FlextInfraConfigModelsContract",),
            ".make": ("ExternalCacheDirectorySpec", "FlextInfraConfigModelsMake"),
            ".provider": ("FlextInfraConfigModelsProvider",),
            ".release": ("FlextInfraConfigModelsRelease",),
            ".render": ("FlextInfraConfigModelsRender",),
            ".root": ("FlextInfraConfigModelsRoot",),
            ".scaffold": ("FlextInfraConfigModelsScaffold",),
            ".static": ("FlextInfraConfigModelsStatic",),
            ".templates": ("FlextInfraConfigModelsTemplates",),
            ".workspace": ("FlextInfraConfigModelsWorkspace",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
