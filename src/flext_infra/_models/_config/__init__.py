# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Models. Config package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .artifact import FlextInfraConfigModelsArtifact
    from .base import FlextInfraConfigModels
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
            ".make": ("FlextInfraConfigModelsMake",),
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
