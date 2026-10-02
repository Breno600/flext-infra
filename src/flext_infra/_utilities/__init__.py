# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._utilities import (
        _git,
        _promoted,
        _pyproject,
        _rope,
        _rope_analysis,
        _semantic_cutover,
    )
    from flext_infra._utilities._docs_audit_detectors import (
        FlextInfraUtilitiesDocsAuditDetectorsMixin,
    )
    from flext_infra._utilities._docs_command_contract import (
        FlextInfraUtilitiesDocsCommandContractMixin,
    )
    from flext_infra._utilities._docs_generate_plan import (
        FlextInfraUtilitiesDocsGeneratePlanMixin,
    )
    from flext_infra._utilities._docs_generate_project import (
        FlextInfraUtilitiesDocsGenerateProjectMixin,
    )
    from flext_infra._utilities._docs_generate_root import (
        FlextInfraUtilitiesDocsGenerateRootMixin,
    )
    from flext_infra._utilities._docs_generate_sources import (
        FlextInfraUtilitiesDocsGenerateSourcesMixin,
    )
    from flext_infra._utilities._docs_github_links import (
        FlextInfraUtilitiesDocsGithubLinks,
    )
    from flext_infra._utilities._docs_guides import FlextInfraUtilitiesDocsGuidesMixin
    from flext_infra._utilities._docs_scope_build import (
        FlextInfraUtilitiesDocsScopeBuildMixin,
    )
    from flext_infra._utilities._docs_scope_paths import (
        FlextInfraUtilitiesDocsScopePathsMixin,
    )
    from flext_infra._utilities._docs_scope_policy import (
        FlextInfraUtilitiesDocsScopePolicyMixin,
    )
    from flext_infra._utilities._docs_scope_projects import (
        FlextInfraUtilitiesDocsScopeProjectsMixin,
    )
    from flext_infra._utilities._docs_scope_selection import (
        FlextInfraUtilitiesDocsScopeSelectionMixin,
    )
    from flext_infra._utilities._docs_scope_state import (
        FlextInfraUtilitiesDocsScopeStateMixin,
    )
    from flext_infra._utilities._git.attestation import (
        FlextInfraUtilitiesGitAttestationMixin,
    )
    from flext_infra._utilities._git.mutation_scope import (
        FlextInfraUtilitiesGitMutationScopeMixin,
    )
    from flext_infra._utilities._git.remote import FlextInfraUtilitiesGitRemote
    from flext_infra._utilities._git.repo import FlextInfraUtilitiesGitRepo
    from flext_infra._utilities._git.scope import FlextInfraUtilitiesGitScopeMixin
    from flext_infra._utilities._git.semantic_identity import (
        FlextInfraUtilitiesGitSemanticIdentityMixin,
    )
    from flext_infra._utilities._git.semantic_index import (
        FlextInfraUtilitiesGitSemanticIndexMixin,
    )
    from flext_infra._utilities._git.semantic_lane import (
        FlextInfraUtilitiesGitSemanticLaneMixin,
    )
    from flext_infra._utilities._git.semantic_paths import (
        FlextInfraUtilitiesGitSemanticPathsMixin,
    )
    from flext_infra._utilities._git.semantic_publish import (
        FlextInfraUtilitiesGitSemanticPublishMixin,
    )
    from flext_infra._utilities._git.semantic_refs import (
        FlextInfraUtilitiesGitSemanticRefsMixin,
    )
    from flext_infra._utilities._git.semantic_submodule import (
        FlextInfraUtilitiesGitSemanticSubmoduleMixin,
    )
    from flext_infra._utilities._git.semantic_worktree import (
        FlextInfraUtilitiesGitSemanticWorktreeMixin,
    )
    from flext_infra._utilities._git.state_capture import (
        FlextInfraUtilitiesGitStateCaptureMixin,
    )
    from flext_infra._utilities._git.state_checkpoint import (
        FlextInfraUtilitiesGitStateCheckpointMixin,
    )
    from flext_infra._utilities._git.state_files import (
        FlextInfraUtilitiesGitStateFilesMixin,
    )
    from flext_infra._utilities._git.state_publication import (
        FlextInfraUtilitiesGitStatePublicationMixin,
    )
    from flext_infra._utilities._git.state_snapshot import (
        FlextInfraUtilitiesGitStateSnapshotMixin,
    )
    from flext_infra._utilities._git.state_transition import (
        FlextInfraUtilitiesGitStateTransitionMixin,
    )
    from flext_infra._utilities._git.state_trees import (
        FlextInfraUtilitiesGitStateTreesMixin,
    )
    from flext_infra._utilities._git.worktree import FlextInfraUtilitiesGitWorktreeMixin
    from flext_infra._utilities._git.worktree_checkpoint import (
        FlextInfraUtilitiesGitWorktreeCheckpointMixin,
    )
    from flext_infra._utilities._git.worktree_discovery import (
        FlextInfraUtilitiesGitWorktreeDiscoveryMixin,
    )
    from flext_infra._utilities._git.worktree_facts import (
        FlextInfraUtilitiesGitWorktreeFactsMixin,
    )
    from flext_infra._utilities._git.worktree_io import FlextInfraUtilitiesGitWorktreeIO
    from flext_infra._utilities._git.worktree_materialization import (
        FlextInfraUtilitiesGitWorktreeMaterializationMixin,
    )
    from flext_infra._utilities._git.worktree_measure import (
        FlextInfraUtilitiesGitWorktreeMeasureMixin,
    )
    from flext_infra._utilities._git.worktree_patch import (
        FlextInfraUtilitiesGitWorktreePatchMixin,
    )
    from flext_infra._utilities._git.worktree_removal import (
        FlextInfraUtilitiesGitWorktreeRemovalMixin,
    )
    from flext_infra._utilities._git.worktree_roots import (
        FlextInfraUtilitiesGitWorktreeRootsMixin,
    )
    from flext_infra._utilities._git.worktree_status import (
        FlextInfraUtilitiesGitWorktreeStatusMixin,
    )
    from flext_infra._utilities._mypy_profile import FlextInfraMypyProfiler
    from flext_infra._utilities._mypy_supervisor import FlextInfraMypyDarwinSupervisor
    from flext_infra._utilities._project_discovery_candidates import (
        FlextInfraUtilitiesProjectDiscoveryCandidatesMixin,
    )
    from flext_infra._utilities._project_discovery_shape import (
        FlextInfraUtilitiesProjectDiscoveryShapeMixin,
    )
    from flext_infra._utilities._promoted.commands import (
        FlextInfraUtilitiesPromotedCommands,
    )
    from flext_infra._utilities._promoted.execution import (
        FlextInfraUtilitiesPromotedExecution,
    )
    from flext_infra._utilities._promoted.invocation import (
        FlextInfraUtilitiesPromotedInvocation,
    )
    from flext_infra._utilities._promoted.rendering import (
        FlextInfraUtilitiesPromotedRendering,
    )
    from flext_infra._utilities._promoted.workspace import (
        FlextInfraUtilitiesPromotedWorkspace,
    )
    from flext_infra._utilities._pyproject.base import (
        FlextInfraUtilitiesPyprojectConformBase,
    )
    from flext_infra._utilities._pyproject.document import (
        FlextInfraUtilitiesPyprojectDocument,
    )
    from flext_infra._utilities._pyproject.overlay import (
        FlextInfraUtilitiesPyprojectOverlay,
    )
    from flext_infra._utilities._pyproject.requirements import (
        FlextInfraUtilitiesPyprojectRequirements,
    )
    from flext_infra._utilities._pyproject.session import (
        FlextInfraUtilitiesPyprojectSession,
    )
    from flext_infra._utilities._pyproject.toml_phases import (
        FlextInfraUtilitiesPyprojectTomlPhases,
    )
    from flext_infra._utilities._pyproject.uv_sources import (
        FlextInfraUtilitiesPyprojectUvSources,
    )
    from flext_infra._utilities._rope.project import FlextInfraRopeProject
    from flext_infra._utilities._rope_analysis.asthelpers import (
        FlextInfraUtilitiesRopeAnalysisAstHelpers,
    )
    from flext_infra._utilities._rope_analysis.base import (
        FlextInfraUtilitiesRopeAnalysisBase,
    )
    from flext_infra._utilities._rope_analysis.exports import (
        FlextInfraUtilitiesRopeAnalysisExports,
    )
    from flext_infra._utilities._rope_analysis.importstate import (
        FlextInfraUtilitiesRopeAnalysisImportState,
    )
    from flext_infra._utilities._rope_analysis.sourcescan import (
        FlextInfraUtilitiesRopeAnalysisSourceScan,
    )
    from flext_infra._utilities._rope_core_pymodule import (
        FlextInfraUtilitiesRopeCorePyModuleMixin,
    )
    from flext_infra._utilities._rope_core_resources import (
        FlextInfraUtilitiesRopeCoreResourcesMixin,
    )
    from flext_infra._utilities._rope_method_order import (
        FlextInfraUtilitiesRopeMethodOrderMixin,
    )
    from flext_infra._utilities._semantic_cutover.alias_cst import (
        FlextInfraUtilitiesSemanticCutoverAliasCst,
    )
    from flext_infra._utilities._semantic_cutover.aliases import (
        FlextInfraUtilitiesSemanticCutoverAliases,
    )
    from flext_infra._utilities._semantic_cutover.base import (
        FlextInfraUtilitiesSemanticCutoverBase,
    )
    from flext_infra._utilities._semantic_cutover.bindings import (
        FlextInfraUtilitiesSemanticCutoverBindings,
    )
    from flext_infra._utilities._semantic_cutover.dynamic_environment import (
        FlextInfraUtilitiesSemanticCutoverDynamicEnvironment,
    )
    from flext_infra._utilities._semantic_cutover.edits import (
        FlextInfraUtilitiesSemanticCutoverEdits,
    )
    from flext_infra._utilities._semantic_cutover.facade_base_cst import (
        FlextInfraUtilitiesSemanticCutoverFacadeBaseCst,
    )
    from flext_infra._utilities._semantic_cutover.facade_bases import (
        FlextInfraUtilitiesSemanticCutoverFacadeBases,
    )
    from flext_infra._utilities._semantic_cutover.facade_owners import (
        FlextInfraUtilitiesSemanticCutoverFacadeOwners,
    )
    from flext_infra._utilities._semantic_cutover.family_flatten import (
        FlextInfraUtilitiesSemanticFamilyFlatten,
    )
    from flext_infra._utilities._semantic_cutover.family_references import (
        FlextInfraUtilitiesSemanticFamilyReferences,
    )
    from flext_infra._utilities._semantic_cutover.family_type_references import (
        FlextInfraUtilitiesSemanticFamilyTypeReferences,
    )
    from flext_infra._utilities._semantic_cutover.helper_references import (
        FlextInfraUtilitiesSemanticHelperReferences,
    )
    from flext_infra._utilities._semantic_cutover.model_fields import (
        FlextInfraUtilitiesSemanticCutoverModelFields,
    )
    from flext_infra._utilities._semantic_cutover.model_fields_bindings import (
        FlextInfraUtilitiesSemanticCutoverModelFieldsBindings,
    )
    from flext_infra._utilities._semantic_cutover.module_layout import (
        FlextInfraUtilitiesSemanticCutoverModuleLayout,
    )
    from flext_infra._utilities._semantic_cutover.nesting import (
        FlextInfraUtilitiesSemanticCutoverNesting,
    )
    from flext_infra._utilities._semantic_cutover.nesting_cst import (
        FlextInfraUtilitiesSemanticCutoverNestingCst,
    )
    from flext_infra._utilities._semantic_cutover.nesting_references import (
        FlextInfraUtilitiesSemanticCutoverNestingReferences,
    )
    from flext_infra._utilities._semantic_cutover.nesting_types import (
        FlextInfraUtilitiesSemanticNestingTypes,
    )
    from flext_infra._utilities._semantic_cutover.private_import_cst import (
        FlextInfraUtilitiesSemanticCutoverPrivateImportCst,
    )
    from flext_infra._utilities._semantic_cutover.private_imports import (
        FlextInfraUtilitiesSemanticCutoverPrivateImports,
    )
    from flext_infra._utilities._semantic_cutover.self_facade import (
        FlextInfraUtilitiesSemanticCutoverSelfFacade,
    )
    from flext_infra._utilities.base import FlextInfraUtilitiesBase
    from flext_infra._utilities.census import FlextInfraUtilitiesRefactorCensus
    from flext_infra._utilities.codegen import FlextInfraUtilitiesCodegen
    from flext_infra._utilities.codegen_facades import FlextInfraUtilitiesCodegenFacades
    from flext_infra._utilities.codegen_file_plan import (
        FlextInfraUtilitiesCodegenFilePlan,
    )
    from flext_infra._utilities.codegen_path_cutover import (
        FlextInfraUtilitiesCodegenPathCutover,
    )
    from flext_infra._utilities.codemod_project import FlextInfraUtilitiesCodemodProject
    from flext_infra._utilities.codemod_rules import FlextInfraUtilitiesCodemodRules
    from flext_infra._utilities.compatibility_alias_validation import (
        FlextInfraUtilitiesCompatibilityAliasValidation,
    )
    from flext_infra._utilities.deferred_self_reference_rewrite import (
        FlextInfraUtilitiesDeferredSelfReferenceRewrite,
    )
    from flext_infra._utilities.dependencies import FlextInfraUtilitiesDependencies
    from flext_infra._utilities.discovery import FlextInfraUtilitiesDiscovery
    from flext_infra._utilities.docs import FlextInfraUtilitiesDocs
    from flext_infra._utilities.docs_api import FlextInfraUtilitiesDocsApi
    from flext_infra._utilities.docs_audit import FlextInfraUtilitiesDocsAudit
    from flext_infra._utilities.docs_build import FlextInfraUtilitiesDocsBuild
    from flext_infra._utilities.docs_collection import FlextInfraUtilitiesDocsCollection
    from flext_infra._utilities.docs_collection_sources import (
        FlextInfraUtilitiesDocsCollectionSources,
    )
    from flext_infra._utilities.docs_collection_verify import (
        FlextInfraUtilitiesDocsCollectionVerify,
    )
    from flext_infra._utilities.docs_contract import FlextInfraUtilitiesDocsContract
    from flext_infra._utilities.docs_fix import FlextInfraUtilitiesDocsFix
    from flext_infra._utilities.docs_generate import FlextInfraUtilitiesDocsGenerate
    from flext_infra._utilities.docs_render import FlextInfraUtilitiesDocsRender
    from flext_infra._utilities.docs_scope import FlextInfraUtilitiesDocsScope
    from flext_infra._utilities.docs_validate import FlextInfraUtilitiesDocsValidate
    from flext_infra._utilities.git import FlextInfraUtilitiesGit
    from flext_infra._utilities.gitignore import FlextInfraUtilitiesGitignore
    from flext_infra._utilities.iteration import FlextInfraUtilitiesIteration
    from flext_infra._utilities.iteration_directory import (
        FlextInfraUtilitiesIterationDirectory,
    )
    from flext_infra._utilities.iteration_matching import (
        FlextInfraUtilitiesIterationMatching,
    )
    from flext_infra._utilities.iteration_workspace import (
        FlextInfraUtilitiesIterationWorkspace,
    )
    from flext_infra._utilities.lint_recipes import FlextInfraUtilitiesLintRecipes
    from flext_infra._utilities.log_parser import FlextInfraUtilitiesLogParser
    from flext_infra._utilities.managed_conflicts import (
        FlextInfraUtilitiesManagedConflicts,
    )
    from flext_infra._utilities.namespace import FlextInfraUtilitiesCodegenNamespace
    from flext_infra._utilities.namespace_analysis import (
        FlextInfraUtilitiesRefactorNamespaceFlext,
    )
    from flext_infra._utilities.namespace_common import (
        FlextInfraUtilitiesRefactorNamespaceCommon,
    )
    from flext_infra._utilities.namespace_config import (
        FlextInfraUtilitiesNamespaceConfig,
    )
    from flext_infra._utilities.namespace_moves import (
        FlextInfraUtilitiesRefactorNamespaceMoves,
    )
    from flext_infra._utilities.network import FlextInfraUtilitiesNetwork
    from flext_infra._utilities.private_import_ancestry import (
        FlextInfraUtilitiesPrivateImportAncestry,
    )
    from flext_infra._utilities.private_import_facades import (
        FlextInfraUtilitiesPrivateImportFacades,
    )
    from flext_infra._utilities.private_import_validation import (
        FlextInfraUtilitiesPrivateImportValidation,
    )
    from flext_infra._utilities.process import FlextInfraUtilitiesProcess
    from flext_infra._utilities.project_discovery import (
        FlextInfraUtilitiesProjectDiscovery,
    )
    from flext_infra._utilities.project_managed_artifacts import (
        FlextInfraUtilitiesProjectManagedArtifacts,
    )
    from flext_infra._utilities.promoted import FlextInfraUtilitiesPromoted
    from flext_infra._utilities.protected_edit import FlextInfraUtilitiesProtectedEdit
    from flext_infra._utilities.protected_edit_apply import (
        FlextInfraUtilitiesProtectedEditApply,
    )
    from flext_infra._utilities.protected_edit_linting import (
        FlextInfraUtilitiesProtectedEditLinting,
    )
    from flext_infra._utilities.protected_edit_preview import (
        FlextInfraUtilitiesProtectedEditPreview,
    )
    from flext_infra._utilities.protected_edit_writes import (
        FlextInfraUtilitiesProtectedEditWrites,
    )
    from flext_infra._utilities.pyproject import FlextInfraUtilitiesPyproject
    from flext_infra._utilities.pyproject_conform import (
        FlextInfraUtilitiesPyprojectConform,
    )
    from flext_infra._utilities.pyrefly import FlextInfraUtilitiesPyrefly
    from flext_infra._utilities.qualified_names import FlextInfraUtilitiesQualifiedNames
    from flext_infra._utilities.refactor import FlextInfraUtilitiesRefactor
    from flext_infra._utilities.release import FlextInfraUtilitiesRelease
    from flext_infra._utilities.repository import FlextInfraUtilitiesRepository
    from flext_infra._utilities.resource_limits import FlextInfraUtilitiesResourceLimits
    from flext_infra._utilities.rope_analysis import FlextInfraUtilitiesRopeAnalysis
    from flext_infra._utilities.rope_analysis_introspection import (
        FlextInfraUtilitiesRopeAnalysisIntrospection,
    )
    from flext_infra._utilities.rope_analysis_workspace import (
        FlextInfraUtilitiesRopeAnalysisWorkspace,
    )
    from flext_infra._utilities.rope_class_move import FlextInfraUtilitiesRopeClassMove
    from flext_infra._utilities.rope_core import FlextInfraUtilitiesRopeCore
    from flext_infra._utilities.rope_helpers import FlextInfraUtilitiesRopeHelpers
    from flext_infra._utilities.rope_imports import FlextInfraUtilitiesRopeImports
    from flext_infra._utilities.rope_inventory import FlextInfraUtilitiesRopeInventory
    from flext_infra._utilities.rope_module_patch import (
        FlextInfraUtilitiesRopeModulePatch,
    )
    from flext_infra._utilities.rope_runtime import FlextInfraUtilitiesRopeRuntime
    from flext_infra._utilities.rope_runtime_base import (
        FlextInfraUtilitiesRopeRuntimeBase,
    )
    from flext_infra._utilities.rope_runtime_modules import (
        FlextInfraUtilitiesRopeRuntimeModules,
    )
    from flext_infra._utilities.rope_runtime_refactors import (
        FlextInfraUtilitiesRopeRuntimeRefactors,
    )
    from flext_infra._utilities.rope_runtime_types import (
        FlextInfraUtilitiesRopeRuntimeTypes,
    )
    from flext_infra._utilities.rope_source import FlextInfraUtilitiesRopeSource
    from flext_infra._utilities.rope_structure import FlextInfraUtilitiesRopeStructure
    from flext_infra._utilities.semantic_cutover import (
        FlextInfraUtilitiesSemanticCutover,
    )
    from flext_infra._utilities.transformer_header import (
        FlextInfraUtilitiesTransformerHeader,
    )
    from flext_infra._utilities.transformer_header_parser import (
        FlextInfraUtilitiesTransformerHeaderParser,
    )
    from flext_infra._utilities.versioning import FlextInfraUtilitiesVersioning
    from flext_infra._utilities.workspace_fingerprint import (
        FlextInfraUtilitiesWorkspaceFingerprint,
    )
    from flext_infra._utilities.workspace_manifest import (
        FlextInfraUtilitiesWorkspaceManifest,
    )
    from flext_infra._utilities.worktree_lifecycle import FlextInfraWorktreeLifecycle
    from flext_infra._utilities.worktree_provisioning import (
        FlextInfraWorktreeProvisioning,
    )

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
    "FlextInfraUtilitiesRopeStructure",
    "FlextInfraUtilitiesSemanticCutover",
    "FlextInfraUtilitiesSemanticCutoverAliasCst",
    "FlextInfraUtilitiesSemanticCutoverAliases",
    "FlextInfraUtilitiesSemanticCutoverBase",
    "FlextInfraUtilitiesSemanticCutoverBindings",
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
            "._git.mutation_scope": ("FlextInfraUtilitiesGitMutationScopeMixin",),
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
            "._git.state_capture": ("FlextInfraUtilitiesGitStateCaptureMixin",),
            "._git.state_checkpoint": ("FlextInfraUtilitiesGitStateCheckpointMixin",),
            "._git.state_files": ("FlextInfraUtilitiesGitStateFilesMixin",),
            "._git.state_publication": ("FlextInfraUtilitiesGitStatePublicationMixin",),
            "._git.state_snapshot": ("FlextInfraUtilitiesGitStateSnapshotMixin",),
            "._git.state_transition": ("FlextInfraUtilitiesGitStateTransitionMixin",),
            "._git.state_trees": ("FlextInfraUtilitiesGitStateTreesMixin",),
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
            "._mypy_profile": ("FlextInfraMypyProfiler",),
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
            "._pyproject.session": ("FlextInfraUtilitiesPyprojectSession",),
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
            "._semantic_cutover.bindings": (
                "FlextInfraUtilitiesSemanticCutoverBindings",
            ),
            "._semantic_cutover.dynamic_environment": (
                "FlextInfraUtilitiesSemanticCutoverDynamicEnvironment",
            ),
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
            "._semantic_cutover.model_fields": (
                "FlextInfraUtilitiesSemanticCutoverModelFields",
            ),
            "._semantic_cutover.model_fields_bindings": (
                "FlextInfraUtilitiesSemanticCutoverModelFieldsBindings",
            ),
            "._semantic_cutover.module_layout": (
                "FlextInfraUtilitiesSemanticCutoverModuleLayout",
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
            "._semantic_cutover.self_facade": (
                "FlextInfraUtilitiesSemanticCutoverSelfFacade",
            ),
            ".base": ("FlextInfraUtilitiesBase",),
            ".census": ("FlextInfraUtilitiesRefactorCensus",),
            ".codegen": ("FlextInfraUtilitiesCodegen",),
            ".codegen_facades": ("FlextInfraUtilitiesCodegenFacades",),
            ".codegen_file_plan": ("FlextInfraUtilitiesCodegenFilePlan",),
            ".codegen_path_cutover": ("FlextInfraUtilitiesCodegenPathCutover",),
            ".codemod_project": ("FlextInfraUtilitiesCodemodProject",),
            ".codemod_rules": ("FlextInfraUtilitiesCodemodRules",),
            ".compatibility_alias_validation": (
                "FlextInfraUtilitiesCompatibilityAliasValidation",
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
            ".iteration_workspace": ("FlextInfraUtilitiesIterationWorkspace",),
            ".lint_recipes": ("FlextInfraUtilitiesLintRecipes",),
            ".log_parser": ("FlextInfraUtilitiesLogParser",),
            ".managed_conflicts": ("FlextInfraUtilitiesManagedConflicts",),
            ".namespace": ("FlextInfraUtilitiesCodegenNamespace",),
            ".namespace_analysis": ("FlextInfraUtilitiesRefactorNamespaceFlext",),
            ".namespace_common": ("FlextInfraUtilitiesRefactorNamespaceCommon",),
            ".namespace_config": ("FlextInfraUtilitiesNamespaceConfig",),
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
            ".semantic_cutover": ("FlextInfraUtilitiesSemanticCutover",),
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
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
