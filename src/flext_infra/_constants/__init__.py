# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Constants package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._constants.base import FlextInfraConstantsBase
    from flext_infra._constants.census import FlextInfraConstantsCensus
    from flext_infra._constants.check import FlextInfraConstantsCheck
    from flext_infra._constants.cli import FlextInfraConstantsCli
    from flext_infra._constants.codegen import FlextInfraConstantsCodegen
    from flext_infra._constants.codegen_detection import (
        FlextInfraConstantsCodegenDetection,
    )
    from flext_infra._constants.codegen_lazy import FlextInfraConstantsCodegenLazy
    from flext_infra._constants.codegen_project import FlextInfraConstantsCodegenProject
    from flext_infra._constants.codegen_render_names import (
        FlextInfraConstantsCodegenRenderNames,
    )
    from flext_infra._constants.deps import FlextInfraConstantsDeps
    from flext_infra._constants.docs import FlextInfraConstantsDocs
    from flext_infra._constants.git import FlextInfraConstantsGit
    from flext_infra._constants.make import FlextInfraConstantsMake
    from flext_infra._constants.namespace import FlextInfraConstantsNamespace
    from flext_infra._constants.promoted import FlextInfraConstantsPromoted
    from flext_infra._constants.promoted_messages import (
        FlextInfraConstantsPromotedMessages,
    )
    from flext_infra._constants.refactor import FlextInfraConstantsRefactor
    from flext_infra._constants.release import FlextInfraConstantsRelease
    from flext_infra._constants.rope import FlextInfraConstantsRope
    from flext_infra._constants.source_code import FlextInfraConstantsSourceCode
    from flext_infra._constants.validate import FlextInfraConstantsSharedInfra
    from flext_infra._constants.workspace import FlextInfraConstantsWorkspace

__all__: tuple[str, ...] = (
    "FlextInfraConstantsBase",
    "FlextInfraConstantsCensus",
    "FlextInfraConstantsCheck",
    "FlextInfraConstantsCli",
    "FlextInfraConstantsCodegen",
    "FlextInfraConstantsCodegenDetection",
    "FlextInfraConstantsCodegenLazy",
    "FlextInfraConstantsCodegenProject",
    "FlextInfraConstantsCodegenRenderNames",
    "FlextInfraConstantsDeps",
    "FlextInfraConstantsDocs",
    "FlextInfraConstantsGit",
    "FlextInfraConstantsMake",
    "FlextInfraConstantsNamespace",
    "FlextInfraConstantsPromoted",
    "FlextInfraConstantsPromotedMessages",
    "FlextInfraConstantsRefactor",
    "FlextInfraConstantsRelease",
    "FlextInfraConstantsRope",
    "FlextInfraConstantsSharedInfra",
    "FlextInfraConstantsSourceCode",
    "FlextInfraConstantsWorkspace",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".base": ("FlextInfraConstantsBase",),
            ".census": ("FlextInfraConstantsCensus",),
            ".check": ("FlextInfraConstantsCheck",),
            ".cli": ("FlextInfraConstantsCli",),
            ".codegen": ("FlextInfraConstantsCodegen",),
            ".codegen_detection": ("FlextInfraConstantsCodegenDetection",),
            ".codegen_lazy": ("FlextInfraConstantsCodegenLazy",),
            ".codegen_project": ("FlextInfraConstantsCodegenProject",),
            ".codegen_render_names": ("FlextInfraConstantsCodegenRenderNames",),
            ".deps": ("FlextInfraConstantsDeps",),
            ".docs": ("FlextInfraConstantsDocs",),
            ".git": ("FlextInfraConstantsGit",),
            ".make": ("FlextInfraConstantsMake",),
            ".namespace": ("FlextInfraConstantsNamespace",),
            ".promoted": ("FlextInfraConstantsPromoted",),
            ".promoted_messages": ("FlextInfraConstantsPromotedMessages",),
            ".refactor": ("FlextInfraConstantsRefactor",),
            ".release": ("FlextInfraConstantsRelease",),
            ".rope": ("FlextInfraConstantsRope",),
            ".source_code": ("FlextInfraConstantsSourceCode",),
            ".validate": ("FlextInfraConstantsSharedInfra",),
            ".workspace": ("FlextInfraConstantsWorkspace",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
