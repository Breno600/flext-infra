# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.codegen. Conform package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.codegen._conform.artifact_render import (
        FlextInfraCodegenConformArtifactRender,
    )
    from flext_infra.codegen._conform.beads_routes import (
        FlextInfraCodegenConformBeadsRoutes,
    )
    from flext_infra.codegen._conform.bootstrap import FlextInfraCodegenConformBootstrap
    from flext_infra.codegen._conform.context_render import (
        FlextInfraCodegenConformContextRender,
    )
    from flext_infra.codegen._conform.docs_ownership import (
        FlextInfraCodegenConformDocsOwnership,
    )
    from flext_infra.codegen._conform.execute import FlextInfraCodegenConformExecute
    from flext_infra.codegen._conform.existing_plan import (
        FlextInfraCodegenConformExistingPlan,
    )
    from flext_infra.codegen._conform.file_plans import (
        FlextInfraCodegenConformFilePlans,
    )
    from flext_infra.codegen._conform.gitignore import FlextInfraCodegenConformGitignore
    from flext_infra.codegen._conform.plan import FlextInfraCodegenConformPlan
    from flext_infra.codegen._conform.pyproject_policy import (
        FlextInfraCodegenConformPyprojectPolicy,
    )
    from flext_infra.codegen._conform.scaffold_plan import (
        FlextInfraCodegenConformScaffoldPlan,
    )


__all__: tuple[str, ...] = (
    "FlextInfraCodegenConformArtifactRender",
    "FlextInfraCodegenConformBeadsRoutes",
    "FlextInfraCodegenConformBootstrap",
    "FlextInfraCodegenConformContextRender",
    "FlextInfraCodegenConformDocsOwnership",
    "FlextInfraCodegenConformExecute",
    "FlextInfraCodegenConformExistingPlan",
    "FlextInfraCodegenConformFilePlans",
    "FlextInfraCodegenConformGitignore",
    "FlextInfraCodegenConformPlan",
    "FlextInfraCodegenConformPyprojectPolicy",
    "FlextInfraCodegenConformScaffoldPlan",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraCodegenConformArtifactRender": (
            ".artifact_render",
            "FlextInfraCodegenConformArtifactRender",
        ),
        "FlextInfraCodegenConformBeadsRoutes": (
            ".beads_routes",
            "FlextInfraCodegenConformBeadsRoutes",
        ),
        "FlextInfraCodegenConformBootstrap": (
            ".bootstrap",
            "FlextInfraCodegenConformBootstrap",
        ),
        "FlextInfraCodegenConformContextRender": (
            ".context_render",
            "FlextInfraCodegenConformContextRender",
        ),
        "FlextInfraCodegenConformDocsOwnership": (
            ".docs_ownership",
            "FlextInfraCodegenConformDocsOwnership",
        ),
        "FlextInfraCodegenConformExecute": (
            ".execute",
            "FlextInfraCodegenConformExecute",
        ),
        "FlextInfraCodegenConformExistingPlan": (
            ".existing_plan",
            "FlextInfraCodegenConformExistingPlan",
        ),
        "FlextInfraCodegenConformFilePlans": (
            ".file_plans",
            "FlextInfraCodegenConformFilePlans",
        ),
        "FlextInfraCodegenConformGitignore": (
            ".gitignore",
            "FlextInfraCodegenConformGitignore",
        ),
        "FlextInfraCodegenConformPlan": (".plan", "FlextInfraCodegenConformPlan"),
        "FlextInfraCodegenConformPyprojectPolicy": (
            ".pyproject_policy",
            "FlextInfraCodegenConformPyprojectPolicy",
        ),
        "FlextInfraCodegenConformScaffoldPlan": (
            ".scaffold_plan",
            "FlextInfraCodegenConformScaffoldPlan",
        ),
    }),
    public_exports=__all__,
)
