# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._utilities import (
        _git,
        _promoted,
        _pyproject,
        _rope,
        _rope_analysis,
        _semantic_cutover,
    )
    from flext_infra._utilities import FlextInfraUtilitiesDocsAuditDetectorsMixin
    from flext_infra._utilities import FlextInfraUtilitiesDocsCommandContractMixin
    from flext_infra._utilities import FlextInfraUtilitiesDocsGeneratePlanMixin
    from flext_infra._utilities import FlextInfraUtilitiesDocsGenerateProjectMixin
    from flext_infra._utilities import FlextInfraUtilitiesDocsGenerateRootMixin
    from flext_infra._utilities import FlextInfraUtilitiesDocsGenerateSourcesMixin
    from flext_infra._utilities import FlextInfraUtilitiesDocsGithubLinks
    from flext_infra._utilities import FlextInfraUtilitiesDocsGuidesMixin
    from flext_infra._utilities import FlextInfraUtilitiesDocsScopeBuildMixin
    from flext_infra._utilities import FlextInfraUtilitiesDocsScopePathsMixin
    from flext_infra._utilities import FlextInfraUtilitiesDocsScopePolicyMixin
    from flext_infra._utilities import FlextInfraUtilitiesDocsScopeProjectsMixin
    from flext_infra._utilities import FlextInfraUtilitiesDocsScopeSelectionMixin
    from flext_infra._utilities import FlextInfraUtilitiesDocsScopeStateMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitAttestationMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitMutationScopeMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitRemote
    from flext_infra._utilities import FlextInfraUtilitiesGitRepo
    from flext_infra._utilities import FlextInfraUtilitiesGitScopeMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticIdentityMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticIndexMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticLaneMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticPathsMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticPublishMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticRefsMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticSubmoduleMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticWorktreeMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStateCaptureMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStateCheckpointMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStateFilesMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStatePublicationMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStateSnapshotMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStateTransitionMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStateTreesMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeCheckpointMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeDiscoveryMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeFactsMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeIO
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeMaterializationMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeMeasureMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreePatchMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeRemovalMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeRootsMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeStatusMixin
    from flext_infra._utilities import FlextInfraMypyProfiler
    from flext_infra._utilities import FlextInfraMypyDarwinSupervisor
    from flext_infra._utilities import FlextInfraUtilitiesProjectDiscoveryCandidatesMixin
    from flext_infra._utilities import FlextInfraUtilitiesProjectDiscoveryShapeMixin
    from flext_infra._utilities import FlextInfraUtilitiesPromotedCommands
    from flext_infra._utilities import FlextInfraUtilitiesPromotedExecution
    from flext_infra._utilities import FlextInfraUtilitiesPromotedInvocation
    from flext_infra._utilities import FlextInfraUtilitiesPromotedRendering
    from flext_infra._utilities import FlextInfraUtilitiesPromotedWorkspace
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectConformBase
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectDocument
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectOverlay
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectRequirements
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectSession
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectTomlPhases
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectUvSources
    from flext_infra._utilities import FlextInfraRopeProject
    from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysisAstHelpers
    from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysisBase
    from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysisExports
    from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysisImportState
    from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysisSourceScan
    from flext_infra._utilities import FlextInfraUtilitiesRopeCorePyModuleMixin
    from flext_infra._utilities import FlextInfraUtilitiesRopeCoreResourcesMixin
    from flext_infra._utilities import FlextInfraUtilitiesRopeMethodOrderMixin
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverAliasCst
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverAliases
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverBase
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverBindings
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverClassScope
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverDynamicEnvironment
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverEdits
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverFacadeBaseCst
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverFacadeBases
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverFacadeOwners
    from flext_infra._utilities import FlextInfraUtilitiesSemanticFamilyFlatten
    from flext_infra._utilities import FlextInfraUtilitiesSemanticFamilyReferences
    from flext_infra._utilities import FlextInfraUtilitiesSemanticFamilyTypeReferences
    from flext_infra._utilities import FlextInfraUtilitiesSemanticHelperReferences
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverModelFields
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverModelFieldsBindings
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverModuleLayout
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverNesting
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverNestingCst
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverNestingModuleAliases
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverNestingOwner
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverNestingReferences
    from flext_infra._utilities import FlextInfraUtilitiesSemanticNestingTypes
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverPrivateImportCst
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverPrivateImports
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutoverSelfFacade
    from flext_infra._utilities import FlextInfraUtilitiesBase
    from flext_infra._utilities import FlextInfraUtilitiesRefactorCensus
    from flext_infra._utilities import FlextInfraUtilitiesCodegen
    from flext_infra._utilities import FlextInfraUtilitiesCodegenFacades
    from flext_infra._utilities import FlextInfraUtilitiesCodegenFilePlan
    from flext_infra._utilities import FlextInfraUtilitiesCodegenPathCutover
    from flext_infra._utilities import FlextInfraUtilitiesCodemodProject
    from flext_infra._utilities import FlextInfraUtilitiesCodemodRules
    from flext_infra._utilities import FlextInfraUtilitiesCompatibilityAliasValidation
    from flext_infra._utilities import FlextInfraUtilitiesDeferredSelfReferenceRewrite
    from flext_infra._utilities import FlextInfraUtilitiesDependencies
    from flext_infra._utilities import FlextInfraUtilitiesDiscovery
    from flext_infra._utilities import FlextInfraUtilitiesDocs
    from flext_infra._utilities import FlextInfraUtilitiesDocsApi
    from flext_infra._utilities import FlextInfraUtilitiesDocsAudit
    from flext_infra._utilities import FlextInfraUtilitiesDocsBuild
    from flext_infra._utilities import FlextInfraUtilitiesDocsCollection
    from flext_infra._utilities import FlextInfraUtilitiesDocsCollectionSources
    from flext_infra._utilities import FlextInfraUtilitiesDocsCollectionVerify
    from flext_infra._utilities import FlextInfraUtilitiesDocsContract
    from flext_infra._utilities import FlextInfraUtilitiesDocsFix
    from flext_infra._utilities import FlextInfraUtilitiesDocsGenerate
    from flext_infra._utilities import FlextInfraUtilitiesDocsRender
    from flext_infra._utilities import FlextInfraUtilitiesDocsScope
    from flext_infra._utilities import FlextInfraUtilitiesDocsValidate
    from flext_infra._utilities import FlextInfraUtilitiesGit
    from flext_infra._utilities import FlextInfraUtilitiesGitignore
    from flext_infra._utilities import FlextInfraUtilitiesIteration
    from flext_infra._utilities import FlextInfraUtilitiesIterationDirectory
    from flext_infra._utilities import FlextInfraUtilitiesIterationMatching
    from flext_infra._utilities import FlextInfraUtilitiesIterationWorkspace
    from flext_infra._utilities import FlextInfraUtilitiesLintRecipes
    from flext_infra._utilities import FlextInfraUtilitiesLogParser
    from flext_infra._utilities import FlextInfraUtilitiesManagedConflicts
    from flext_infra._utilities import FlextInfraUtilitiesCodegenNamespace
    from flext_infra._utilities import FlextInfraUtilitiesRefactorNamespaceFlext
    from flext_infra._utilities import FlextInfraUtilitiesRefactorNamespaceCommon
    from flext_infra._utilities import FlextInfraUtilitiesNamespaceConfig
    from flext_infra._utilities import FlextInfraUtilitiesRefactorNamespaceMoves
    from flext_infra._utilities import FlextInfraUtilitiesNetwork
    from flext_infra._utilities import FlextInfraUtilitiesPrivateImportAncestry
    from flext_infra._utilities import FlextInfraUtilitiesPrivateImportFacades
    from flext_infra._utilities import FlextInfraUtilitiesPrivateImportValidation
    from flext_infra._utilities import FlextInfraUtilitiesProcess
    from flext_infra._utilities import FlextInfraUtilitiesProjectDiscovery
    from flext_infra._utilities import FlextInfraUtilitiesProjectManagedArtifacts
    from flext_infra._utilities import FlextInfraUtilitiesPromoted
    from flext_infra._utilities import FlextInfraUtilitiesProtectedEdit
    from flext_infra._utilities import FlextInfraUtilitiesProtectedEditApply
    from flext_infra._utilities import FlextInfraUtilitiesProtectedEditLinting
    from flext_infra._utilities import FlextInfraUtilitiesProtectedEditPreview
    from flext_infra._utilities import FlextInfraUtilitiesProtectedEditWrites
    from flext_infra._utilities import FlextInfraUtilitiesPyproject
    from flext_infra._utilities import FlextInfraUtilitiesPyprojectConform
    from flext_infra._utilities import FlextInfraUtilitiesPyrefly
    from flext_infra._utilities import FlextInfraUtilitiesQualifiedNames
    from flext_infra._utilities import FlextInfraUtilitiesRefactor
    from flext_infra._utilities import FlextInfraUtilitiesRelease
    from flext_infra._utilities import FlextInfraUtilitiesRepository
    from flext_infra._utilities import FlextInfraUtilitiesResourceLimits
    from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysis
    from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysisIntrospection
    from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysisWorkspace
    from flext_infra._utilities import FlextInfraUtilitiesRopeClassMove
    from flext_infra._utilities import FlextInfraUtilitiesRopeCore
    from flext_infra._utilities import FlextInfraUtilitiesRopeHelpers
    from flext_infra._utilities import FlextInfraUtilitiesRopeImports
    from flext_infra._utilities import FlextInfraUtilitiesRopeInventory
    from flext_infra._utilities import FlextInfraUtilitiesRopeModulePatch
    from flext_infra._utilities import FlextInfraUtilitiesRopeRuntime
    from flext_infra._utilities import FlextInfraUtilitiesRopeRuntimeBase
    from flext_infra._utilities import FlextInfraUtilitiesRopeRuntimeModules
    from flext_infra._utilities import FlextInfraUtilitiesRopeRuntimeRefactors
    from flext_infra._utilities import FlextInfraUtilitiesRopeRuntimeTypes
    from flext_infra._utilities import FlextInfraUtilitiesRopeSource
    from flext_infra._utilities import FlextInfraUtilitiesRopeSourceBases
    from flext_infra._utilities import FlextInfraUtilitiesRopeStructure
    from flext_infra._utilities import FlextInfraUtilitiesSemanticCutover
    from flext_infra._utilities import FlextInfraUtilitiesTransformerHeader
    from flext_infra._utilities import FlextInfraUtilitiesTransformerHeaderParser
    from flext_infra._utilities import FlextInfraUtilitiesVersioning
    from flext_infra._utilities import FlextInfraUtilitiesWorkspaceFingerprint
    from flext_infra._utilities import FlextInfraUtilitiesWorkspaceManifest
    from flext_infra._utilities import FlextInfraWorktreeLifecycle
    from flext_infra._utilities import FlextInfraWorktreeProvisioning


__all__: tuple[str, ...] = (
    "FlextInfraMypyDarwinSupervisor",
    "FlextInfraMypyProfiler",
    "FlextInfraRopeProject",
    "FlextInfraUtilitiesBase",
    "FlextInfraUtilitiesCodegen",
    "FlextInfraUtilitiesCodegenFacades",
    "FlextInfraUtilitiesCodegenFilePlan",
    "FlextInfraUtilitiesCodegenNamespace",
    "FlextInfraUtilitiesCodegenPathCutover",
    "FlextInfraUtilitiesCodemodProject",
    "FlextInfraUtilitiesCodemodRules",
    "FlextInfraUtilitiesCompatibilityAliasValidation",
    "FlextInfraUtilitiesDeferredSelfReferenceRewrite",
    "FlextInfraUtilitiesDependencies",
    "FlextInfraUtilitiesDiscovery",
    "FlextInfraUtilitiesDocs",
    "FlextInfraUtilitiesDocsApi",
    "FlextInfraUtilitiesDocsAudit",
    "FlextInfraUtilitiesDocsAuditDetectorsMixin",
    "FlextInfraUtilitiesDocsBuild",
    "FlextInfraUtilitiesDocsCollection",
    "FlextInfraUtilitiesDocsCollectionSources",
    "FlextInfraUtilitiesDocsCollectionVerify",
    "FlextInfraUtilitiesDocsCommandContractMixin",
    "FlextInfraUtilitiesDocsContract",
    "FlextInfraUtilitiesDocsFix",
    "FlextInfraUtilitiesDocsGenerate",
    "FlextInfraUtilitiesDocsGeneratePlanMixin",
    "FlextInfraUtilitiesDocsGenerateProjectMixin",
    "FlextInfraUtilitiesDocsGenerateRootMixin",
    "FlextInfraUtilitiesDocsGenerateSourcesMixin",
    "FlextInfraUtilitiesDocsGithubLinks",
    "FlextInfraUtilitiesDocsGuidesMixin",
    "FlextInfraUtilitiesDocsRender",
    "FlextInfraUtilitiesDocsScope",
    "FlextInfraUtilitiesDocsScopeBuildMixin",
    "FlextInfraUtilitiesDocsScopePathsMixin",
    "FlextInfraUtilitiesDocsScopePolicyMixin",
    "FlextInfraUtilitiesDocsScopeProjectsMixin",
    "FlextInfraUtilitiesDocsScopeSelectionMixin",
    "FlextInfraUtilitiesDocsScopeStateMixin",
    "FlextInfraUtilitiesDocsValidate",
    "FlextInfraUtilitiesGit",
    "FlextInfraUtilitiesGitAttestationMixin",
    "FlextInfraUtilitiesGitMutationScopeMixin",
    "FlextInfraUtilitiesGitRemote",
    "FlextInfraUtilitiesGitRepo",
    "FlextInfraUtilitiesGitScopeMixin",
    "FlextInfraUtilitiesGitSemanticIdentityMixin",
    "FlextInfraUtilitiesGitSemanticIndexMixin",
    "FlextInfraUtilitiesGitSemanticLaneMixin",
    "FlextInfraUtilitiesGitSemanticPathsMixin",
    "FlextInfraUtilitiesGitSemanticPublishMixin",
    "FlextInfraUtilitiesGitSemanticRefsMixin",
    "FlextInfraUtilitiesGitSemanticSubmoduleMixin",
    "FlextInfraUtilitiesGitSemanticWorktreeMixin",
    "FlextInfraUtilitiesGitStateCaptureMixin",
    "FlextInfraUtilitiesGitStateCheckpointMixin",
    "FlextInfraUtilitiesGitStateFilesMixin",
    "FlextInfraUtilitiesGitStatePublicationMixin",
    "FlextInfraUtilitiesGitStateSnapshotMixin",
    "FlextInfraUtilitiesGitStateTransitionMixin",
    "FlextInfraUtilitiesGitStateTreesMixin",
    "FlextInfraUtilitiesGitWorktreeCheckpointMixin",
    "FlextInfraUtilitiesGitWorktreeDiscoveryMixin",
    "FlextInfraUtilitiesGitWorktreeFactsMixin",
    "FlextInfraUtilitiesGitWorktreeIO",
    "FlextInfraUtilitiesGitWorktreeMaterializationMixin",
    "FlextInfraUtilitiesGitWorktreeMeasureMixin",
    "FlextInfraUtilitiesGitWorktreeMixin",
    "FlextInfraUtilitiesGitWorktreePatchMixin",
    "FlextInfraUtilitiesGitWorktreeRemovalMixin",
    "FlextInfraUtilitiesGitWorktreeRootsMixin",
    "FlextInfraUtilitiesGitWorktreeStatusMixin",
    "FlextInfraUtilitiesGitignore",
    "FlextInfraUtilitiesIteration",
    "FlextInfraUtilitiesIterationDirectory",
    "FlextInfraUtilitiesIterationMatching",
    "FlextInfraUtilitiesIterationWorkspace",
    "FlextInfraUtilitiesLintRecipes",
    "FlextInfraUtilitiesLogParser",
    "FlextInfraUtilitiesManagedConflicts",
    "FlextInfraUtilitiesNamespaceConfig",
    "FlextInfraUtilitiesNetwork",
    "FlextInfraUtilitiesPrivateImportAncestry",
    "FlextInfraUtilitiesPrivateImportFacades",
    "FlextInfraUtilitiesPrivateImportValidation",
    "FlextInfraUtilitiesProcess",
    "FlextInfraUtilitiesProjectDiscovery",
    "FlextInfraUtilitiesProjectDiscoveryCandidatesMixin",
    "FlextInfraUtilitiesProjectDiscoveryShapeMixin",
    "FlextInfraUtilitiesProjectManagedArtifacts",
    "FlextInfraUtilitiesPromoted",
    "FlextInfraUtilitiesPromotedCommands",
    "FlextInfraUtilitiesPromotedExecution",
    "FlextInfraUtilitiesPromotedInvocation",
    "FlextInfraUtilitiesPromotedRendering",
    "FlextInfraUtilitiesPromotedWorkspace",
    "FlextInfraUtilitiesProtectedEdit",
    "FlextInfraUtilitiesProtectedEditApply",
    "FlextInfraUtilitiesProtectedEditLinting",
    "FlextInfraUtilitiesProtectedEditPreview",
    "FlextInfraUtilitiesProtectedEditWrites",
    "FlextInfraUtilitiesPyproject",
    "FlextInfraUtilitiesPyprojectConform",
    "FlextInfraUtilitiesPyprojectConformBase",
    "FlextInfraUtilitiesPyprojectDocument",
    "FlextInfraUtilitiesPyprojectOverlay",
    "FlextInfraUtilitiesPyprojectRequirements",
    "FlextInfraUtilitiesPyprojectSession",
    "FlextInfraUtilitiesPyprojectTomlPhases",
    "FlextInfraUtilitiesPyprojectUvSources",
    "FlextInfraUtilitiesPyrefly",
    "FlextInfraUtilitiesQualifiedNames",
    "FlextInfraUtilitiesRefactor",
    "FlextInfraUtilitiesRefactorCensus",
    "FlextInfraUtilitiesRefactorNamespaceCommon",
    "FlextInfraUtilitiesRefactorNamespaceFlext",
    "FlextInfraUtilitiesRefactorNamespaceMoves",
    "FlextInfraUtilitiesRelease",
    "FlextInfraUtilitiesRepository",
    "FlextInfraUtilitiesResourceLimits",
    "FlextInfraUtilitiesRopeAnalysis",
    "FlextInfraUtilitiesRopeAnalysisAstHelpers",
    "FlextInfraUtilitiesRopeAnalysisBase",
    "FlextInfraUtilitiesRopeAnalysisExports",
    "FlextInfraUtilitiesRopeAnalysisImportState",
    "FlextInfraUtilitiesRopeAnalysisIntrospection",
    "FlextInfraUtilitiesRopeAnalysisSourceScan",
    "FlextInfraUtilitiesRopeAnalysisWorkspace",
    "FlextInfraUtilitiesRopeClassMove",
    "FlextInfraUtilitiesRopeCore",
    "FlextInfraUtilitiesRopeCorePyModuleMixin",
    "FlextInfraUtilitiesRopeCoreResourcesMixin",
    "FlextInfraUtilitiesRopeHelpers",
    "FlextInfraUtilitiesRopeImports",
    "FlextInfraUtilitiesRopeInventory",
    "FlextInfraUtilitiesRopeMethodOrderMixin",
    "FlextInfraUtilitiesRopeModulePatch",
    "FlextInfraUtilitiesRopeRuntime",
    "FlextInfraUtilitiesRopeRuntimeBase",
    "FlextInfraUtilitiesRopeRuntimeModules",
    "FlextInfraUtilitiesRopeRuntimeRefactors",
    "FlextInfraUtilitiesRopeRuntimeTypes",
    "FlextInfraUtilitiesRopeSource",
    "FlextInfraUtilitiesRopeSourceBases",
    "FlextInfraUtilitiesRopeStructure",
    "FlextInfraUtilitiesSemanticCutover",
    "FlextInfraUtilitiesSemanticCutoverAliasCst",
    "FlextInfraUtilitiesSemanticCutoverAliases",
    "FlextInfraUtilitiesSemanticCutoverBase",
    "FlextInfraUtilitiesSemanticCutoverBindings",
    "FlextInfraUtilitiesSemanticCutoverClassScope",
    "FlextInfraUtilitiesSemanticCutoverDynamicEnvironment",
    "FlextInfraUtilitiesSemanticCutoverEdits",
    "FlextInfraUtilitiesSemanticCutoverFacadeBaseCst",
    "FlextInfraUtilitiesSemanticCutoverFacadeBases",
    "FlextInfraUtilitiesSemanticCutoverFacadeOwners",
    "FlextInfraUtilitiesSemanticCutoverModelFields",
    "FlextInfraUtilitiesSemanticCutoverModelFieldsBindings",
    "FlextInfraUtilitiesSemanticCutoverModuleLayout",
    "FlextInfraUtilitiesSemanticCutoverNesting",
    "FlextInfraUtilitiesSemanticCutoverNestingCst",
    "FlextInfraUtilitiesSemanticCutoverNestingModuleAliases",
    "FlextInfraUtilitiesSemanticCutoverNestingOwner",
    "FlextInfraUtilitiesSemanticCutoverNestingReferences",
    "FlextInfraUtilitiesSemanticCutoverPrivateImportCst",
    "FlextInfraUtilitiesSemanticCutoverPrivateImports",
    "FlextInfraUtilitiesSemanticCutoverSelfFacade",
    "FlextInfraUtilitiesSemanticFamilyFlatten",
    "FlextInfraUtilitiesSemanticFamilyReferences",
    "FlextInfraUtilitiesSemanticFamilyTypeReferences",
    "FlextInfraUtilitiesSemanticHelperReferences",
    "FlextInfraUtilitiesSemanticNestingTypes",
    "FlextInfraUtilitiesTransformerHeader",
    "FlextInfraUtilitiesTransformerHeaderParser",
    "FlextInfraUtilitiesVersioning",
    "FlextInfraUtilitiesWorkspaceFingerprint",
    "FlextInfraUtilitiesWorkspaceManifest",
    "FlextInfraWorktreeLifecycle",
    "FlextInfraWorktreeProvisioning",
    "_git",
    "_promoted",
    "_pyproject",
    "_rope",
    "_rope_analysis",
    "_semantic_cutover",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraMypyDarwinSupervisor": "._mypy_supervisor",
        "FlextInfraMypyProfiler": "._mypy_profile",
        "FlextInfraRopeProject": "._rope.project",
        "FlextInfraUtilitiesBase": ".base",
        "FlextInfraUtilitiesCodegen": ".codegen",
        "FlextInfraUtilitiesCodegenFacades": ".codegen_facades",
        "FlextInfraUtilitiesCodegenFilePlan": ".codegen_file_plan",
        "FlextInfraUtilitiesCodegenNamespace": ".namespace",
        "FlextInfraUtilitiesCodegenPathCutover": ".codegen_path_cutover",
        "FlextInfraUtilitiesCodemodProject": ".codemod_project",
        "FlextInfraUtilitiesCodemodRules": ".codemod_rules",
        "FlextInfraUtilitiesCompatibilityAliasValidation": (
            ".compatibility_alias_validation"
        ),
        "FlextInfraUtilitiesDeferredSelfReferenceRewrite": (
            ".deferred_self_reference_rewrite"
        ),
        "FlextInfraUtilitiesDependencies": ".dependencies",
        "FlextInfraUtilitiesDiscovery": ".discovery",
        "FlextInfraUtilitiesDocs": ".docs",
        "FlextInfraUtilitiesDocsApi": ".docs_api",
        "FlextInfraUtilitiesDocsAudit": ".docs_audit",
        "FlextInfraUtilitiesDocsAuditDetectorsMixin": "._docs_audit_detectors",
        "FlextInfraUtilitiesDocsBuild": ".docs_build",
        "FlextInfraUtilitiesDocsCollection": ".docs_collection",
        "FlextInfraUtilitiesDocsCollectionSources": ".docs_collection_sources",
        "FlextInfraUtilitiesDocsCollectionVerify": ".docs_collection_verify",
        "FlextInfraUtilitiesDocsCommandContractMixin": "._docs_command_contract",
        "FlextInfraUtilitiesDocsContract": ".docs_contract",
        "FlextInfraUtilitiesDocsFix": ".docs_fix",
        "FlextInfraUtilitiesDocsGenerate": ".docs_generate",
        "FlextInfraUtilitiesDocsGeneratePlanMixin": "._docs_generate_plan",
        "FlextInfraUtilitiesDocsGenerateProjectMixin": "._docs_generate_project",
        "FlextInfraUtilitiesDocsGenerateRootMixin": "._docs_generate_root",
        "FlextInfraUtilitiesDocsGenerateSourcesMixin": "._docs_generate_sources",
        "FlextInfraUtilitiesDocsGithubLinks": "._docs_github_links",
        "FlextInfraUtilitiesDocsGuidesMixin": "._docs_guides",
        "FlextInfraUtilitiesDocsRender": ".docs_render",
        "FlextInfraUtilitiesDocsScope": ".docs_scope",
        "FlextInfraUtilitiesDocsScopeBuildMixin": "._docs_scope_build",
        "FlextInfraUtilitiesDocsScopePathsMixin": "._docs_scope_paths",
        "FlextInfraUtilitiesDocsScopePolicyMixin": "._docs_scope_policy",
        "FlextInfraUtilitiesDocsScopeProjectsMixin": "._docs_scope_projects",
        "FlextInfraUtilitiesDocsScopeSelectionMixin": "._docs_scope_selection",
        "FlextInfraUtilitiesDocsScopeStateMixin": "._docs_scope_state",
        "FlextInfraUtilitiesDocsValidate": ".docs_validate",
        "FlextInfraUtilitiesGit": ".git",
        "FlextInfraUtilitiesGitAttestationMixin": "._git.attestation",
        "FlextInfraUtilitiesGitMutationScopeMixin": "._git.mutation_scope",
        "FlextInfraUtilitiesGitRemote": "._git.remote",
        "FlextInfraUtilitiesGitRepo": "._git.repo",
        "FlextInfraUtilitiesGitScopeMixin": "._git.scope",
        "FlextInfraUtilitiesGitSemanticIdentityMixin": "._git.semantic_identity",
        "FlextInfraUtilitiesGitSemanticIndexMixin": "._git.semantic_index",
        "FlextInfraUtilitiesGitSemanticLaneMixin": "._git.semantic_lane",
        "FlextInfraUtilitiesGitSemanticPathsMixin": "._git.semantic_paths",
        "FlextInfraUtilitiesGitSemanticPublishMixin": "._git.semantic_publish",
        "FlextInfraUtilitiesGitSemanticRefsMixin": "._git.semantic_refs",
        "FlextInfraUtilitiesGitSemanticSubmoduleMixin": "._git.semantic_submodule",
        "FlextInfraUtilitiesGitSemanticWorktreeMixin": "._git.semantic_worktree",
        "FlextInfraUtilitiesGitStateCaptureMixin": "._git.state_capture",
        "FlextInfraUtilitiesGitStateCheckpointMixin": "._git.state_checkpoint",
        "FlextInfraUtilitiesGitStateFilesMixin": "._git.state_files",
        "FlextInfraUtilitiesGitStatePublicationMixin": "._git.state_publication",
        "FlextInfraUtilitiesGitStateSnapshotMixin": "._git.state_snapshot",
        "FlextInfraUtilitiesGitStateTransitionMixin": "._git.state_transition",
        "FlextInfraUtilitiesGitStateTreesMixin": "._git.state_trees",
        "FlextInfraUtilitiesGitWorktreeCheckpointMixin": "._git.worktree_checkpoint",
        "FlextInfraUtilitiesGitWorktreeDiscoveryMixin": "._git.worktree_discovery",
        "FlextInfraUtilitiesGitWorktreeFactsMixin": "._git.worktree_facts",
        "FlextInfraUtilitiesGitWorktreeIO": "._git.worktree_io",
        "FlextInfraUtilitiesGitWorktreeMaterializationMixin": (
            "._git.worktree_materialization"
        ),
        "FlextInfraUtilitiesGitWorktreeMeasureMixin": "._git.worktree_measure",
        "FlextInfraUtilitiesGitWorktreeMixin": "._git.worktree",
        "FlextInfraUtilitiesGitWorktreePatchMixin": "._git.worktree_patch",
        "FlextInfraUtilitiesGitWorktreeRemovalMixin": "._git.worktree_removal",
        "FlextInfraUtilitiesGitWorktreeRootsMixin": "._git.worktree_roots",
        "FlextInfraUtilitiesGitWorktreeStatusMixin": "._git.worktree_status",
        "FlextInfraUtilitiesGitignore": ".gitignore",
        "FlextInfraUtilitiesIteration": ".iteration",
        "FlextInfraUtilitiesIterationDirectory": ".iteration_directory",
        "FlextInfraUtilitiesIterationMatching": ".iteration_matching",
        "FlextInfraUtilitiesIterationWorkspace": ".iteration_workspace",
        "FlextInfraUtilitiesLintRecipes": ".lint_recipes",
        "FlextInfraUtilitiesLogParser": ".log_parser",
        "FlextInfraUtilitiesManagedConflicts": ".managed_conflicts",
        "FlextInfraUtilitiesNamespaceConfig": ".namespace_config",
        "FlextInfraUtilitiesNetwork": ".network",
        "FlextInfraUtilitiesPrivateImportAncestry": ".private_import_ancestry",
        "FlextInfraUtilitiesPrivateImportFacades": ".private_import_facades",
        "FlextInfraUtilitiesPrivateImportValidation": ".private_import_validation",
        "FlextInfraUtilitiesProcess": ".process",
        "FlextInfraUtilitiesProjectDiscovery": ".project_discovery",
        "FlextInfraUtilitiesProjectDiscoveryCandidatesMixin": (
            "._project_discovery_candidates"
        ),
        "FlextInfraUtilitiesProjectDiscoveryShapeMixin": "._project_discovery_shape",
        "FlextInfraUtilitiesProjectManagedArtifacts": ".project_managed_artifacts",
        "FlextInfraUtilitiesPromoted": ".promoted",
        "FlextInfraUtilitiesPromotedCommands": "._promoted.commands",
        "FlextInfraUtilitiesPromotedExecution": "._promoted.execution",
        "FlextInfraUtilitiesPromotedInvocation": "._promoted.invocation",
        "FlextInfraUtilitiesPromotedRendering": "._promoted.rendering",
        "FlextInfraUtilitiesPromotedWorkspace": "._promoted.workspace",
        "FlextInfraUtilitiesProtectedEdit": ".protected_edit",
        "FlextInfraUtilitiesProtectedEditApply": ".protected_edit_apply",
        "FlextInfraUtilitiesProtectedEditLinting": ".protected_edit_linting",
        "FlextInfraUtilitiesProtectedEditPreview": ".protected_edit_preview",
        "FlextInfraUtilitiesProtectedEditWrites": ".protected_edit_writes",
        "FlextInfraUtilitiesPyproject": ".pyproject",
        "FlextInfraUtilitiesPyprojectConform": ".pyproject_conform",
        "FlextInfraUtilitiesPyprojectConformBase": "._pyproject.base",
        "FlextInfraUtilitiesPyprojectDocument": "._pyproject.document",
        "FlextInfraUtilitiesPyprojectOverlay": "._pyproject.overlay",
        "FlextInfraUtilitiesPyprojectRequirements": "._pyproject.requirements",
        "FlextInfraUtilitiesPyprojectSession": "._pyproject.session",
        "FlextInfraUtilitiesPyprojectTomlPhases": "._pyproject.toml_phases",
        "FlextInfraUtilitiesPyprojectUvSources": "._pyproject.uv_sources",
        "FlextInfraUtilitiesPyrefly": ".pyrefly",
        "FlextInfraUtilitiesQualifiedNames": ".qualified_names",
        "FlextInfraUtilitiesRefactor": ".refactor",
        "FlextInfraUtilitiesRefactorCensus": ".census",
        "FlextInfraUtilitiesRefactorNamespaceCommon": ".namespace_common",
        "FlextInfraUtilitiesRefactorNamespaceFlext": ".namespace_analysis",
        "FlextInfraUtilitiesRefactorNamespaceMoves": ".namespace_moves",
        "FlextInfraUtilitiesRelease": ".release",
        "FlextInfraUtilitiesRepository": ".repository",
        "FlextInfraUtilitiesResourceLimits": ".resource_limits",
        "FlextInfraUtilitiesRopeAnalysis": ".rope_analysis",
        "FlextInfraUtilitiesRopeAnalysisAstHelpers": "._rope_analysis.asthelpers",
        "FlextInfraUtilitiesRopeAnalysisBase": "._rope_analysis.base",
        "FlextInfraUtilitiesRopeAnalysisExports": "._rope_analysis.exports",
        "FlextInfraUtilitiesRopeAnalysisImportState": "._rope_analysis.importstate",
        "FlextInfraUtilitiesRopeAnalysisIntrospection": ".rope_analysis_introspection",
        "FlextInfraUtilitiesRopeAnalysisSourceScan": "._rope_analysis.sourcescan",
        "FlextInfraUtilitiesRopeAnalysisWorkspace": ".rope_analysis_workspace",
        "FlextInfraUtilitiesRopeClassMove": ".rope_class_move",
        "FlextInfraUtilitiesRopeCore": ".rope_core",
        "FlextInfraUtilitiesRopeCorePyModuleMixin": "._rope_core_pymodule",
        "FlextInfraUtilitiesRopeCoreResourcesMixin": "._rope_core_resources",
        "FlextInfraUtilitiesRopeHelpers": ".rope_helpers",
        "FlextInfraUtilitiesRopeImports": ".rope_imports",
        "FlextInfraUtilitiesRopeInventory": ".rope_inventory",
        "FlextInfraUtilitiesRopeMethodOrderMixin": "._rope_method_order",
        "FlextInfraUtilitiesRopeModulePatch": ".rope_module_patch",
        "FlextInfraUtilitiesRopeRuntime": ".rope_runtime",
        "FlextInfraUtilitiesRopeRuntimeBase": ".rope_runtime_base",
        "FlextInfraUtilitiesRopeRuntimeModules": ".rope_runtime_modules",
        "FlextInfraUtilitiesRopeRuntimeRefactors": ".rope_runtime_refactors",
        "FlextInfraUtilitiesRopeRuntimeTypes": ".rope_runtime_types",
        "FlextInfraUtilitiesRopeSource": ".rope_source",
        "FlextInfraUtilitiesRopeSourceBases": ".rope_source_bases",
        "FlextInfraUtilitiesRopeStructure": ".rope_structure",
        "FlextInfraUtilitiesSemanticCutover": ".semantic_cutover",
        "FlextInfraUtilitiesSemanticCutoverAliasCst": "._semantic_cutover.alias_cst",
        "FlextInfraUtilitiesSemanticCutoverAliases": "._semantic_cutover.aliases",
        "FlextInfraUtilitiesSemanticCutoverBase": "._semantic_cutover.base",
        "FlextInfraUtilitiesSemanticCutoverBindings": "._semantic_cutover.bindings",
        "FlextInfraUtilitiesSemanticCutoverClassScope": (
            "._semantic_cutover.class_scope"
        ),
        "FlextInfraUtilitiesSemanticCutoverDynamicEnvironment": (
            "._semantic_cutover.dynamic_environment"
        ),
        "FlextInfraUtilitiesSemanticCutoverEdits": "._semantic_cutover.edits",
        "FlextInfraUtilitiesSemanticCutoverFacadeBaseCst": (
            "._semantic_cutover.facade_base_cst"
        ),
        "FlextInfraUtilitiesSemanticCutoverFacadeBases": (
            "._semantic_cutover.facade_bases"
        ),
        "FlextInfraUtilitiesSemanticCutoverFacadeOwners": (
            "._semantic_cutover.facade_owners"
        ),
        "FlextInfraUtilitiesSemanticCutoverModelFields": (
            "._semantic_cutover.model_fields"
        ),
        "FlextInfraUtilitiesSemanticCutoverModelFieldsBindings": (
            "._semantic_cutover.model_fields_bindings"
        ),
        "FlextInfraUtilitiesSemanticCutoverModuleLayout": (
            "._semantic_cutover.module_layout"
        ),
        "FlextInfraUtilitiesSemanticCutoverNesting": "._semantic_cutover.nesting",
        "FlextInfraUtilitiesSemanticCutoverNestingCst": (
            "._semantic_cutover.nesting_cst"
        ),
        "FlextInfraUtilitiesSemanticCutoverNestingModuleAliases": (
            "._semantic_cutover.nesting_module_aliases"
        ),
        "FlextInfraUtilitiesSemanticCutoverNestingOwner": (
            "._semantic_cutover.nesting_owner"
        ),
        "FlextInfraUtilitiesSemanticCutoverNestingReferences": (
            "._semantic_cutover.nesting_references"
        ),
        "FlextInfraUtilitiesSemanticCutoverPrivateImportCst": (
            "._semantic_cutover.private_import_cst"
        ),
        "FlextInfraUtilitiesSemanticCutoverPrivateImports": (
            "._semantic_cutover.private_imports"
        ),
        "FlextInfraUtilitiesSemanticCutoverSelfFacade": (
            "._semantic_cutover.self_facade"
        ),
        "FlextInfraUtilitiesSemanticFamilyFlatten": "._semantic_cutover.family_flatten",
        "FlextInfraUtilitiesSemanticFamilyReferences": (
            "._semantic_cutover.family_references"
        ),
        "FlextInfraUtilitiesSemanticFamilyTypeReferences": (
            "._semantic_cutover.family_type_references"
        ),
        "FlextInfraUtilitiesSemanticHelperReferences": (
            "._semantic_cutover.helper_references"
        ),
        "FlextInfraUtilitiesSemanticNestingTypes": "._semantic_cutover.nesting_types",
        "FlextInfraUtilitiesTransformerHeader": ".transformer_header",
        "FlextInfraUtilitiesTransformerHeaderParser": ".transformer_header_parser",
        "FlextInfraUtilitiesVersioning": ".versioning",
        "FlextInfraUtilitiesWorkspaceFingerprint": ".workspace_fingerprint",
        "FlextInfraUtilitiesWorkspaceManifest": ".workspace_manifest",
        "FlextInfraWorktreeLifecycle": ".worktree_lifecycle",
        "FlextInfraWorktreeProvisioning": ".worktree_provisioning",
        "_git": "._git",
        "_promoted": "._promoted",
        "_pyproject": "._pyproject",
        "_rope": "._rope",
        "_rope_analysis": "._rope_analysis",
        "_semantic_cutover": "._semantic_cutover",
    }),
    public_exports=__all__,
)
