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
    from flext_infra.refactor._accessor_origin import FlextInfraAccessorOriginResolver
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
    from flext_infra.refactor._import_ast import FlextInfraImportNormalizationAstMixin
    from flext_infra.refactor._import_enforcement import FlextInfraImportNormalization
    from flext_infra.refactor._import_placement import (
        FlextInfraImportNormalizationPlacementMixin,
    )
    from flext_infra.refactor._import_routes import (
        FlextInfraImportNormalizationRoutesMixin,
    )
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
    from flext_infra.refactor.namespace_relocations import (
        FlextInfraNamespaceRelocationCascade,
    )
    from flext_infra.refactor.project_classifier import FlextInfraProjectClassifier
    from flext_infra.refactor.violations_sweep import FlextInfraRefactorViolationsSweep
    from flext_infra.refactor.wrapper_root_namespace import (
        FlextInfraWrapperRootNamespaceRefactor,
    )


__all__: tuple[str, ...] = (
    "FlextInfraAccessorMigrationOrchestrator",
    "FlextInfraAccessorMigrationReportMixin",
    "FlextInfraAccessorMigrationRewriteMixin",
    "FlextInfraAccessorOriginResolver",
    "FlextInfraImportNormalization",
    "FlextInfraImportNormalizationAstMixin",
    "FlextInfraImportNormalizationPlacementMixin",
    "FlextInfraImportNormalizationRoutesMixin",
    "FlextInfraNamespaceEnforcer",
    "FlextInfraNamespaceEnforcerProjectMixin",
    "FlextInfraNamespaceRelocationCascade",
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
    "FlextInfraRefactorViolationsSweep",
    "FlextInfraWrapperRootNamespaceRefactor",
    "FlextInfraWrapperRootNamespaceRewriteMixin",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraAccessorMigrationOrchestrator": ".accessor_migration",
        "FlextInfraAccessorMigrationReportMixin": "._accessor_report",
        "FlextInfraAccessorMigrationRewriteMixin": "._accessor_rewrite",
        "FlextInfraAccessorOriginResolver": "._accessor_origin",
        "FlextInfraImportNormalization": "._import_enforcement",
        "FlextInfraImportNormalizationAstMixin": "._import_ast",
        "FlextInfraImportNormalizationPlacementMixin": "._import_placement",
        "FlextInfraImportNormalizationRoutesMixin": "._import_routes",
        "FlextInfraNamespaceEnforcer": ".namespace_enforcer",
        "FlextInfraNamespaceEnforcerProjectMixin": "._namespace_enforcer_project",
        "FlextInfraNamespaceRelocationCascade": ".namespace_relocations",
        "FlextInfraProjectClassifier": ".project_classifier",
        "FlextInfraProjectClassifierDepsMixin": "._project_classifier_deps",
        "FlextInfraProjectClassifierFamilyMixin": "._project_classifier_family",
        "FlextInfraRefactorCensus": ".census",
        "FlextInfraRefactorCensusApplyFormattingMixin": "._census_apply_formatting",
        "FlextInfraRefactorCensusCollectHelpersMixin": "._census_collect_helpers",
        "FlextInfraRefactorCensusCollectMixin": "._census_collect",
        "FlextInfraRefactorCensusFiltersMixin": "._census_filters",
        "FlextInfraRefactorCensusObjectsMixin": "._census_objects",
        "FlextInfraRefactorCensusProjectMixin": "._census_project",
        "FlextInfraRefactorCensusRemovalMixin": "._census_removal",
        "FlextInfraRefactorCensusRenderMixin": "._census_render",
        "FlextInfraRefactorViolationsSweep": ".violations_sweep",
        "FlextInfraWrapperRootNamespaceRefactor": ".wrapper_root_namespace",
        "FlextInfraWrapperRootNamespaceRewriteMixin": "._wrapper_rewrite",
    }),
    public_exports=__all__,
)
