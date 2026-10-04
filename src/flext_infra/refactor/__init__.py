# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.refactor package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.refactor._accessor_report import (
        FlextInfraAccessorMigrationReportMixin,
    )
    from flext_infra.refactor._accessor_rewrite import (
        FlextInfraAccessorMigrationRewriteMixin,
    )
    from flext_infra.refactor._census_apply_formatting import (
        FlextInfraRefactorCensusApplyFormattingMixin,
    )
    from flext_infra.refactor._census_collect import (
        FlextInfraRefactorCensusCollectMixin,
    )
    from flext_infra.refactor._census_collect_helpers import (
        FlextInfraRefactorCensusCollectHelpersMixin,
    )
    from flext_infra.refactor._census_filters import (
        FlextInfraRefactorCensusFiltersMixin,
    )
    from flext_infra.refactor._census_objects import (
        FlextInfraRefactorCensusObjectsMixin,
    )
    from flext_infra.refactor._census_project import (
        FlextInfraRefactorCensusProjectMixin,
    )
    from flext_infra.refactor._census_removal import (
        FlextInfraRefactorCensusRemovalMixin,
    )
    from flext_infra.refactor._census_render import FlextInfraRefactorCensusRenderMixin
    from flext_infra.refactor._namespace_enforcer_project import (
        FlextInfraNamespaceEnforcerProjectMixin,
    )
    from flext_infra.refactor._project_classifier_deps import (
        FlextInfraProjectClassifierDepsMixin,
    )
    from flext_infra.refactor._project_classifier_family import (
        FlextInfraProjectClassifierFamilyMixin,
    )
    from flext_infra.refactor._wrapper_rewrite import (
        FlextInfraWrapperRootNamespaceRewriteMixin,
    )
    from flext_infra.refactor.accessor_migration import (
        FlextInfraAccessorMigrationOrchestrator,
    )
    from flext_infra.refactor.census import FlextInfraRefactorCensus
    from flext_infra.refactor.namespace_enforcer import FlextInfraNamespaceEnforcer
    from flext_infra.refactor.project_classifier import FlextInfraProjectClassifier
    from flext_infra.refactor.wrapper_root_namespace import (
        FlextInfraWrapperRootNamespaceRefactor,
    )


__all__: tuple[str, ...] = (
    "FlextInfraAccessorMigrationOrchestrator",
    "FlextInfraAccessorMigrationReportMixin",
    "FlextInfraAccessorMigrationRewriteMixin",
    "FlextInfraNamespaceEnforcer",
    "FlextInfraNamespaceEnforcerProjectMixin",
    "FlextInfraProjectClassifier",
    "FlextInfraProjectClassifierDepsMixin",
    "FlextInfraProjectClassifierFamilyMixin",
    "FlextInfraRefactorCensus",
    "FlextInfraRefactorCensusApplyFormattingMixin",
    "FlextInfraRefactorCensusCollectHelpersMixin",
    "FlextInfraRefactorCensusCollectMixin",
    "FlextInfraRefactorCensusFiltersMixin",
    "FlextInfraRefactorCensusObjectsMixin",
    "FlextInfraRefactorCensusProjectMixin",
    "FlextInfraRefactorCensusRemovalMixin",
    "FlextInfraRefactorCensusRenderMixin",
    "FlextInfraWrapperRootNamespaceRefactor",
    "FlextInfraWrapperRootNamespaceRewriteMixin",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraAccessorMigrationOrchestrator": (
            ".accessor_migration",
            "FlextInfraAccessorMigrationOrchestrator",
        ),
        "FlextInfraAccessorMigrationReportMixin": (
            "._accessor_report",
            "FlextInfraAccessorMigrationReportMixin",
        ),
        "FlextInfraAccessorMigrationRewriteMixin": (
            "._accessor_rewrite",
            "FlextInfraAccessorMigrationRewriteMixin",
        ),
        "FlextInfraNamespaceEnforcer": (
            ".namespace_enforcer",
            "FlextInfraNamespaceEnforcer",
        ),
        "FlextInfraNamespaceEnforcerProjectMixin": (
            "._namespace_enforcer_project",
            "FlextInfraNamespaceEnforcerProjectMixin",
        ),
        "FlextInfraProjectClassifier": (
            ".project_classifier",
            "FlextInfraProjectClassifier",
        ),
        "FlextInfraProjectClassifierDepsMixin": (
            "._project_classifier_deps",
            "FlextInfraProjectClassifierDepsMixin",
        ),
        "FlextInfraProjectClassifierFamilyMixin": (
            "._project_classifier_family",
            "FlextInfraProjectClassifierFamilyMixin",
        ),
        "FlextInfraRefactorCensus": (".census", "FlextInfraRefactorCensus"),
        "FlextInfraRefactorCensusApplyFormattingMixin": (
            "._census_apply_formatting",
            "FlextInfraRefactorCensusApplyFormattingMixin",
        ),
        "FlextInfraRefactorCensusCollectHelpersMixin": (
            "._census_collect_helpers",
            "FlextInfraRefactorCensusCollectHelpersMixin",
        ),
        "FlextInfraRefactorCensusCollectMixin": (
            "._census_collect",
            "FlextInfraRefactorCensusCollectMixin",
        ),
        "FlextInfraRefactorCensusFiltersMixin": (
            "._census_filters",
            "FlextInfraRefactorCensusFiltersMixin",
        ),
        "FlextInfraRefactorCensusObjectsMixin": (
            "._census_objects",
            "FlextInfraRefactorCensusObjectsMixin",
        ),
        "FlextInfraRefactorCensusProjectMixin": (
            "._census_project",
            "FlextInfraRefactorCensusProjectMixin",
        ),
        "FlextInfraRefactorCensusRemovalMixin": (
            "._census_removal",
            "FlextInfraRefactorCensusRemovalMixin",
        ),
        "FlextInfraRefactorCensusRenderMixin": (
            "._census_render",
            "FlextInfraRefactorCensusRenderMixin",
        ),
        "FlextInfraWrapperRootNamespaceRefactor": (
            ".wrapper_root_namespace",
            "FlextInfraWrapperRootNamespaceRefactor",
        ),
        "FlextInfraWrapperRootNamespaceRewriteMixin": (
            "._wrapper_rewrite",
            "FlextInfraWrapperRootNamespaceRewriteMixin",
        ),
    }),
    public_exports=__all__,
)
