# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.refactor package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from ._accessor_report import FlextInfraAccessorMigrationReportMixin
    from ._accessor_rewrite import FlextInfraAccessorMigrationRewriteMixin
    from ._census_apply import FlextInfraRefactorCensusApplyMixin
    from ._census_apply_formatting import FlextInfraRefactorCensusApplyFormattingMixin
    from ._census_collect import FlextInfraRefactorCensusCollectMixin
    from ._census_collect_helpers import FlextInfraRefactorCensusCollectHelpersMixin
    from ._census_filters import FlextInfraRefactorCensusFiltersMixin
    from ._census_inventory import FlextInfraRefactorCensusInventoryMixin
    from ._census_objects import FlextInfraRefactorCensusObjectsMixin
    from ._census_project import FlextInfraRefactorCensusProjectMixin
    from ._census_render import FlextInfraRefactorCensusRenderMixin
    from ._census_rules_alias import FlextInfraRefactorCensusRulesAliasMixin
    from ._census_rules_dispatch import FlextInfraRefactorCensusRulesDispatchMixin
    from ._census_rules_shared import FlextInfraRefactorCensusRulesSharedMixin
    from ._census_rules_struct import FlextInfraRefactorCensusRulesStructMixin
    from ._census_symbols import FlextInfraRefactorCensusSymbolsMixin
    from ._census_validate import FlextInfraRefactorCensusValidateMixin
    from ._namespace_enforcer_project import FlextInfraNamespaceEnforcerProjectMixin
    from ._project_classifier_deps import FlextInfraProjectClassifierDepsMixin
    from ._project_classifier_family import FlextInfraProjectClassifierFamilyMixin
    from ._wrapper_rewrite import FlextInfraWrapperRootNamespaceRewriteMixin
    from .accessor_migration import FlextInfraAccessorMigrationOrchestrator
    from .census import FlextInfraRefactorCensus
    from .classvar_constant_autofix import FlextInfraRefactorClassvarConstantAutofix
    from .modernize_orchestrator import FlextInfraModernizeOrchestrator
    from .namespace_enforcer import FlextInfraNamespaceEnforcer
    from .namespace_enforcer_phases import FlextInfraNamespaceEnforcerPhasesMixin
    from .project_alias_migrator import FlextInfraRefactorProjectAliasMigrator
    from .project_classifier import FlextInfraProjectClassifier
    from .signature_propagation import FlextInfraRefactorSignaturePropagation
    from .wrapper_root_namespace import FlextInfraWrapperRootNamespaceRefactor


__all__: tuple[str, ...] = (
    "FlextInfraAccessorMigrationOrchestrator",
    "FlextInfraAccessorMigrationReportMixin",
    "FlextInfraAccessorMigrationRewriteMixin",
    "FlextInfraModernizeOrchestrator",
    "FlextInfraNamespaceEnforcer",
    "FlextInfraNamespaceEnforcerPhasesMixin",
    "FlextInfraNamespaceEnforcerProjectMixin",
    "FlextInfraProjectClassifier",
    "FlextInfraProjectClassifierDepsMixin",
    "FlextInfraProjectClassifierFamilyMixin",
    "FlextInfraRefactorCensus",
    "FlextInfraRefactorCensusApplyFormattingMixin",
    "FlextInfraRefactorCensusApplyMixin",
    "FlextInfraRefactorCensusCollectHelpersMixin",
    "FlextInfraRefactorCensusCollectMixin",
    "FlextInfraRefactorCensusFiltersMixin",
    "FlextInfraRefactorCensusInventoryMixin",
    "FlextInfraRefactorCensusObjectsMixin",
    "FlextInfraRefactorCensusProjectMixin",
    "FlextInfraRefactorCensusRenderMixin",
    "FlextInfraRefactorCensusRulesAliasMixin",
    "FlextInfraRefactorCensusRulesDispatchMixin",
    "FlextInfraRefactorCensusRulesSharedMixin",
    "FlextInfraRefactorCensusRulesStructMixin",
    "FlextInfraRefactorCensusSymbolsMixin",
    "FlextInfraRefactorCensusValidateMixin",
    "FlextInfraRefactorClassvarConstantAutofix",
    "FlextInfraRefactorProjectAliasMigrator",
    "FlextInfraRefactorSignaturePropagation",
    "FlextInfraWrapperRootNamespaceRefactor",
    "FlextInfraWrapperRootNamespaceRewriteMixin",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._accessor_report": ("FlextInfraAccessorMigrationReportMixin",),
            "._accessor_rewrite": ("FlextInfraAccessorMigrationRewriteMixin",),
            "._census_apply": ("FlextInfraRefactorCensusApplyMixin",),
            "._census_apply_formatting": (
                "FlextInfraRefactorCensusApplyFormattingMixin",
            ),
            "._census_collect": ("FlextInfraRefactorCensusCollectMixin",),
            "._census_collect_helpers": (
                "FlextInfraRefactorCensusCollectHelpersMixin",
            ),
            "._census_filters": ("FlextInfraRefactorCensusFiltersMixin",),
            "._census_inventory": ("FlextInfraRefactorCensusInventoryMixin",),
            "._census_objects": ("FlextInfraRefactorCensusObjectsMixin",),
            "._census_project": ("FlextInfraRefactorCensusProjectMixin",),
            "._census_render": ("FlextInfraRefactorCensusRenderMixin",),
            "._census_rules_alias": ("FlextInfraRefactorCensusRulesAliasMixin",),
            "._census_rules_dispatch": ("FlextInfraRefactorCensusRulesDispatchMixin",),
            "._census_rules_shared": ("FlextInfraRefactorCensusRulesSharedMixin",),
            "._census_rules_struct": ("FlextInfraRefactorCensusRulesStructMixin",),
            "._census_symbols": ("FlextInfraRefactorCensusSymbolsMixin",),
            "._census_validate": ("FlextInfraRefactorCensusValidateMixin",),
            "._namespace_enforcer_project": (
                "FlextInfraNamespaceEnforcerProjectMixin",
            ),
            "._project_classifier_deps": ("FlextInfraProjectClassifierDepsMixin",),
            "._project_classifier_family": ("FlextInfraProjectClassifierFamilyMixin",),
            "._wrapper_rewrite": ("FlextInfraWrapperRootNamespaceRewriteMixin",),
            ".accessor_migration": ("FlextInfraAccessorMigrationOrchestrator",),
            ".census": ("FlextInfraRefactorCensus",),
            ".classvar_constant_autofix": (
                "FlextInfraRefactorClassvarConstantAutofix",
            ),
            ".modernize_orchestrator": ("FlextInfraModernizeOrchestrator",),
            ".namespace_enforcer": ("FlextInfraNamespaceEnforcer",),
            ".namespace_enforcer_phases": ("FlextInfraNamespaceEnforcerPhasesMixin",),
            ".project_alias_migrator": ("FlextInfraRefactorProjectAliasMigrator",),
            ".project_classifier": ("FlextInfraProjectClassifier",),
            ".signature_propagation": ("FlextInfraRefactorSignaturePropagation",),
            ".wrapper_root_namespace": ("FlextInfraWrapperRootNamespaceRefactor",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
