# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.refactor package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

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

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._accessor_report": ("FlextInfraAccessorMigrationReportMixin",),
            "._accessor_rewrite": ("FlextInfraAccessorMigrationRewriteMixin",),
            "._census_apply_formatting": (
                "FlextInfraRefactorCensusApplyFormattingMixin",
            ),
            "._census_collect": ("FlextInfraRefactorCensusCollectMixin",),
            "._census_collect_helpers": (
                "FlextInfraRefactorCensusCollectHelpersMixin",
            ),
            "._census_filters": ("FlextInfraRefactorCensusFiltersMixin",),
            "._census_objects": ("FlextInfraRefactorCensusObjectsMixin",),
            "._census_project": ("FlextInfraRefactorCensusProjectMixin",),
            "._census_removal": ("FlextInfraRefactorCensusRemovalMixin",),
            "._census_render": ("FlextInfraRefactorCensusRenderMixin",),
            "._namespace_enforcer_project": (
                "FlextInfraNamespaceEnforcerProjectMixin",
            ),
            "._project_classifier_deps": ("FlextInfraProjectClassifierDepsMixin",),
            "._project_classifier_family": ("FlextInfraProjectClassifierFamilyMixin",),
            "._wrapper_rewrite": ("FlextInfraWrapperRootNamespaceRewriteMixin",),
            ".accessor_migration": ("FlextInfraAccessorMigrationOrchestrator",),
            ".census": ("FlextInfraRefactorCensus",),
            ".namespace_enforcer": ("FlextInfraNamespaceEnforcer",),
            ".project_classifier": ("FlextInfraProjectClassifier",),
            ".wrapper_root_namespace": ("FlextInfraWrapperRootNamespaceRefactor",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
