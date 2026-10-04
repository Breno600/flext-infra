# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Constants package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

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

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraConstantsBase": (".base", "FlextInfraConstantsBase"),
        "FlextInfraConstantsCensus": (".census", "FlextInfraConstantsCensus"),
        "FlextInfraConstantsCheck": (".check", "FlextInfraConstantsCheck"),
        "FlextInfraConstantsCli": (".cli", "FlextInfraConstantsCli"),
        "FlextInfraConstantsCodegen": (".codegen", "FlextInfraConstantsCodegen"),
        "FlextInfraConstantsCodegenDetection": (
            ".codegen_detection",
            "FlextInfraConstantsCodegenDetection",
        ),
        "FlextInfraConstantsCodegenLazy": (
            ".codegen_lazy",
            "FlextInfraConstantsCodegenLazy",
        ),
        "FlextInfraConstantsCodegenProject": (
            ".codegen_project",
            "FlextInfraConstantsCodegenProject",
        ),
        "FlextInfraConstantsCodegenRenderNames": (
            ".codegen_render_names",
            "FlextInfraConstantsCodegenRenderNames",
        ),
        "FlextInfraConstantsDeps": (".deps", "FlextInfraConstantsDeps"),
        "FlextInfraConstantsDocs": (".docs", "FlextInfraConstantsDocs"),
        "FlextInfraConstantsGit": (".git", "FlextInfraConstantsGit"),
        "FlextInfraConstantsMake": (".make", "FlextInfraConstantsMake"),
        "FlextInfraConstantsNamespace": (".namespace", "FlextInfraConstantsNamespace"),
        "FlextInfraConstantsPromoted": (".promoted", "FlextInfraConstantsPromoted"),
        "FlextInfraConstantsPromotedMessages": (
            ".promoted_messages",
            "FlextInfraConstantsPromotedMessages",
        ),
        "FlextInfraConstantsRefactor": (".refactor", "FlextInfraConstantsRefactor"),
        "FlextInfraConstantsRelease": (".release", "FlextInfraConstantsRelease"),
        "FlextInfraConstantsRope": (".rope", "FlextInfraConstantsRope"),
        "FlextInfraConstantsSharedInfra": (
            ".validate",
            "FlextInfraConstantsSharedInfra",
        ),
        "FlextInfraConstantsSourceCode": (
            ".source_code",
            "FlextInfraConstantsSourceCode",
        ),
        "FlextInfraConstantsWorkspace": (".workspace", "FlextInfraConstantsWorkspace"),
    }),
    public_exports=__all__,
)
