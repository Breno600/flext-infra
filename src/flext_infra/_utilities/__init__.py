# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from . import _git, _promoted, _pyproject, _rope, _rope_analysis, _semantic_cutover
    from ._docs_audit_detectors import FlextInfraUtilitiesDocsAuditDetectorsMixin
    from ._docs_command_contract import FlextInfraUtilitiesDocsCommandContractMixin
    from ._docs_generate_plan import FlextInfraUtilitiesDocsGeneratePlanMixin
    from ._docs_generate_project import FlextInfraUtilitiesDocsGenerateProjectMixin
    from ._docs_generate_root import FlextInfraUtilitiesDocsGenerateRootMixin
    from ._docs_generate_sources import FlextInfraUtilitiesDocsGenerateSourcesMixin
    from ._docs_github_links import FlextInfraUtilitiesDocsGithubLinks
    from ._docs_guides import FlextInfraUtilitiesDocsGuidesMixin
    from ._docs_scope_build import FlextInfraUtilitiesDocsScopeBuildMixin
    from ._docs_scope_paths import FlextInfraUtilitiesDocsScopePathsMixin
    from ._docs_scope_policy import FlextInfraUtilitiesDocsScopePolicyMixin
    from ._docs_scope_projects import FlextInfraUtilitiesDocsScopeProjectsMixin
    from ._docs_scope_selection import FlextInfraUtilitiesDocsScopeSelectionMixin
    from ._docs_scope_state import FlextInfraUtilitiesDocsScopeStateMixin
    from ._git.attestation import FlextInfraUtilitiesGitAttestationMixin
    from ._git.remote import FlextInfraUtilitiesGitRemote
    from ._git.repo import FlextInfraUtilitiesGitRepo
    from ._git.scope import FlextInfraUtilitiesGitScopeMixin
    from ._git.semantic_identity import FlextInfraUtilitiesGitSemanticIdentityMixin
    from ._git.semantic_index import FlextInfraUtilitiesGitSemanticIndexMixin
    from ._git.semantic_lane import FlextInfraUtilitiesGitSemanticLaneMixin
    from ._git.semantic_paths import FlextInfraUtilitiesGitSemanticPathsMixin
    from ._git.semantic_publish import FlextInfraUtilitiesGitSemanticPublishMixin
    from ._git.semantic_refs import FlextInfraUtilitiesGitSemanticRefsMixin
    from ._git.semantic_submodule import FlextInfraUtilitiesGitSemanticSubmoduleMixin
    from ._git.semantic_worktree import FlextInfraUtilitiesGitSemanticWorktreeMixin
    from ._git.worktree import FlextInfraUtilitiesGitWorktreeMixin
    from ._git.worktree_checkpoint import FlextInfraUtilitiesGitWorktreeCheckpointMixin
    from ._git.worktree_discovery import FlextInfraUtilitiesGitWorktreeDiscoveryMixin
    from ._git.worktree_facts import FlextInfraUtilitiesGitWorktreeFactsMixin
    from ._git.worktree_io import FlextInfraUtilitiesGitWorktreeIO
    from ._git.worktree_materialization import (
        FlextInfraUtilitiesGitWorktreeMaterializationMixin,
    )
    from ._git.worktree_measure import FlextInfraUtilitiesGitWorktreeMeasureMixin
    from ._git.worktree_patch import FlextInfraUtilitiesGitWorktreePatchMixin
    from ._git.worktree_removal import FlextInfraUtilitiesGitWorktreeRemovalMixin
    from ._git.worktree_roots import FlextInfraUtilitiesGitWorktreeRootsMixin
    from ._git.worktree_status import FlextInfraUtilitiesGitWorktreeStatusMixin
    from ._mypy_supervisor import FlextInfraMypyDarwinSupervisor
    from ._project_discovery_candidates import (
        FlextInfraUtilitiesProjectDiscoveryCandidatesMixin,
    )
    from ._project_discovery_shape import FlextInfraUtilitiesProjectDiscoveryShapeMixin
    from ._promoted.commands import FlextInfraUtilitiesPromotedCommands
    from ._promoted.execution import FlextInfraUtilitiesPromotedExecution
    from ._promoted.invocation import FlextInfraUtilitiesPromotedInvocation
    from ._promoted.rendering import FlextInfraUtilitiesPromotedRendering
    from ._promoted.workspace import FlextInfraUtilitiesPromotedWorkspace
    from ._pyproject.base import FlextInfraUtilitiesPyprojectConformBase
    from ._pyproject.document import FlextInfraUtilitiesPyprojectDocument
    from ._pyproject.overlay import FlextInfraUtilitiesPyprojectOverlay
    from ._pyproject.requirements import FlextInfraUtilitiesPyprojectRequirements
    from ._pyproject.toml_phases import FlextInfraUtilitiesPyprojectTomlPhases
    from ._pyproject.uv_sources import FlextInfraUtilitiesPyprojectUvSources
    from ._rope.project import FlextInfraRopeProject
    from ._rope_analysis.asthelpers import FlextInfraUtilitiesRopeAnalysisAstHelpers
    from ._rope_analysis.base import FlextInfraUtilitiesRopeAnalysisBase
    from ._rope_analysis.exports import FlextInfraUtilitiesRopeAnalysisExports
    from ._rope_analysis.importstate import FlextInfraUtilitiesRopeAnalysisImportState
    from ._rope_analysis.sourcescan import FlextInfraUtilitiesRopeAnalysisSourceScan
    from ._rope_bracket_balance import FlextInfraUtilitiesRopeBracketBalanceMixin
    from ._rope_core_pymodule import FlextInfraUtilitiesRopeCorePyModuleMixin
    from ._rope_core_resources import FlextInfraUtilitiesRopeCoreResourcesMixin
    from ._rope_method_order import FlextInfraUtilitiesRopeMethodOrderMixin
    from ._semantic_cutover.alias_cst import FlextInfraUtilitiesSemanticCutoverAliasCst
    from ._semantic_cutover.aliases import FlextInfraUtilitiesSemanticCutoverAliases
    from ._semantic_cutover.base import FlextInfraUtilitiesSemanticCutoverBase
    from ._semantic_cutover.edits import FlextInfraUtilitiesSemanticCutoverEdits
    from ._semantic_cutover.facade_base_cst import (
        FlextInfraUtilitiesSemanticCutoverFacadeBaseCst,
    )
    from ._semantic_cutover.facade_bases import (
        FlextInfraUtilitiesSemanticCutoverFacadeBases,
    )
    from ._semantic_cutover.facade_owners import (
        FlextInfraUtilitiesSemanticCutoverFacadeOwners,
    )
    from ._semantic_cutover.family_flatten import (
        FlextInfraUtilitiesSemanticFamilyFlatten,
    )
    from ._semantic_cutover.family_references import (
        FlextInfraUtilitiesSemanticFamilyReferences,
    )
    from ._semantic_cutover.family_type_references import (
        FlextInfraUtilitiesSemanticFamilyTypeReferences,
    )
    from ._semantic_cutover.helper_references import (
        FlextInfraUtilitiesSemanticHelperReferences,
    )
    from ._semantic_cutover.nesting import FlextInfraUtilitiesSemanticCutoverNesting
    from ._semantic_cutover.nesting_cst import (
        FlextInfraUtilitiesSemanticCutoverNestingCst,
    )
    from ._semantic_cutover.nesting_references import (
        FlextInfraUtilitiesSemanticCutoverNestingReferences,
    )
    from ._semantic_cutover.nesting_types import FlextInfraUtilitiesSemanticNestingTypes
    from ._semantic_cutover.private_import_cst import (
        FlextInfraUtilitiesSemanticCutoverPrivateImportCst,
    )
    from ._semantic_cutover.private_imports import (
        FlextInfraUtilitiesSemanticCutoverPrivateImports,
    )
    from .base import FlextInfraUtilitiesBase
    from .census import FlextInfraUtilitiesRefactorCensus
    from .codegen import FlextInfraUtilitiesCodegen
    from .codegen_facades import FlextInfraUtilitiesCodegenFacades
    from .codegen_file_plan import FlextInfraUtilitiesCodegenFilePlan
    from .codegen_path_cutover import FlextInfraUtilitiesCodegenPathCutover
    from .codemod_rules import FlextInfraUtilitiesCodemodRules
    from .compatibility_alias_validation import (
        FlextInfraUtilitiesCompatibilityAliasValidation,
    )
    from .deferred_self_reference_ast import FlextInfraUtilitiesDeferredSelfReference
    from .deferred_self_reference_rewrite import (
        FlextInfraUtilitiesDeferredSelfReferenceRewrite,
    )
    from .dependencies import FlextInfraUtilitiesDependencies
    from .discovery import FlextInfraUtilitiesDiscovery
    from .docs import FlextInfraUtilitiesDocs
    from .docs_api import FlextInfraUtilitiesDocsApi
    from .docs_audit import FlextInfraUtilitiesDocsAudit
    from .docs_build import FlextInfraUtilitiesDocsBuild
    from .docs_collection import FlextInfraUtilitiesDocsCollection
    from .docs_collection_sources import FlextInfraUtilitiesDocsCollectionSources
    from .docs_collection_verify import FlextInfraUtilitiesDocsCollectionVerify
    from .docs_contract import FlextInfraUtilitiesDocsContract
    from .docs_fix import FlextInfraUtilitiesDocsFix
    from .docs_generate import FlextInfraUtilitiesDocsGenerate
    from .docs_render import FlextInfraUtilitiesDocsRender
    from .docs_scope import FlextInfraUtilitiesDocsScope
    from .docs_validate import FlextInfraUtilitiesDocsValidate
    from .git import FlextInfraUtilitiesGit
    from .gitignore import FlextInfraUtilitiesGitignore
    from .iteration import FlextInfraUtilitiesIteration
    from .iteration_directory import FlextInfraUtilitiesIterationDirectory
    from .iteration_matching import FlextInfraUtilitiesIterationMatching
    from .iteration_project import FlextInfraUtilitiesIterationProject
    from .iteration_workspace import FlextInfraUtilitiesIterationWorkspace
    from .log_parser import FlextInfraUtilitiesLogParser
    from .managed_conflicts import FlextInfraUtilitiesManagedConflicts
    from .namespace import FlextInfraUtilitiesCodegenNamespace
    from .namespace_analysis import FlextInfraUtilitiesRefactorNamespaceFlext
    from .namespace_common import FlextInfraUtilitiesRefactorNamespaceCommon
    from .namespace_config import FlextInfraUtilitiesNamespaceConfig
    from .namespace_facades import FlextInfraUtilitiesRefactorNamespaceFacades
    from .namespace_moves import FlextInfraUtilitiesRefactorNamespaceMoves
    from .network import FlextInfraUtilitiesNetwork
    from .private_import_ancestry import FlextInfraUtilitiesPrivateImportAncestry
    from .private_import_facades import FlextInfraUtilitiesPrivateImportFacades
    from .private_import_validation import FlextInfraUtilitiesPrivateImportValidation
    from .process import FlextInfraUtilitiesProcess
    from .project_discovery import FlextInfraUtilitiesProjectDiscovery
    from .project_managed_artifacts import FlextInfraUtilitiesProjectManagedArtifacts
    from .promoted import FlextInfraUtilitiesPromoted
    from .protected_edit import FlextInfraUtilitiesProtectedEdit
    from .protected_edit_apply import FlextInfraUtilitiesProtectedEditApply
    from .protected_edit_linting import FlextInfraUtilitiesProtectedEditLinting
    from .protected_edit_preview import FlextInfraUtilitiesProtectedEditPreview
    from .protected_edit_writes import FlextInfraUtilitiesProtectedEditWrites
    from .pyproject import FlextInfraUtilitiesPyproject
    from .pyproject_conform import FlextInfraUtilitiesPyprojectConform
    from .pyrefly import FlextInfraUtilitiesPyrefly
    from .qualified_names import FlextInfraUtilitiesQualifiedNames
    from .refactor import FlextInfraUtilitiesRefactor
    from .refactor_discovery import FlextInfraUtilitiesRefactorDiscovery
    from .release import FlextInfraUtilitiesRelease
    from .repository import FlextInfraUtilitiesRepository
    from .resource_limits import FlextInfraUtilitiesResourceLimits
    from .rope_analysis import FlextInfraUtilitiesRopeAnalysis
    from .rope_analysis_introspection import (
        FlextInfraUtilitiesRopeAnalysisIntrospection,
    )
    from .rope_analysis_workspace import FlextInfraUtilitiesRopeAnalysisWorkspace
    from .rope_class_move import FlextInfraUtilitiesRopeClassMove
    from .rope_core import FlextInfraUtilitiesRopeCore
    from .rope_helpers import FlextInfraUtilitiesRopeHelpers
    from .rope_imports import FlextInfraUtilitiesRopeImports
    from .rope_inventory import FlextInfraUtilitiesRopeInventory
    from .rope_module_patch import FlextInfraUtilitiesRopeModulePatch
    from .rope_runtime import FlextInfraUtilitiesRopeRuntime
    from .rope_runtime_base import FlextInfraUtilitiesRopeRuntimeBase
    from .rope_runtime_modules import FlextInfraUtilitiesRopeRuntimeModules
    from .rope_runtime_refactors import FlextInfraUtilitiesRopeRuntimeRefactors
    from .rope_runtime_types import FlextInfraUtilitiesRopeRuntimeTypes
    from .rope_source import FlextInfraUtilitiesRopeSource
    from .rope_structure import FlextInfraUtilitiesRopeStructure
    from .safety import FlextInfraUtilitiesSafety
    from .semantic_cutover import FlextInfraUtilitiesSemanticCutover
    from .signature_rules import FlextInfraUtilitiesSignatureRules
    from .silent_failure_ast import FlextInfraUtilitiesSilentFailureAst
    from .silent_failure_ast_base import FlextInfraUtilitiesSilentFailureAstBase
    from .silent_failure_ast_rules import FlextInfraUtilitiesSilentFailureAstRules
    from .transformer_base import FlextInfraChangeTrackingTransformer
    from .transformer_header import FlextInfraUtilitiesTransformerHeader
    from .transformer_header_parser import FlextInfraUtilitiesTransformerHeaderParser
    from .versioning import FlextInfraUtilitiesVersioning
    from .workspace_fingerprint import FlextInfraUtilitiesWorkspaceFingerprint
    from .workspace_manifest import FlextInfraUtilitiesWorkspaceManifest
    from .worktree_lifecycle import FlextInfraWorktreeLifecycle
    from .worktree_provisioning import FlextInfraWorktreeProvisioning


__all__: tuple[str, ...] = (
    "FlextInfraChangeTrackingTransformer",
    "FlextInfraMypyDarwinSupervisor",
    "FlextInfraRopeProject",
    "FlextInfraUtilitiesBase",
    "FlextInfraUtilitiesCodegen",
    "FlextInfraUtilitiesCodegenFacades",
    "FlextInfraUtilitiesCodegenFilePlan",
    "FlextInfraUtilitiesCodegenNamespace",
    "FlextInfraUtilitiesCodegenPathCutover",
    "FlextInfraUtilitiesCodemodRules",
    "FlextInfraUtilitiesCompatibilityAliasValidation",
    "FlextInfraUtilitiesDeferredSelfReference",
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
    "FlextInfraUtilitiesIterationProject",
    "FlextInfraUtilitiesIterationWorkspace",
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
    "FlextInfraUtilitiesPyprojectTomlPhases",
    "FlextInfraUtilitiesPyprojectUvSources",
    "FlextInfraUtilitiesPyrefly",
    "FlextInfraUtilitiesQualifiedNames",
    "FlextInfraUtilitiesRefactor",
    "FlextInfraUtilitiesRefactorCensus",
    "FlextInfraUtilitiesRefactorDiscovery",
    "FlextInfraUtilitiesRefactorNamespaceCommon",
    "FlextInfraUtilitiesRefactorNamespaceFacades",
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
    "FlextInfraUtilitiesRopeBracketBalanceMixin",
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
    "FlextInfraUtilitiesRopeStructure",
    "FlextInfraUtilitiesSafety",
    "FlextInfraUtilitiesSemanticCutover",
    "FlextInfraUtilitiesSemanticCutoverAliasCst",
    "FlextInfraUtilitiesSemanticCutoverAliases",
    "FlextInfraUtilitiesSemanticCutoverBase",
    "FlextInfraUtilitiesSemanticCutoverEdits",
    "FlextInfraUtilitiesSemanticCutoverFacadeBaseCst",
    "FlextInfraUtilitiesSemanticCutoverFacadeBases",
    "FlextInfraUtilitiesSemanticCutoverFacadeOwners",
    "FlextInfraUtilitiesSemanticCutoverNesting",
    "FlextInfraUtilitiesSemanticCutoverNestingCst",
    "FlextInfraUtilitiesSemanticCutoverNestingReferences",
    "FlextInfraUtilitiesSemanticCutoverPrivateImportCst",
    "FlextInfraUtilitiesSemanticCutoverPrivateImports",
    "FlextInfraUtilitiesSemanticFamilyFlatten",
    "FlextInfraUtilitiesSemanticFamilyReferences",
    "FlextInfraUtilitiesSemanticFamilyTypeReferences",
    "FlextInfraUtilitiesSemanticHelperReferences",
    "FlextInfraUtilitiesSemanticNestingTypes",
    "FlextInfraUtilitiesSignatureRules",
    "FlextInfraUtilitiesSilentFailureAst",
    "FlextInfraUtilitiesSilentFailureAstBase",
    "FlextInfraUtilitiesSilentFailureAstRules",
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

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._docs_audit_detectors": ("FlextInfraUtilitiesDocsAuditDetectorsMixin",),
            "._docs_command_contract": ("FlextInfraUtilitiesDocsCommandContractMixin",),
            "._docs_generate_plan": ("FlextInfraUtilitiesDocsGeneratePlanMixin",),
            "._docs_generate_project": ("FlextInfraUtilitiesDocsGenerateProjectMixin",),
            "._docs_generate_root": ("FlextInfraUtilitiesDocsGenerateRootMixin",),
            "._docs_generate_sources": ("FlextInfraUtilitiesDocsGenerateSourcesMixin",),
            "._docs_github_links": ("FlextInfraUtilitiesDocsGithubLinks",),
            "._docs_guides": ("FlextInfraUtilitiesDocsGuidesMixin",),
            "._docs_scope_build": ("FlextInfraUtilitiesDocsScopeBuildMixin",),
            "._docs_scope_paths": ("FlextInfraUtilitiesDocsScopePathsMixin",),
            "._docs_scope_policy": ("FlextInfraUtilitiesDocsScopePolicyMixin",),
            "._docs_scope_projects": ("FlextInfraUtilitiesDocsScopeProjectsMixin",),
            "._docs_scope_selection": ("FlextInfraUtilitiesDocsScopeSelectionMixin",),
            "._docs_scope_state": ("FlextInfraUtilitiesDocsScopeStateMixin",),
            "._git": ("_git",),
            "._git.attestation": ("FlextInfraUtilitiesGitAttestationMixin",),
            "._git.remote": ("FlextInfraUtilitiesGitRemote",),
            "._git.repo": ("FlextInfraUtilitiesGitRepo",),
            "._git.scope": ("FlextInfraUtilitiesGitScopeMixin",),
            "._git.semantic_identity": ("FlextInfraUtilitiesGitSemanticIdentityMixin",),
            "._git.semantic_index": ("FlextInfraUtilitiesGitSemanticIndexMixin",),
            "._git.semantic_lane": ("FlextInfraUtilitiesGitSemanticLaneMixin",),
            "._git.semantic_paths": ("FlextInfraUtilitiesGitSemanticPathsMixin",),
            "._git.semantic_publish": ("FlextInfraUtilitiesGitSemanticPublishMixin",),
            "._git.semantic_refs": ("FlextInfraUtilitiesGitSemanticRefsMixin",),
            "._git.semantic_submodule": (
                "FlextInfraUtilitiesGitSemanticSubmoduleMixin",
            ),
            "._git.semantic_worktree": ("FlextInfraUtilitiesGitSemanticWorktreeMixin",),
            "._git.worktree": ("FlextInfraUtilitiesGitWorktreeMixin",),
            "._git.worktree_checkpoint": (
                "FlextInfraUtilitiesGitWorktreeCheckpointMixin",
            ),
            "._git.worktree_discovery": (
                "FlextInfraUtilitiesGitWorktreeDiscoveryMixin",
            ),
            "._git.worktree_facts": ("FlextInfraUtilitiesGitWorktreeFactsMixin",),
            "._git.worktree_io": ("FlextInfraUtilitiesGitWorktreeIO",),
            "._git.worktree_materialization": (
                "FlextInfraUtilitiesGitWorktreeMaterializationMixin",
            ),
            "._git.worktree_measure": ("FlextInfraUtilitiesGitWorktreeMeasureMixin",),
            "._git.worktree_patch": ("FlextInfraUtilitiesGitWorktreePatchMixin",),
            "._git.worktree_removal": ("FlextInfraUtilitiesGitWorktreeRemovalMixin",),
            "._git.worktree_roots": ("FlextInfraUtilitiesGitWorktreeRootsMixin",),
            "._git.worktree_status": ("FlextInfraUtilitiesGitWorktreeStatusMixin",),
            "._mypy_supervisor": ("FlextInfraMypyDarwinSupervisor",),
            "._project_discovery_candidates": (
                "FlextInfraUtilitiesProjectDiscoveryCandidatesMixin",
            ),
            "._project_discovery_shape": (
                "FlextInfraUtilitiesProjectDiscoveryShapeMixin",
            ),
            "._promoted": ("_promoted",),
            "._promoted.commands": ("FlextInfraUtilitiesPromotedCommands",),
            "._promoted.execution": ("FlextInfraUtilitiesPromotedExecution",),
            "._promoted.invocation": ("FlextInfraUtilitiesPromotedInvocation",),
            "._promoted.rendering": ("FlextInfraUtilitiesPromotedRendering",),
            "._promoted.workspace": ("FlextInfraUtilitiesPromotedWorkspace",),
            "._pyproject": ("_pyproject",),
            "._pyproject.base": ("FlextInfraUtilitiesPyprojectConformBase",),
            "._pyproject.document": ("FlextInfraUtilitiesPyprojectDocument",),
            "._pyproject.overlay": ("FlextInfraUtilitiesPyprojectOverlay",),
            "._pyproject.requirements": ("FlextInfraUtilitiesPyprojectRequirements",),
            "._pyproject.toml_phases": ("FlextInfraUtilitiesPyprojectTomlPhases",),
            "._pyproject.uv_sources": ("FlextInfraUtilitiesPyprojectUvSources",),
            "._rope": ("_rope",),
            "._rope.project": ("FlextInfraRopeProject",),
            "._rope_analysis": ("_rope_analysis",),
            "._rope_analysis.asthelpers": (
                "FlextInfraUtilitiesRopeAnalysisAstHelpers",
            ),
            "._rope_analysis.base": ("FlextInfraUtilitiesRopeAnalysisBase",),
            "._rope_analysis.exports": ("FlextInfraUtilitiesRopeAnalysisExports",),
            "._rope_analysis.importstate": (
                "FlextInfraUtilitiesRopeAnalysisImportState",
            ),
            "._rope_analysis.sourcescan": (
                "FlextInfraUtilitiesRopeAnalysisSourceScan",
            ),
            "._rope_bracket_balance": ("FlextInfraUtilitiesRopeBracketBalanceMixin",),
            "._rope_core_pymodule": ("FlextInfraUtilitiesRopeCorePyModuleMixin",),
            "._rope_core_resources": ("FlextInfraUtilitiesRopeCoreResourcesMixin",),
            "._rope_method_order": ("FlextInfraUtilitiesRopeMethodOrderMixin",),
            "._semantic_cutover": ("_semantic_cutover",),
            "._semantic_cutover.alias_cst": (
                "FlextInfraUtilitiesSemanticCutoverAliasCst",
            ),
            "._semantic_cutover.aliases": (
                "FlextInfraUtilitiesSemanticCutoverAliases",
            ),
            "._semantic_cutover.base": ("FlextInfraUtilitiesSemanticCutoverBase",),
            "._semantic_cutover.edits": ("FlextInfraUtilitiesSemanticCutoverEdits",),
            "._semantic_cutover.facade_base_cst": (
                "FlextInfraUtilitiesSemanticCutoverFacadeBaseCst",
            ),
            "._semantic_cutover.facade_bases": (
                "FlextInfraUtilitiesSemanticCutoverFacadeBases",
            ),
            "._semantic_cutover.facade_owners": (
                "FlextInfraUtilitiesSemanticCutoverFacadeOwners",
            ),
            "._semantic_cutover.family_flatten": (
                "FlextInfraUtilitiesSemanticFamilyFlatten",
            ),
            "._semantic_cutover.family_references": (
                "FlextInfraUtilitiesSemanticFamilyReferences",
            ),
            "._semantic_cutover.family_type_references": (
                "FlextInfraUtilitiesSemanticFamilyTypeReferences",
            ),
            "._semantic_cutover.helper_references": (
                "FlextInfraUtilitiesSemanticHelperReferences",
            ),
            "._semantic_cutover.nesting": (
                "FlextInfraUtilitiesSemanticCutoverNesting",
            ),
            "._semantic_cutover.nesting_cst": (
                "FlextInfraUtilitiesSemanticCutoverNestingCst",
            ),
            "._semantic_cutover.nesting_references": (
                "FlextInfraUtilitiesSemanticCutoverNestingReferences",
            ),
            "._semantic_cutover.nesting_types": (
                "FlextInfraUtilitiesSemanticNestingTypes",
            ),
            "._semantic_cutover.private_import_cst": (
                "FlextInfraUtilitiesSemanticCutoverPrivateImportCst",
            ),
            "._semantic_cutover.private_imports": (
                "FlextInfraUtilitiesSemanticCutoverPrivateImports",
            ),
            ".base": ("FlextInfraUtilitiesBase",),
            ".census": ("FlextInfraUtilitiesRefactorCensus",),
            ".codegen": ("FlextInfraUtilitiesCodegen",),
            ".codegen_facades": ("FlextInfraUtilitiesCodegenFacades",),
            ".codegen_file_plan": ("FlextInfraUtilitiesCodegenFilePlan",),
            ".codegen_path_cutover": ("FlextInfraUtilitiesCodegenPathCutover",),
            ".codemod_rules": ("FlextInfraUtilitiesCodemodRules",),
            ".compatibility_alias_validation": (
                "FlextInfraUtilitiesCompatibilityAliasValidation",
            ),
            ".deferred_self_reference_ast": (
                "FlextInfraUtilitiesDeferredSelfReference",
            ),
            ".deferred_self_reference_rewrite": (
                "FlextInfraUtilitiesDeferredSelfReferenceRewrite",
            ),
            ".dependencies": ("FlextInfraUtilitiesDependencies",),
            ".discovery": ("FlextInfraUtilitiesDiscovery",),
            ".docs": ("FlextInfraUtilitiesDocs",),
            ".docs_api": ("FlextInfraUtilitiesDocsApi",),
            ".docs_audit": ("FlextInfraUtilitiesDocsAudit",),
            ".docs_build": ("FlextInfraUtilitiesDocsBuild",),
            ".docs_collection": ("FlextInfraUtilitiesDocsCollection",),
            ".docs_collection_sources": ("FlextInfraUtilitiesDocsCollectionSources",),
            ".docs_collection_verify": ("FlextInfraUtilitiesDocsCollectionVerify",),
            ".docs_contract": ("FlextInfraUtilitiesDocsContract",),
            ".docs_fix": ("FlextInfraUtilitiesDocsFix",),
            ".docs_generate": ("FlextInfraUtilitiesDocsGenerate",),
            ".docs_render": ("FlextInfraUtilitiesDocsRender",),
            ".docs_scope": ("FlextInfraUtilitiesDocsScope",),
            ".docs_validate": ("FlextInfraUtilitiesDocsValidate",),
            ".git": ("FlextInfraUtilitiesGit",),
            ".gitignore": ("FlextInfraUtilitiesGitignore",),
            ".iteration": ("FlextInfraUtilitiesIteration",),
            ".iteration_directory": ("FlextInfraUtilitiesIterationDirectory",),
            ".iteration_matching": ("FlextInfraUtilitiesIterationMatching",),
            ".iteration_project": ("FlextInfraUtilitiesIterationProject",),
            ".iteration_workspace": ("FlextInfraUtilitiesIterationWorkspace",),
            ".log_parser": ("FlextInfraUtilitiesLogParser",),
            ".managed_conflicts": ("FlextInfraUtilitiesManagedConflicts",),
            ".namespace": ("FlextInfraUtilitiesCodegenNamespace",),
            ".namespace_analysis": ("FlextInfraUtilitiesRefactorNamespaceFlext",),
            ".namespace_common": ("FlextInfraUtilitiesRefactorNamespaceCommon",),
            ".namespace_config": ("FlextInfraUtilitiesNamespaceConfig",),
            ".namespace_facades": ("FlextInfraUtilitiesRefactorNamespaceFacades",),
            ".namespace_moves": ("FlextInfraUtilitiesRefactorNamespaceMoves",),
            ".network": ("FlextInfraUtilitiesNetwork",),
            ".private_import_ancestry": ("FlextInfraUtilitiesPrivateImportAncestry",),
            ".private_import_facades": ("FlextInfraUtilitiesPrivateImportFacades",),
            ".private_import_validation": (
                "FlextInfraUtilitiesPrivateImportValidation",
            ),
            ".process": ("FlextInfraUtilitiesProcess",),
            ".project_discovery": ("FlextInfraUtilitiesProjectDiscovery",),
            ".project_managed_artifacts": (
                "FlextInfraUtilitiesProjectManagedArtifacts",
            ),
            ".promoted": ("FlextInfraUtilitiesPromoted",),
            ".protected_edit": ("FlextInfraUtilitiesProtectedEdit",),
            ".protected_edit_apply": ("FlextInfraUtilitiesProtectedEditApply",),
            ".protected_edit_linting": ("FlextInfraUtilitiesProtectedEditLinting",),
            ".protected_edit_preview": ("FlextInfraUtilitiesProtectedEditPreview",),
            ".protected_edit_writes": ("FlextInfraUtilitiesProtectedEditWrites",),
            ".pyproject": ("FlextInfraUtilitiesPyproject",),
            ".pyproject_conform": ("FlextInfraUtilitiesPyprojectConform",),
            ".pyrefly": ("FlextInfraUtilitiesPyrefly",),
            ".qualified_names": ("FlextInfraUtilitiesQualifiedNames",),
            ".refactor": ("FlextInfraUtilitiesRefactor",),
            ".refactor_discovery": ("FlextInfraUtilitiesRefactorDiscovery",),
            ".release": ("FlextInfraUtilitiesRelease",),
            ".repository": ("FlextInfraUtilitiesRepository",),
            ".resource_limits": ("FlextInfraUtilitiesResourceLimits",),
            ".rope_analysis": ("FlextInfraUtilitiesRopeAnalysis",),
            ".rope_analysis_introspection": (
                "FlextInfraUtilitiesRopeAnalysisIntrospection",
            ),
            ".rope_analysis_workspace": ("FlextInfraUtilitiesRopeAnalysisWorkspace",),
            ".rope_class_move": ("FlextInfraUtilitiesRopeClassMove",),
            ".rope_core": ("FlextInfraUtilitiesRopeCore",),
            ".rope_helpers": ("FlextInfraUtilitiesRopeHelpers",),
            ".rope_imports": ("FlextInfraUtilitiesRopeImports",),
            ".rope_inventory": ("FlextInfraUtilitiesRopeInventory",),
            ".rope_module_patch": ("FlextInfraUtilitiesRopeModulePatch",),
            ".rope_runtime": ("FlextInfraUtilitiesRopeRuntime",),
            ".rope_runtime_base": ("FlextInfraUtilitiesRopeRuntimeBase",),
            ".rope_runtime_modules": ("FlextInfraUtilitiesRopeRuntimeModules",),
            ".rope_runtime_refactors": ("FlextInfraUtilitiesRopeRuntimeRefactors",),
            ".rope_runtime_types": ("FlextInfraUtilitiesRopeRuntimeTypes",),
            ".rope_source": ("FlextInfraUtilitiesRopeSource",),
            ".rope_structure": ("FlextInfraUtilitiesRopeStructure",),
            ".safety": ("FlextInfraUtilitiesSafety",),
            ".semantic_cutover": ("FlextInfraUtilitiesSemanticCutover",),
            ".signature_rules": ("FlextInfraUtilitiesSignatureRules",),
            ".silent_failure_ast": ("FlextInfraUtilitiesSilentFailureAst",),
            ".silent_failure_ast_base": ("FlextInfraUtilitiesSilentFailureAstBase",),
            ".silent_failure_ast_rules": ("FlextInfraUtilitiesSilentFailureAstRules",),
            ".transformer_base": ("FlextInfraChangeTrackingTransformer",),
            ".transformer_header": ("FlextInfraUtilitiesTransformerHeader",),
            ".transformer_header_parser": (
                "FlextInfraUtilitiesTransformerHeaderParser",
            ),
            ".versioning": ("FlextInfraUtilitiesVersioning",),
            ".workspace_fingerprint": ("FlextInfraUtilitiesWorkspaceFingerprint",),
            ".workspace_manifest": ("FlextInfraUtilitiesWorkspaceManifest",),
            ".worktree_lifecycle": ("FlextInfraWorktreeLifecycle",),
            ".worktree_provisioning": ("FlextInfraWorktreeProvisioning",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
