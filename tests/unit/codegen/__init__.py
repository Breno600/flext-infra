# AUTO-GENERATED FILE — Regenerate with: make gen
"""Tests.unit.codegen package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from ._support import CodegenTestSupport
    from .autofix_workspace_tests import TestsFlextInfraCodegenAutofixWorkspace
    from .census_models_tests import TestsFlextInfraCodegenCensusModels
    from .census_tests import TestsFlextInfraCodegenCensus
    from .ci_custom_steps_tests import TestsFlextInfraCodegenCiCustomSteps
    from .codegen_file_plan_state_tests import TestsFlextInfraCodegenFilePlanState
    from .consolidator_tests import TestsFlextInfraCodegenConsolidator
    from .constants_quality_gate_tests import TestsFlextInfraCodegenConstantsQualityGate
    from .docs_workflow_profile_tests import TestsFlextInfraCodegenDocsWorkflowProfile
    from .init_tests import TestsFlextInfraCodegenInit
    from .layout_fixture import archive_root, build_loose_project, layout_engine
    from .layout_gitignore_tests import TestsFlextInfraCodegenLayoutGitignore
    from .layout_tests import TestsFlextInfraCodegenLayout
    from .lazy_init_alias_inheritance_tests import (
        TestsFlextInfraLazyInitAliasInheritance,
    )
    from .lazy_init_bootstrap_package_tests import (
        TestsFlextInfraLazyInitBootstrapPackage,
    )
    from .lazy_init_file_plan_tests import TestsFlextInfraCodegenLazyInitFilePlans
    from .lazy_init_generation_tests import TestsFlextInfraCodegenGeneration
    from .lazy_init_process_tests import TestsFlextInfraLazyInitProcessing
    from .lazy_init_registry_wrapper_tests import TestsFlextInfraLazyInitCleanup
    from .lazy_init_runtime_tests import TestsFlextInfraLazyInitRuntime
    from .lazy_init_service_tests import TestsFlextInfraCodegenLazyInitService
    from .lazy_init_tests import TestsFlextInfraCodegenLazyInit
    from .main_tests import TestsFlextInfraCodegenMain
    from .scaffolder_naming_tests import TestsFlextInfraCodegenScaffolderNaming
    from .scaffolder_tests import TestsFlextInfraCodegenScaffolder
    from .submodule_recipe_shell_tests import TestsFlextInfraSubmoduleRecipeShell
    from .test_ci_checkout_mode_normalization import (
        TestsFlextInfraCiCheckoutModeNormalization,
    )
    from .test_ci_declared_secrets_contract import (
        TestsFlextInfraCiDeclaredSecretsContract,
    )
    from .test_ci_integration_branch_triggers import (
        TestsFlextInfraCiIntegrationBranchTriggers,
    )
    from .test_ci_system_packages import TestsFlextInfraCiSystemPackages
    from .test_codegen_artifact_ssot import TestsFlextInfraCodegenArtifactSsot
    from .test_codegen_beads_projection import TestsFlextInfraCodegenBeadsProjection
    from .test_codegen_catalog_extensions import TestsFlextInfraCodegenCatalogExtensions
    from .test_codegen_ci_matrix import TestsFlextInfraCodegenCiMatrix
    from .test_codegen_conform_no_transaction_worktrees import (
        TestsFlextInfraCodegenConformNoTransactionWorktrees,
    )
    from .test_codegen_hook_conformance import TestsFlextInfraCodegenHookConformance
    from .test_codegen_linked_worktree_manifest import (
        TestsFlextInfraCodegenLinkedWorktreeManifest,
    )
    from .test_codegen_make_environment import TestsFlextInfraCodegenMakeEnvironment
    from .test_codegen_manifestless_existing import (
        TestsFlextInfraCodegenManifestlessExisting,
    )
    from .test_codegen_mise_artifacts import TestsFlextInfraCodegenMiseArtifacts
    from .test_codegen_packaged_data_wheel_collision import (
        TestsFlextInfraCodegenPackagedDataWheel,
    )
    from .test_codegen_pipeline_performance import (
        TestsFlextInfraCodegenPipelinePerformance,
    )
    from .test_codegen_pyproject_conform import TestsFlextInfraCodegenPyprojectConform
    from .test_codegen_render_purity_golden import (
        TestsFlextInfraCodegenRenderPurityGolden,
    )
    from .test_codegen_repository_root_fanout import (
        TestsFlextInfraCodegenRepositoryRootFanout,
    )
    from .test_codegen_runtime_profiles import TestsFlextInfraCodegenRuntimeProfiles
    from .test_codegen_setup_submodules import TestsFlextInfraCodegenSetupSubmodules
    from .test_codegen_version_file import TestsFlextInfraCodegenVersionFile
    from .test_codegen_workflow_retirement import (
        TestsFlextInfraCodegenWorkflowRetirement,
    )
    from .test_file_participant_recovery import TestsFlextInfraFileParticipantRecovery
    from .test_gen_respects_invocation_scope import (
        TestsFlextInfraGenRespectsInvocationScope,
    )
    from .test_managed_conflicts import TestsFlextInfraManagedConflictRecovery
    from .test_managed_maintenance_headers import (
        TestsFlextInfraManagedMaintenanceHeaders,
    )
    from .test_mise_runtime_storage import TestsFlextInfraMiseRuntimeStorage
    from .test_plan_collection import TestsFlextInfraPlanCollection
    from .test_release_checkout_credentials import (
        TestsFlextInfraReleaseCheckoutCredentials,
    )
    from .test_root_artifact_ownership import TestsFlextInfraRootArtifactOwnership
    from .test_setup_never_destroys import TestsFlextInfraSetupNeverDestroys
    from .test_template_formatter_fixed_point import (
        TestsFlextInfraTemplateFormatterFixedPoint,
    )
    from .test_utility_facade_projection import TestsFlextInfraUtilityFacadeProjection
    from .test_violation_key import TestsFlextInfraCodegenViolationKey
    from .test_vscode_owner_merge import TestsFlextInfraVscodeOwnerMerge
    from .test_workspace_root_setup_submodules import (
        TestsFlextInfraWorkspaceRootSetupSubmodules,
    )
    from .toolchain_beads_distribution_tests import (
        TestsFlextInfraToolchainBeadsDistribution,
    )
    from .toolchain_go_backend_tests import TestsFlextInfraToolchainGoBackend
    from .toolchain_make_tests import TestsFlextInfraToolchainMake
    from .toolchain_requirement_tests import TestsFlextInfraToolchainRequirement
    from .transaction_directory_journal_tests import (
        TestsFlextInfraTransactionDirectoryJournal,
    )
    from .transaction_lease_tests import TestsFlextInfraTransactionLease
    from .workflow_comment_spacing_tests import TestsFlextInfraWorkflowCommentSpacing
    from .workflow_orphan_guard_tests import TestsFlextInfraWorkflowOrphanGuard


__all__: tuple[str, ...] = (
    "CodegenTestSupport",
    "TestsFlextInfraCiCheckoutModeNormalization",
    "TestsFlextInfraCiDeclaredSecretsContract",
    "TestsFlextInfraCiIntegrationBranchTriggers",
    "TestsFlextInfraCiSystemPackages",
    "TestsFlextInfraCodegenArtifactSsot",
    "TestsFlextInfraCodegenAutofixWorkspace",
    "TestsFlextInfraCodegenBeadsProjection",
    "TestsFlextInfraCodegenCatalogExtensions",
    "TestsFlextInfraCodegenCensus",
    "TestsFlextInfraCodegenCensusModels",
    "TestsFlextInfraCodegenCiCustomSteps",
    "TestsFlextInfraCodegenCiMatrix",
    "TestsFlextInfraCodegenConformNoTransactionWorktrees",
    "TestsFlextInfraCodegenConsolidator",
    "TestsFlextInfraCodegenConstantsQualityGate",
    "TestsFlextInfraCodegenDocsWorkflowProfile",
    "TestsFlextInfraCodegenFilePlanState",
    "TestsFlextInfraCodegenGeneration",
    "TestsFlextInfraCodegenHookConformance",
    "TestsFlextInfraCodegenInit",
    "TestsFlextInfraCodegenLayout",
    "TestsFlextInfraCodegenLayoutGitignore",
    "TestsFlextInfraCodegenLazyInit",
    "TestsFlextInfraCodegenLazyInitFilePlans",
    "TestsFlextInfraCodegenLazyInitService",
    "TestsFlextInfraCodegenLinkedWorktreeManifest",
    "TestsFlextInfraCodegenMain",
    "TestsFlextInfraCodegenMakeEnvironment",
    "TestsFlextInfraCodegenManifestlessExisting",
    "TestsFlextInfraCodegenMiseArtifacts",
    "TestsFlextInfraCodegenPackagedDataWheel",
    "TestsFlextInfraCodegenPipelinePerformance",
    "TestsFlextInfraCodegenPyprojectConform",
    "TestsFlextInfraCodegenRenderPurityGolden",
    "TestsFlextInfraCodegenRepositoryRootFanout",
    "TestsFlextInfraCodegenRuntimeProfiles",
    "TestsFlextInfraCodegenScaffolder",
    "TestsFlextInfraCodegenScaffolderNaming",
    "TestsFlextInfraCodegenSetupSubmodules",
    "TestsFlextInfraCodegenVersionFile",
    "TestsFlextInfraCodegenViolationKey",
    "TestsFlextInfraCodegenWorkflowRetirement",
    "TestsFlextInfraFileParticipantRecovery",
    "TestsFlextInfraGenRespectsInvocationScope",
    "TestsFlextInfraLazyInitAliasInheritance",
    "TestsFlextInfraLazyInitBootstrapPackage",
    "TestsFlextInfraLazyInitCleanup",
    "TestsFlextInfraLazyInitProcessing",
    "TestsFlextInfraLazyInitRuntime",
    "TestsFlextInfraManagedConflictRecovery",
    "TestsFlextInfraManagedMaintenanceHeaders",
    "TestsFlextInfraMiseRuntimeStorage",
    "TestsFlextInfraPlanCollection",
    "TestsFlextInfraReleaseCheckoutCredentials",
    "TestsFlextInfraRootArtifactOwnership",
    "TestsFlextInfraSetupNeverDestroys",
    "TestsFlextInfraSubmoduleRecipeShell",
    "TestsFlextInfraTemplateFormatterFixedPoint",
    "TestsFlextInfraToolchainBeadsDistribution",
    "TestsFlextInfraToolchainGoBackend",
    "TestsFlextInfraToolchainMake",
    "TestsFlextInfraToolchainRequirement",
    "TestsFlextInfraTransactionDirectoryJournal",
    "TestsFlextInfraTransactionLease",
    "TestsFlextInfraUtilityFacadeProjection",
    "TestsFlextInfraVscodeOwnerMerge",
    "TestsFlextInfraWorkflowCommentSpacing",
    "TestsFlextInfraWorkflowOrphanGuard",
    "TestsFlextInfraWorkspaceRootSetupSubmodules",
    "archive_root",
    "build_loose_project",
    "layout_engine",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._support": ("CodegenTestSupport",),
            ".autofix_workspace_tests": ("TestsFlextInfraCodegenAutofixWorkspace",),
            ".census_models_tests": ("TestsFlextInfraCodegenCensusModels",),
            ".census_tests": ("TestsFlextInfraCodegenCensus",),
            ".ci_custom_steps_tests": ("TestsFlextInfraCodegenCiCustomSteps",),
            ".codegen_file_plan_state_tests": ("TestsFlextInfraCodegenFilePlanState",),
            ".consolidator_tests": ("TestsFlextInfraCodegenConsolidator",),
            ".constants_quality_gate_tests": (
                "TestsFlextInfraCodegenConstantsQualityGate",
            ),
            ".docs_workflow_profile_tests": (
                "TestsFlextInfraCodegenDocsWorkflowProfile",
            ),
            ".init_tests": ("TestsFlextInfraCodegenInit",),
            ".layout_fixture": ("archive_root", "build_loose_project", "layout_engine"),
            ".layout_gitignore_tests": ("TestsFlextInfraCodegenLayoutGitignore",),
            ".layout_tests": ("TestsFlextInfraCodegenLayout",),
            ".lazy_init_alias_inheritance_tests": (
                "TestsFlextInfraLazyInitAliasInheritance",
            ),
            ".lazy_init_bootstrap_package_tests": (
                "TestsFlextInfraLazyInitBootstrapPackage",
            ),
            ".lazy_init_file_plan_tests": ("TestsFlextInfraCodegenLazyInitFilePlans",),
            ".lazy_init_generation_tests": ("TestsFlextInfraCodegenGeneration",),
            ".lazy_init_process_tests": ("TestsFlextInfraLazyInitProcessing",),
            ".lazy_init_registry_wrapper_tests": ("TestsFlextInfraLazyInitCleanup",),
            ".lazy_init_runtime_tests": ("TestsFlextInfraLazyInitRuntime",),
            ".lazy_init_service_tests": ("TestsFlextInfraCodegenLazyInitService",),
            ".lazy_init_tests": ("TestsFlextInfraCodegenLazyInit",),
            ".main_tests": ("TestsFlextInfraCodegenMain",),
            ".scaffolder_naming_tests": ("TestsFlextInfraCodegenScaffolderNaming",),
            ".scaffolder_tests": ("TestsFlextInfraCodegenScaffolder",),
            ".submodule_recipe_shell_tests": ("TestsFlextInfraSubmoduleRecipeShell",),
            ".test_ci_checkout_mode_normalization": (
                "TestsFlextInfraCiCheckoutModeNormalization",
            ),
            ".test_ci_declared_secrets_contract": (
                "TestsFlextInfraCiDeclaredSecretsContract",
            ),
            ".test_ci_integration_branch_triggers": (
                "TestsFlextInfraCiIntegrationBranchTriggers",
            ),
            ".test_ci_system_packages": ("TestsFlextInfraCiSystemPackages",),
            ".test_codegen_artifact_ssot": ("TestsFlextInfraCodegenArtifactSsot",),
            ".test_codegen_beads_projection": (
                "TestsFlextInfraCodegenBeadsProjection",
            ),
            ".test_codegen_catalog_extensions": (
                "TestsFlextInfraCodegenCatalogExtensions",
            ),
            ".test_codegen_ci_matrix": ("TestsFlextInfraCodegenCiMatrix",),
            ".test_codegen_conform_no_transaction_worktrees": (
                "TestsFlextInfraCodegenConformNoTransactionWorktrees",
            ),
            ".test_codegen_hook_conformance": (
                "TestsFlextInfraCodegenHookConformance",
            ),
            ".test_codegen_linked_worktree_manifest": (
                "TestsFlextInfraCodegenLinkedWorktreeManifest",
            ),
            ".test_codegen_make_environment": (
                "TestsFlextInfraCodegenMakeEnvironment",
            ),
            ".test_codegen_manifestless_existing": (
                "TestsFlextInfraCodegenManifestlessExisting",
            ),
            ".test_codegen_mise_artifacts": ("TestsFlextInfraCodegenMiseArtifacts",),
            ".test_codegen_packaged_data_wheel_collision": (
                "TestsFlextInfraCodegenPackagedDataWheel",
            ),
            ".test_codegen_pipeline_performance": (
                "TestsFlextInfraCodegenPipelinePerformance",
            ),
            ".test_codegen_pyproject_conform": (
                "TestsFlextInfraCodegenPyprojectConform",
            ),
            ".test_codegen_render_purity_golden": (
                "TestsFlextInfraCodegenRenderPurityGolden",
            ),
            ".test_codegen_repository_root_fanout": (
                "TestsFlextInfraCodegenRepositoryRootFanout",
            ),
            ".test_codegen_runtime_profiles": (
                "TestsFlextInfraCodegenRuntimeProfiles",
            ),
            ".test_codegen_setup_submodules": (
                "TestsFlextInfraCodegenSetupSubmodules",
            ),
            ".test_codegen_version_file": ("TestsFlextInfraCodegenVersionFile",),
            ".test_codegen_workflow_retirement": (
                "TestsFlextInfraCodegenWorkflowRetirement",
            ),
            ".test_file_participant_recovery": (
                "TestsFlextInfraFileParticipantRecovery",
            ),
            ".test_gen_respects_invocation_scope": (
                "TestsFlextInfraGenRespectsInvocationScope",
            ),
            ".test_managed_conflicts": ("TestsFlextInfraManagedConflictRecovery",),
            ".test_managed_maintenance_headers": (
                "TestsFlextInfraManagedMaintenanceHeaders",
            ),
            ".test_mise_runtime_storage": ("TestsFlextInfraMiseRuntimeStorage",),
            ".test_plan_collection": ("TestsFlextInfraPlanCollection",),
            ".test_release_checkout_credentials": (
                "TestsFlextInfraReleaseCheckoutCredentials",
            ),
            ".test_root_artifact_ownership": ("TestsFlextInfraRootArtifactOwnership",),
            ".test_setup_never_destroys": ("TestsFlextInfraSetupNeverDestroys",),
            ".test_template_formatter_fixed_point": (
                "TestsFlextInfraTemplateFormatterFixedPoint",
            ),
            ".test_utility_facade_projection": (
                "TestsFlextInfraUtilityFacadeProjection",
            ),
            ".test_violation_key": ("TestsFlextInfraCodegenViolationKey",),
            ".test_vscode_owner_merge": ("TestsFlextInfraVscodeOwnerMerge",),
            ".test_workspace_root_setup_submodules": (
                "TestsFlextInfraWorkspaceRootSetupSubmodules",
            ),
            ".toolchain_beads_distribution_tests": (
                "TestsFlextInfraToolchainBeadsDistribution",
            ),
            ".toolchain_go_backend_tests": ("TestsFlextInfraToolchainGoBackend",),
            ".toolchain_make_tests": ("TestsFlextInfraToolchainMake",),
            ".toolchain_requirement_tests": ("TestsFlextInfraToolchainRequirement",),
            ".transaction_directory_journal_tests": (
                "TestsFlextInfraTransactionDirectoryJournal",
            ),
            ".transaction_lease_tests": ("TestsFlextInfraTransactionLease",),
            ".workflow_comment_spacing_tests": (
                "TestsFlextInfraWorkflowCommentSpacing",
            ),
            ".workflow_orphan_guard_tests": ("TestsFlextInfraWorkflowOrphanGuard",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
