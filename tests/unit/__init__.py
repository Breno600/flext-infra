# AUTO-GENERATED FILE — Regenerate with: make gen
"""Tests.unit package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from types import MappingProxyType

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from . import _utilities as _utilities
    from . import basemk as basemk
    from . import check as check
    from . import codegen as codegen
    from . import codemod as codemod
    from . import conftest as conftest
    from . import container as container
    from . import deps as deps
    from . import detectors as detectors
    from . import discovery as discovery
    from . import docs as docs
    from . import github as github
    from . import io as io
    from . import refactor as refactor
    from . import release as release
    from . import test_cprofile_entry as test_cprofile_entry
    from . import test_git_fixture_isolation as test_git_fixture_isolation
    from . import test_mro_service_base_alias as test_mro_service_base_alias
    from . import test_repository_baseline_branch as test_repository_baseline_branch
    from . import test_root_makefile_single_owner as test_root_makefile_single_owner
    from . import test_version_diag as test_version_diag
    from . import test_version_diag2 as test_version_diag2
    from . import transformers as transformers
    from . import validate as validate
    from . import workspace as workspace
    from flext_tests import c, d, e, h, m, p, r, s, t, td, tf, tk, tm, tv, u, x

    from ._utilities.test_discovery_consolidated import (
        TestsFlextInfraUtilitiesdiscoveryconsolidated,
    )
    from ._utilities.test_formatting import TestsFlextInfraUtilitiesformatting
    from ._utilities.test_git_facet_gitpython import TestsFlextInfraGitFacet
    from ._utilities.test_protected_edit import TestsFlextInfraUtilitiesProtectedEdit
    from ._utilities.test_resource_limits import TestsFlextInfraUtilitiesResourceLimits
    from ._utilities.test_rope_analysis import TestsFlextInfraRopeAnalysis
    from ._utilities.test_rope_hooks import TestsFlextInfraUtilitiesRopeHooks
    from ._utilities.test_rope_structure import TestsFlextInfraRopeStructure
    from ._utilities.test_safety import TestsFlextInfraUtilitiessafety
    from ._utilities.test_scanning import TestsFlextInfraUtilitiesscanning
    from .basemk.test_bootstrap_refname_safety import TestsBootstrapRefnameSafety
    from .basemk.test_custom_mk_policy import TestsFlextInfraCustomMkPolicy
    from .basemk.test_generator import TestsFlextInfraBasemkGenerator
    from .basemk.test_generator_edge_cases import (
        TestsFlextInfraBasemkGeneratorEdgeCases,
    )
    from .basemk.test_init import TestsFlextInfraBasemkInit
    from .basemk.test_main import TestsFlextInfraBasemkMain
    from .basemk.test_make_contract import TestsFlextInfraBasemkMakeContract
    from .basemk.test_renderer import TestsFlextInfraBasemkRenderer
    from .check.enforcement_fixer_orchestrator_tests import (
        TestsEnforcementFixerOrchestrator,
    )
    from .check.extended_cli_entry_tests import TestWorkspaceCheckCLI
    from .check.extended_config_fixer_errors_tests import TestConfigFixerPublicBehavior
    from .check.extended_config_fixer_tests import (
        TestConfigFixerExecute,
        TestConfigFixerProcessFile,
        TestConfigFixerRun,
        TestConfigFixerToArray,
    )
    from .check.extended_error_reporting_tests import (
        TestGateErrorReportingPublicBehavior,
    )
    from .check.extended_models_tests import (
        TestCheckIssueFormatted,
        TestProjectResultProperties,
        TestRunCommandGateParsing,
        TestWorkspaceCheckerErrorSummary,
    )
    from .check.extended_project_runners_tests import TestsExtendedProjectRunners
    from .check.extended_resolve_gates_tests import (
        TestWorkspaceCheckerCiGateRules,
        TestWorkspaceCheckerResolveGates,
    )
    from .check.extended_run_projects_tests import TestRunProjectsPublicBehavior
    from .check.extended_runners_extra_tests import TestExtendedRunnerExtras
    from .check.extended_runners_tests import TestRunnerPublicBehavior
    from .check.init_tests import TestFlextInfraCheck
    from .check.pyrefly_tests import TestFlextInfraConfigFixer
    from .check.test_cli import TestWorkspaceCheckCli
    from .check.workspace_tests import TestFlextInfraWorkspaceChecker
    from .cli_what_selector_tests import TestsFlextInfraCliWhatSelector
    from .codegen.lazy_init_fixture_settings_tests import (
        TestsFlextInfraLazyInitFixtureSettingsCollision,
    )
    from .codegen.lazy_init_generation_tests import TestsFlextInfraCodegenGeneration
    from .codegen.lazy_init_helpers_tests import TestsFlextInfraLazyInitHelpers
    from .codegen.lazy_init_process_tests import TestsFlextInfraLazyInitProcessing
    from .codegen.lazy_init_registry_wrapper_tests import TestsFlextInfraLazyInitCleanup
    from .codegen.lazy_init_runtime_tests import TestsFlextInfraLazyInitRuntime
    from .codegen.lazy_init_service_tests import TestsFlextInfraCodegenLazyInitService
    from .codegen.lazy_init_tests import (
        TestAllDirectoriesScanned,
        TestCheckOnlyMode,
        TestEdgeCases,
        TestExcludedDirectories,
    )
    from .codegen.lazy_init_transforms_tests import TestsFlextInfraLazyInitTransforms
    from .codegen.make_test_selector_tests import TestsMakeTestSelector
    from .codegen.scaffolder_naming_tests import (
        TestGeneratedClassNamingConvention,
        TestGeneratedFilesAreValidPython,
    )
    from .codegen.test_codegen_artifact_ssot import TestsCodegenArtifactSsot
    from .codegen.test_codegen_beads_ledger import TestCodegenBeadsLedger
    from .codegen.test_codegen_conform_progress import (
        TestsFlextInfraCodegenConformProgress,
    )
    from .codegen.test_codegen_hook_conformance import TestGitHookConformance
    from .codegen.test_codegen_linked_worktree_manifest import (
        TestCodegenLinkedWorktreeManifest,
    )
    from .codegen.test_codegen_make_environment import TestsCodegenMakeEnvironment
    from .codegen.test_codegen_pyproject_conform import (
        TestsFlextInfraCodegenPyprojectConform,
    )
    from .codegen.test_codegen_uv_exclude_newer_overlay import (
        TestCodegenUvExcludeNewerOverlay,
    )
    from .codegen.test_managed_conflicts import TestsFlextInfraCodegenManagedConflicts
    from .codegen.test_managed_maintenance_headers import (
        TestsFlextInfraManagedMaintenanceHeaders,
    )
    from .codegen.test_review_mro_vw2w_template_contracts import (
        TestsReviewTemplateContracts,
    )
    from .codegen.test_vscode_owner_merge import TestsVscodeOwnerMerge
    from .codegen.test_workspace_root_setup_submodules import (
        TestsWorkspaceRootSetupSubmodules,
    )
    from .codegen.worktree_verb_tests import TestsCodegenWorkVerb
    from .codemod.test_mod_circuit import (
        TestsFlextInfraModCircuitApply,
        TestsFlextInfraModCircuitDecision,
        TestsFlextInfraModCliRoute,
    )
    from .container.test_infra_container import TestsFlextInfraContainerInfraContainer
    from .deps.test_detection_classify import TestsFlextInfraDepsDetectionClassify
    from .deps.test_detection_deptry import TestsFlextInfraDepsDetectionDeptry
    from .deps.test_detection_discover import TestsFlextInfraDepsDetectionDiscover
    from .deps.test_detection_models import TestsFlextInfraDepsDetectionModels
    from .deps.test_detection_typings import TestsFlextInfraDepsDetectionTypings
    from .deps.test_detection_typings_flow import (
        TestsFlextInfraDepsDetectionTypingsFlow,
    )
    from .deps.test_detection_uncovered import TestsFlextInfraDepsDetectionUncovered
    from .deps.test_detector_detect import TestsFlextInfraDepsDetectorDetect
    from .deps.test_detector_detect_failures import (
        TestsFlextInfraDepsDetectorDetectFailures,
    )
    from .deps.test_detector_init import TestsFlextInfraDepsDetectorInit
    from .deps.test_detector_main import TestsFlextInfraDepsDetectorMain
    from .deps.test_detector_models import TestsFlextInfraDepsDetectorModels
    from .deps.test_detector_report import TestsFlextInfraDepsDetectorReport
    from .deps.test_detector_report_flags import TestsFlextInfraDepsDetectorReportFlags
    from .deps.test_extra_paths_manager import TestsFlextInfraExtraPathsManager
    from .deps.test_extra_paths_search_paths import TestsFlextInfraExtraPathsSearchPaths
    from .deps.test_extra_paths_sync import TestsFlextInfraDepsExtraPathsSync
    from .deps.test_init import TestsFlextInfraDepsInit
    from .deps.test_main_dispatch import TestsFlextInfraDepsMainDispatch
    from .deps.test_modernizer_comments import TestsFlextInfraDepsModernizerComments
    from .deps.test_modernizer_consolidate import (
        TestsFlextInfraDepsModernizerConsolidate,
    )
    from .deps.test_modernizer_coverage import TestsFlextInfraDepsModernizerCoverage
    from .deps.test_modernizer_helpers import TestsFlextInfraDepsModernizerHelpers
    from .deps.test_modernizer_main import TestsFlextInfraDepsModernizerMain
    from .deps.test_modernizer_main_extra import TestsFlextInfraDepsModernizerMainExtra
    from .deps.test_modernizer_mypy import TestsFlextInfraDepsModernizerMypy
    from .deps.test_modernizer_pyrefly import TestsFlextInfraModernizerPyrefly
    from .deps.test_modernizer_pyright import TestsFlextInfraDepsModernizerPyright
    from .deps.test_modernizer_pytest import TestsFlextInfraDepsModernizerPytest
    from .deps.test_modernizer_tooling import TestsFlextInfraDepsModernizerTooling
    from .deps.test_modernizer_workspace import TestsFlextInfraDepsModernizerWorkspace
    from .deps.test_pytest_fail_closed_config import (
        TestsFlextInfraPytestFailClosedConfig,
    )
    from .deps.test_pytest_timeout_config import TestsFlextInfraPytestTimeoutConfig
    from .detectors.test_deferred_self_reference_ast import (
        TestsFlextInfraDeferredSelfReferenceDetector,
    )
    from .detectors.test_internal_import_detector import (
        TestsFlextInfraInternalImportDetector,
    )
    from .detectors.test_loose_object_detector import TestsFlextInfraLooseObjectDetector
    from .detectors.test_loose_object_detector_characterization import (
        TestsFlextInfraLooseObjectCharacterization,
    )
    from .detectors.test_loose_test_function_detector import (
        TestsFlextInfraLooseTestFunctionDetector,
    )
    from .detectors.test_pattern_smell_detector import (
        TestsFlextInfraPatternSmellDetector,
    )
    from .discovery.test_infra_discovery_edge_cases import (
        TestsFlextInfraDiscoveryInfraDiscoveryEdgeCases,
    )
    from .docs.auditor_budgets_tests import TestLoadAuditBudgets
    from .docs.auditor_docstring_tests import TestsDocstringCoverage
    from .docs.auditor_links_tests import (
        TestAuditorBrokenLinks,
        TestAuditorGithubLinks,
        TestAuditorToMarkdown,
    )
    from .docs.auditor_scope_tests import TestAuditorForbiddenTerms, TestAuditorScope
    from .docs.auditor_tests import TestAuditorCore, TestAuditorNormalize
    from .docs.builder_tests import TestBuilderCore
    from .docs.main_entry_tests import TestsDocsCli
    from .docs.render_tests import TestsDocsRenderExcludeDocs
    from .docs.server_tests import TestsFlextInfraDocServer
    from .docs.shared_iter_tests import TestIterMarkdownFiles
    from .fixtures import (
        deptry_report_payload,
        models_resource,
        modernizer_workspace,
        modernizer_workspace_with_projects,
        real_docs_project,
        real_makefile_project,
        real_python_package,
        real_toml_project,
        real_workspace,
        rope_workspace,
        services_resource,
        tool_config_document,
    )
    from .fixtures_git import real_git_repo
    from .github.main_tests import TestsInfraGithub
    from .io.test_infra_terminal_detection import (
        TestsFlextInfraIoInfraTerminalDetection,
    )
    from .refactor.test_apply_renames_cli import TestsFlextInfraApplyRenamesCli
    from .refactor.test_declarative_enforcement import (
        TestsFlextInfraRefactorDeclarativeEnforcement,
        TestsFlextInfraRefactorDeclarativeEnforcementInCensus,
    )
    from .refactor.test_infra_refactor_class_and_propagation import (
        TestsFlextInfraRefactorInfraRefactorClassAndPropagation,
    )
    from .refactor.test_infra_refactor_class_placement import (
        TestsFlextInfraRefactorInfraRefactorClassPlacement,
    )
    from .refactor.test_infra_refactor_cli_models_workflow import (
        TestsFlextInfraRefactorInfraRefactorCliModelsWorkflow,
    )
    from .refactor.test_infra_refactor_import_modernizer import (
        TestsFlextInfraRefactorInfraRefactorImportModernizer,
    )
    from .refactor.test_infra_refactor_legacy_and_annotations import (
        TestsFlextInfraRefactorInfraRefactorLegacyAndAnnotations,
    )
    from .refactor.test_infra_refactor_migrate_to_class_mro import (
        TestsFlextInfraRefactorInfraRefactorMigrateToClassMro,
    )
    from .refactor.test_infra_refactor_mro_completeness import (
        TestsFlextInfraRefactorInfraRefactorMroCompleteness,
    )
    from .refactor.test_infra_refactor_mro_shape import (
        TestsFlextInfraRefactorInfraRefactorMroShape,
    )
    from .refactor.test_infra_refactor_namespace_aliases import (
        TestsFlextInfraRefactorInfraRefactorNamespaceAliases,
    )
    from .refactor.test_infra_refactor_namespace_enforcer import (
        TestsFlextInfraRefactorInfraRefactorNamespaceEnforcer,
    )
    from .refactor.test_infra_refactor_namespace_moves import (
        TestsFlextInfraRefactorInfraRefactorNamespaceMoves,
    )
    from .refactor.test_infra_refactor_pattern_corrections import (
        TestsFlextInfraRefactorInfraRefactorPatternCorrections,
    )
    from .refactor.test_infra_refactor_policy_family_rules import (
        TestsFlextInfraRefactorInfraRefactorPolicyFamilyRules,
    )
    from .refactor.test_infra_refactor_project_classifier import (
        TestsFlextInfraRefactorInfraRefactorProjectClassifier,
    )
    from .refactor.test_infra_refactor_safety import (
        RefactorSafetyStub,
        TestsFlextInfraRefactorInfraRefactorSafety,
    )
    from .refactor.test_infra_refactor_service import (
        TestsFlextInfraRefactorInfraRefactorService,
    )
    from .refactor.test_infra_refactor_typing_unifier import (
        FlextInfraRefactorTypingUnificationRule,
        TestsFlextInfraRefactorInfraRefactorTypingUnifier,
    )
    from .refactor.test_main_cli import TestsFlextInfraRefactorMainCli
    from .release.flow_tests import TestsFlextInfraReleaseFlow
    from .release.main_tests import TestsFlextInfraReleaseCli
    from .release.orchestrator_git_tests import TestsFlextInfraReleaseGit
    from .release.orchestrator_helpers_tests import TestsFlextInfraReleaseHelpers
    from .release.orchestrator_publish_tests import TestsFlextInfraReleasePublish
    from .release.orchestrator_tests import TestsFlextInfraReleaseOrchestration
    from .release.policy_fixture_root_tests import TestsReleasePolicyFixtureRoot
    from .release.test_release_dag import TestsFlextInfraReleaseDag
    from .release.version_resolution_tests import (
        TestsFlextInfraReleaseVersionResolution,
    )
    from .runner_service import RealSubprocessRunner
    from .test_custom_handler_policy_is_profile_aware import (
        TestsFlextInfraCustomHandlerPolicyIsProfileAware,
    )
    from .test_custom_make_surface_is_derived import (
        TestsFlextInfraCustomMakeSurfaceIsDerived,
    )
    from .test_custom_make_surface_is_single import (
        TestsFlextInfraCustomMakeSurfaceIsSingle,
    )
    from .test_custom_surface_never_shadows_public_verbs import (
        TestsFlextInfraCustomSurfaceNeverShadowsPublicVerbs,
    )
    from .test_engine_is_consumer_agnostic import (
        TestsFlextInfraEngineIsConsumerAgnostic,
    )
    from .test_gitignore_is_generated_from_ssot import (
        TestsFlextInfraGitignoreIsGeneratedFromSsot,
    )
    from .test_infra_constants_core import TestsFlextInfraInfraConstantsCore
    from .test_infra_constants_extra import TestsFlextInfraInfraConstantsExtra
    from .test_infra_git_identity_submodules import TestInfraGitIdentitySubmodules
    from .test_infra_main import TestsFlextInfraInfraMain
    from .test_infra_maintenance_cli import TestsFlextInfraInfraMaintenanceCli
    from .test_infra_maintenance_init import TestsFlextInfraInfraMaintenanceInit
    from .test_infra_maintenance_main import TestsFlextInfraInfraMaintenanceMain
    from .test_infra_maintenance_python_version import (
        TestsFlextInfraInfraMaintenancePythonVersion,
    )
    from .test_infra_paths import TestsFlextInfraInfraPaths
    from .test_infra_patterns_core import TestsFlextInfraInfraPatternsCore
    from .test_infra_patterns_extra import TestsFlextInfraInfraPatternsExtra
    from .test_infra_protocols import TestsFlextInfraInfraProtocols
    from .test_infra_public_api import TestsFlextInfraPublicApi
    from .test_infra_refactor_rope_migrations import (
        TestsFlextInfraInfraRefactorRopeMigrations,
    )
    from .test_infra_reporting_core import TestsFlextInfraInfraReportingCore
    from .test_infra_reporting_extra import TestsFlextInfraInfraReportingExtra
    from .test_infra_root_export_contract import TestsFlextInfraRootExportContract
    from .test_infra_rope_imports import TestsFlextInfraRopeImports
    from .test_infra_rope_service import TestsFlextInfraInfraRopeService
    from .test_infra_selection import TestsFlextInfraInfraSelection
    from .test_infra_typings import TestsFlextInfraInfraTypings
    from .test_infra_utilities import TestsFlextInfraInfraUtilities
    from .test_infra_version_core import TestsFlextInfraInfraVersionCore
    from .test_infra_version_extra import TestsFlextInfraInfraVersionExtra
    from .test_infra_versioning import TestsFlextInfraInfraVersioning
    from .test_infra_workspace_detector import TestsFlextInfraInfraWorkspaceDetector
    from .test_infra_workspace_orchestrator import (
        TestsFlextInfraInfraWorkspaceOrchestrator,
    )
    from .test_lockfile_is_tracked_at_the_resolution_root import (
        TestsFlextInfraLockfileIsTrackedAtTheResolutionRoot,
    )
    from .test_make_parse_is_side_effect_free import (
        TestsFlextInfraMakeParseIsSideEffectFree,
    )
    from .test_make_surface_never_silences_failures import (
        TestsFlextInfraMakeSurfaceNeverSilencesFailures,
    )
    from .test_pyproject_conform_preserves_lint_scope import (
        TestsFlextInfraPyprojectConformPreservesLintScope,
    )
    from .test_pyproject_conform_topology_sources import (
        TestsFlextInfraPyprojectConformTopologySources,
    )
    from .test_python_selector_render import TestsFlextInfraPythonSelectorRender
    from .test_workspace_check_scope import TestsFlextInfraWorkspaceCheckScope
    from .transformers.test_infra_transformer_cast_remover import (
        TestsFlextInfraTransformersCastRemover,
    )
    from .transformers.test_infra_transformer_class_nesting import (
        TestsFlextInfraTransformersInfraTransformerClassNesting,
    )
    from .transformers.test_infra_transformer_cli_modernizer import (
        TestsFlextInfraTransformersCliModernizer,
    )
    from .transformers.test_infra_transformer_enforcement_fixers import (
        TestsFlextInfraTransformersCompatibilityAlias,
        TestsFlextInfraTransformersFutureImport,
        TestsFlextInfraTransformersHardcodedVersion,
        TestsFlextInfraTransformersOpenEncoding,
        TestsFlextInfraTransformersPattern,
        TestsFlextInfraTransformersPatternList,
        TestsFlextInfraTransformersPatternStructlog,
        TestsFlextInfraTransformersTypingDictAttr,
        TestsFlextInfraTransformersTypingDictImport,
        TestsFlextInfraTransformersTypingUnifier,
    )
    from .transformers.test_infra_transformer_helper_consolidation import (
        TestsFlextInfraTransformersInfraTransformerHelperConsolidation,
    )
    from .transformers.test_infra_transformer_logging_modernizer import (
        TestsFlextInfraTransformersLoggingModernizer,
    )
    from .transformers.test_infra_transformer_nested_class_propagation import (
        TestsFlextInfraTransformersInfraTransformerNestedClassPropagation,
    )
    from .transformers.test_infra_transformer_pattern_modernizer import (
        TestsFlextInfraTransformersPatternModernizer,
    )
    from .transformers.test_infra_transformer_pydantic_modernizer import (
        TestsFlextInfraTransformersPydanticModernizer,
    )
    from .transformers.test_infra_transformer_result_di_modernizer import (
        TestsFlextInfraTransformersResultDiModernizer,
    )
    from .transformers.test_project_alias_migrator import (
        TestsFlextInfraRefactorProjectAliasMigrator,
    )
    from .validate.cprofile_report_tests import TestsFlextInfraCProfileReport
    from .validate.main_cli_tests import TestValidateCli
    from .validate.namespace_validator_tests import TestFlextInfraNamespaceValidator
    from .validate.pytest_runner_tests import TestsFlextInfraPytestRunner
    from .validate.pytest_selector_tests import TestsFlextInfraPytestSelectorValidator
    from .validate.testmon_db_tests import TestsFlextInfraTestmonDbInspector
    from .workspace.test_detector_owns_no_project_registry import (
        TestsDetectorOwnsNoProjectRegistry,
    )
    from .workspace.test_environment_provenance import (
        TestsFlextInfraWorkspaceEnvironmentProvenance,
    )
    from .workspace.test_facade_environment_sync import (
        TestsFlextInfraFacadeBaseMk,
        TestsFlextInfraFacadeEnvironmentSync,
    )
    from .workspace.test_main import TestsFlextInfraWorkspaceMain
    from .workspace.test_manifest_v2_contract import TestsWorkspaceManifestV2Contract
    from .workspace.test_vscode import TestsFlextInfraCodegenVscode
    from .workspace.test_work_finish_recovery import TestsWorkFinishRecovery
    from .workspace.test_work_service import TestsFlextInfraWorkService
    from .workspace.test_workspace_root_make_contract import (
        TestsWorkspaceRootMakeContract,
    )
    from .workspace.work_public_adversarial_fixture import (
        MetadataSnapshot,
        WorkAdversarialFixture,
    )
    from .workspace.work_public_finish_fixture import (
        ChildFinishState,
        WorkInvocation,
        WorkPublicFinishFixture,
    )
    from .workspace.work_public_service_fixture import (
        PullRequestCreateReceipt,
        WorkPublicServiceFixture,
    )
    from .workspace.worktree_fixture import WorktreeFixture
    from .workspace_factory import TestsFlextInfraWorkspaceFactory
__all__: tuple[str, ...] = (
    "ChildFinishState",
    "FlextInfraRefactorTypingUnificationRule",
    "MetadataSnapshot",
    "PullRequestCreateReceipt",
    "RealSubprocessRunner",
    "RefactorSafetyStub",
    "TestAllDirectoriesScanned",
    "TestAuditorBrokenLinks",
    "TestAuditorCore",
    "TestAuditorForbiddenTerms",
    "TestAuditorGithubLinks",
    "TestAuditorNormalize",
    "TestAuditorScope",
    "TestAuditorToMarkdown",
    "TestBuilderCore",
    "TestCheckIssueFormatted",
    "TestCheckOnlyMode",
    "TestCodegenBeadsLedger",
    "TestCodegenLinkedWorktreeManifest",
    "TestCodegenUvExcludeNewerOverlay",
    "TestConfigFixerExecute",
    "TestConfigFixerProcessFile",
    "TestConfigFixerPublicBehavior",
    "TestConfigFixerRun",
    "TestConfigFixerToArray",
    "TestEdgeCases",
    "TestExcludedDirectories",
    "TestExtendedRunnerExtras",
    "TestFlextInfraCheck",
    "TestFlextInfraConfigFixer",
    "TestFlextInfraNamespaceValidator",
    "TestFlextInfraWorkspaceChecker",
    "TestGateErrorReportingPublicBehavior",
    "TestGeneratedClassNamingConvention",
    "TestGeneratedFilesAreValidPython",
    "TestGitHookConformance",
    "TestInfraGitIdentitySubmodules",
    "TestIterMarkdownFiles",
    "TestLoadAuditBudgets",
    "TestProjectResultProperties",
    "TestRunCommandGateParsing",
    "TestRunProjectsPublicBehavior",
    "TestRunnerPublicBehavior",
    "TestValidateCli",
    "TestWorkspaceCheckCLI",
    "TestWorkspaceCheckCli",
    "TestWorkspaceCheckerCiGateRules",
    "TestWorkspaceCheckerErrorSummary",
    "TestWorkspaceCheckerResolveGates",
    "TestsBootstrapRefnameSafety",
    "TestsCodegenArtifactSsot",
    "TestsCodegenMakeEnvironment",
    "TestsCodegenWorkVerb",
    "TestsDetectorOwnsNoProjectRegistry",
    "TestsDocsCli",
    "TestsDocsRenderExcludeDocs",
    "TestsDocstringCoverage",
    "TestsEnforcementFixerOrchestrator",
    "TestsExtendedProjectRunners",
    "TestsFlextInfraApplyRenamesCli",
    "TestsFlextInfraBasemkGenerator",
    "TestsFlextInfraBasemkGeneratorEdgeCases",
    "TestsFlextInfraBasemkInit",
    "TestsFlextInfraBasemkMain",
    "TestsFlextInfraBasemkMakeContract",
    "TestsFlextInfraBasemkRenderer",
    "TestsFlextInfraCProfileReport",
    "TestsFlextInfraCliWhatSelector",
    "TestsFlextInfraCodegenConformProgress",
    "TestsFlextInfraCodegenGeneration",
    "TestsFlextInfraCodegenLazyInitService",
    "TestsFlextInfraCodegenManagedConflicts",
    "TestsFlextInfraCodegenPyprojectConform",
    "TestsFlextInfraCodegenVscode",
    "TestsFlextInfraContainerInfraContainer",
    "TestsFlextInfraCustomHandlerPolicyIsProfileAware",
    "TestsFlextInfraCustomMakeSurfaceIsDerived",
    "TestsFlextInfraCustomMakeSurfaceIsSingle",
    "TestsFlextInfraCustomMkPolicy",
    "TestsFlextInfraCustomSurfaceNeverShadowsPublicVerbs",
    "TestsFlextInfraDeferredSelfReferenceDetector",
    "TestsFlextInfraDepsDetectionClassify",
    "TestsFlextInfraDepsDetectionDeptry",
    "TestsFlextInfraDepsDetectionDiscover",
    "TestsFlextInfraDepsDetectionModels",
    "TestsFlextInfraDepsDetectionTypings",
    "TestsFlextInfraDepsDetectionTypingsFlow",
    "TestsFlextInfraDepsDetectionUncovered",
    "TestsFlextInfraDepsDetectorDetect",
    "TestsFlextInfraDepsDetectorDetectFailures",
    "TestsFlextInfraDepsDetectorInit",
    "TestsFlextInfraDepsDetectorMain",
    "TestsFlextInfraDepsDetectorModels",
    "TestsFlextInfraDepsDetectorReport",
    "TestsFlextInfraDepsDetectorReportFlags",
    "TestsFlextInfraDepsExtraPathsSync",
    "TestsFlextInfraDepsInit",
    "TestsFlextInfraDepsMainDispatch",
    "TestsFlextInfraDepsModernizerComments",
    "TestsFlextInfraDepsModernizerConsolidate",
    "TestsFlextInfraDepsModernizerCoverage",
    "TestsFlextInfraDepsModernizerHelpers",
    "TestsFlextInfraDepsModernizerMain",
    "TestsFlextInfraDepsModernizerMainExtra",
    "TestsFlextInfraDepsModernizerMypy",
    "TestsFlextInfraDepsModernizerPyright",
    "TestsFlextInfraDepsModernizerPytest",
    "TestsFlextInfraDepsModernizerTooling",
    "TestsFlextInfraDepsModernizerWorkspace",
    "TestsFlextInfraDiscoveryInfraDiscoveryEdgeCases",
    "TestsFlextInfraDocServer",
    "TestsFlextInfraEngineIsConsumerAgnostic",
    "TestsFlextInfraExtraPathsManager",
    "TestsFlextInfraExtraPathsSearchPaths",
    "TestsFlextInfraFacadeBaseMk",
    "TestsFlextInfraFacadeEnvironmentSync",
    "TestsFlextInfraGitFacet",
    "TestsFlextInfraGitignoreIsGeneratedFromSsot",
    "TestsFlextInfraInfraConstantsCore",
    "TestsFlextInfraInfraConstantsExtra",
    "TestsFlextInfraInfraMain",
    "TestsFlextInfraInfraMaintenanceCli",
    "TestsFlextInfraInfraMaintenanceInit",
    "TestsFlextInfraInfraMaintenanceMain",
    "TestsFlextInfraInfraMaintenancePythonVersion",
    "TestsFlextInfraInfraPaths",
    "TestsFlextInfraInfraPatternsCore",
    "TestsFlextInfraInfraPatternsExtra",
    "TestsFlextInfraInfraProtocols",
    "TestsFlextInfraInfraRefactorRopeMigrations",
    "TestsFlextInfraInfraReportingCore",
    "TestsFlextInfraInfraReportingExtra",
    "TestsFlextInfraInfraRopeService",
    "TestsFlextInfraInfraSelection",
    "TestsFlextInfraInfraTypings",
    "TestsFlextInfraInfraUtilities",
    "TestsFlextInfraInfraVersionCore",
    "TestsFlextInfraInfraVersionExtra",
    "TestsFlextInfraInfraVersioning",
    "TestsFlextInfraInfraWorkspaceDetector",
    "TestsFlextInfraInfraWorkspaceOrchestrator",
    "TestsFlextInfraInternalImportDetector",
    "TestsFlextInfraIoInfraTerminalDetection",
    "TestsFlextInfraLazyInitCleanup",
    "TestsFlextInfraLazyInitFixtureSettingsCollision",
    "TestsFlextInfraLazyInitHelpers",
    "TestsFlextInfraLazyInitProcessing",
    "TestsFlextInfraLazyInitRuntime",
    "TestsFlextInfraLazyInitTransforms",
    "TestsFlextInfraLockfileIsTrackedAtTheResolutionRoot",
    "TestsFlextInfraLooseObjectCharacterization",
    "TestsFlextInfraLooseObjectDetector",
    "TestsFlextInfraLooseTestFunctionDetector",
    "TestsFlextInfraMakeParseIsSideEffectFree",
    "TestsFlextInfraMakeSurfaceNeverSilencesFailures",
    "TestsFlextInfraManagedMaintenanceHeaders",
    "TestsFlextInfraModCircuitApply",
    "TestsFlextInfraModCircuitDecision",
    "TestsFlextInfraModCliRoute",
    "TestsFlextInfraModernizerPyrefly",
    "TestsFlextInfraPatternSmellDetector",
    "TestsFlextInfraPublicApi",
    "TestsFlextInfraPyprojectConformPreservesLintScope",
    "TestsFlextInfraPyprojectConformTopologySources",
    "TestsFlextInfraPytestFailClosedConfig",
    "TestsFlextInfraPytestRunner",
    "TestsFlextInfraPytestSelectorValidator",
    "TestsFlextInfraPytestTimeoutConfig",
    "TestsFlextInfraPythonSelectorRender",
    "TestsFlextInfraRefactorDeclarativeEnforcement",
    "TestsFlextInfraRefactorDeclarativeEnforcementInCensus",
    "TestsFlextInfraRefactorInfraRefactorClassAndPropagation",
    "TestsFlextInfraRefactorInfraRefactorClassPlacement",
    "TestsFlextInfraRefactorInfraRefactorCliModelsWorkflow",
    "TestsFlextInfraRefactorInfraRefactorImportModernizer",
    "TestsFlextInfraRefactorInfraRefactorLegacyAndAnnotations",
    "TestsFlextInfraRefactorInfraRefactorMigrateToClassMro",
    "TestsFlextInfraRefactorInfraRefactorMroCompleteness",
    "TestsFlextInfraRefactorInfraRefactorMroShape",
    "TestsFlextInfraRefactorInfraRefactorNamespaceAliases",
    "TestsFlextInfraRefactorInfraRefactorNamespaceEnforcer",
    "TestsFlextInfraRefactorInfraRefactorNamespaceMoves",
    "TestsFlextInfraRefactorInfraRefactorPatternCorrections",
    "TestsFlextInfraRefactorInfraRefactorPolicyFamilyRules",
    "TestsFlextInfraRefactorInfraRefactorProjectClassifier",
    "TestsFlextInfraRefactorInfraRefactorSafety",
    "TestsFlextInfraRefactorInfraRefactorService",
    "TestsFlextInfraRefactorInfraRefactorTypingUnifier",
    "TestsFlextInfraRefactorMainCli",
    "TestsFlextInfraRefactorProjectAliasMigrator",
    "TestsFlextInfraReleaseCli",
    "TestsFlextInfraReleaseDag",
    "TestsFlextInfraReleaseFlow",
    "TestsFlextInfraReleaseGit",
    "TestsFlextInfraReleaseHelpers",
    "TestsFlextInfraReleaseOrchestration",
    "TestsFlextInfraReleasePublish",
    "TestsFlextInfraReleaseVersionResolution",
    "TestsFlextInfraRootExportContract",
    "TestsFlextInfraRopeAnalysis",
    "TestsFlextInfraRopeImports",
    "TestsFlextInfraRopeStructure",
    "TestsFlextInfraTestmonDbInspector",
    "TestsFlextInfraTransformersCastRemover",
    "TestsFlextInfraTransformersCliModernizer",
    "TestsFlextInfraTransformersCompatibilityAlias",
    "TestsFlextInfraTransformersFutureImport",
    "TestsFlextInfraTransformersHardcodedVersion",
    "TestsFlextInfraTransformersInfraTransformerClassNesting",
    "TestsFlextInfraTransformersInfraTransformerHelperConsolidation",
    "TestsFlextInfraTransformersInfraTransformerNestedClassPropagation",
    "TestsFlextInfraTransformersLoggingModernizer",
    "TestsFlextInfraTransformersOpenEncoding",
    "TestsFlextInfraTransformersPattern",
    "TestsFlextInfraTransformersPatternList",
    "TestsFlextInfraTransformersPatternModernizer",
    "TestsFlextInfraTransformersPatternStructlog",
    "TestsFlextInfraTransformersPydanticModernizer",
    "TestsFlextInfraTransformersResultDiModernizer",
    "TestsFlextInfraTransformersTypingDictAttr",
    "TestsFlextInfraTransformersTypingDictImport",
    "TestsFlextInfraTransformersTypingUnifier",
    "TestsFlextInfraUtilitiesProtectedEdit",
    "TestsFlextInfraUtilitiesResourceLimits",
    "TestsFlextInfraUtilitiesRopeHooks",
    "TestsFlextInfraUtilitiesdiscoveryconsolidated",
    "TestsFlextInfraUtilitiesformatting",
    "TestsFlextInfraUtilitiessafety",
    "TestsFlextInfraUtilitiesscanning",
    "TestsFlextInfraWorkService",
    "TestsFlextInfraWorkspaceCheckScope",
    "TestsFlextInfraWorkspaceEnvironmentProvenance",
    "TestsFlextInfraWorkspaceFactory",
    "TestsFlextInfraWorkspaceMain",
    "TestsInfraGithub",
    "TestsMakeTestSelector",
    "TestsReleasePolicyFixtureRoot",
    "TestsReviewTemplateContracts",
    "TestsVscodeOwnerMerge",
    "TestsWorkFinishRecovery",
    "TestsWorkspaceManifestV2Contract",
    "TestsWorkspaceRootMakeContract",
    "TestsWorkspaceRootSetupSubmodules",
    "WorkAdversarialFixture",
    "WorkInvocation",
    "WorkPublicFinishFixture",
    "WorkPublicServiceFixture",
    "WorktreeFixture",
    "_utilities",
    "basemk",
    "c",
    "check",
    "codegen",
    "codemod",
    "conftest",
    "container",
    "d",
    "deps",
    "deptry_report_payload",
    "detectors",
    "discovery",
    "docs",
    "e",
    "github",
    "h",
    "io",
    "m",
    "models_resource",
    "modernizer_workspace",
    "modernizer_workspace_with_projects",
    "p",
    "r",
    "real_docs_project",
    "real_git_repo",
    "real_makefile_project",
    "real_python_package",
    "real_toml_project",
    "real_workspace",
    "refactor",
    "release",
    "rope_workspace",
    "s",
    "services_resource",
    "t",
    "td",
    "test_cprofile_entry",
    "test_git_fixture_isolation",
    "test_mro_service_base_alias",
    "test_repository_baseline_branch",
    "test_root_makefile_single_owner",
    "test_version_diag",
    "test_version_diag2",
    "tf",
    "tk",
    "tm",
    "tool_config_document",
    "transformers",
    "tv",
    "u",
    "validate",
    "workspace",
    "x",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._utilities": ("_utilities",),
            "._utilities.test_discovery_consolidated": (
                "TestsFlextInfraUtilitiesdiscoveryconsolidated",
            ),
            "._utilities.test_formatting": ("TestsFlextInfraUtilitiesformatting",),
            "._utilities.test_git_facet_gitpython": ("TestsFlextInfraGitFacet",),
            "._utilities.test_protected_edit": (
                "TestsFlextInfraUtilitiesProtectedEdit",
            ),
            "._utilities.test_resource_limits": (
                "TestsFlextInfraUtilitiesResourceLimits",
            ),
            "._utilities.test_rope_analysis": ("TestsFlextInfraRopeAnalysis",),
            "._utilities.test_rope_hooks": ("TestsFlextInfraUtilitiesRopeHooks",),
            "._utilities.test_rope_structure": ("TestsFlextInfraRopeStructure",),
            "._utilities.test_safety": ("TestsFlextInfraUtilitiessafety",),
            "._utilities.test_scanning": ("TestsFlextInfraUtilitiesscanning",),
            ".basemk": ("basemk",),
            ".basemk.test_bootstrap_refname_safety": ("TestsBootstrapRefnameSafety",),
            ".basemk.test_custom_mk_policy": ("TestsFlextInfraCustomMkPolicy",),
            ".basemk.test_generator": ("TestsFlextInfraBasemkGenerator",),
            ".basemk.test_generator_edge_cases": (
                "TestsFlextInfraBasemkGeneratorEdgeCases",
            ),
            ".basemk.test_init": ("TestsFlextInfraBasemkInit",),
            ".basemk.test_main": ("TestsFlextInfraBasemkMain",),
            ".basemk.test_make_contract": ("TestsFlextInfraBasemkMakeContract",),
            ".basemk.test_renderer": ("TestsFlextInfraBasemkRenderer",),
            ".check": ("check",),
            ".check.enforcement_fixer_orchestrator_tests": (
                "TestsEnforcementFixerOrchestrator",
            ),
            ".check.extended_cli_entry_tests": ("TestWorkspaceCheckCLI",),
            ".check.extended_config_fixer_errors_tests": (
                "TestConfigFixerPublicBehavior",
            ),
            ".check.extended_config_fixer_tests": (
                "TestConfigFixerExecute",
                "TestConfigFixerProcessFile",
                "TestConfigFixerRun",
                "TestConfigFixerToArray",
            ),
            ".check.extended_error_reporting_tests": (
                "TestGateErrorReportingPublicBehavior",
            ),
            ".check.extended_models_tests": (
                "TestCheckIssueFormatted",
                "TestProjectResultProperties",
                "TestRunCommandGateParsing",
                "TestWorkspaceCheckerErrorSummary",
            ),
            ".check.extended_project_runners_tests": ("TestsExtendedProjectRunners",),
            ".check.extended_resolve_gates_tests": (
                "TestWorkspaceCheckerCiGateRules",
                "TestWorkspaceCheckerResolveGates",
            ),
            ".check.extended_run_projects_tests": ("TestRunProjectsPublicBehavior",),
            ".check.extended_runners_extra_tests": ("TestExtendedRunnerExtras",),
            ".check.extended_runners_tests": ("TestRunnerPublicBehavior",),
            ".check.init_tests": ("TestFlextInfraCheck",),
            ".check.pyrefly_tests": ("TestFlextInfraConfigFixer",),
            ".check.test_cli": ("TestWorkspaceCheckCli",),
            ".check.workspace_tests": ("TestFlextInfraWorkspaceChecker",),
            ".cli_what_selector_tests": ("TestsFlextInfraCliWhatSelector",),
            ".codegen": ("codegen",),
            ".codegen.lazy_init_fixture_settings_tests": (
                "TestsFlextInfraLazyInitFixtureSettingsCollision",
            ),
            ".codegen.lazy_init_generation_tests": (
                "TestsFlextInfraCodegenGeneration",
            ),
            ".codegen.lazy_init_helpers_tests": ("TestsFlextInfraLazyInitHelpers",),
            ".codegen.lazy_init_process_tests": ("TestsFlextInfraLazyInitProcessing",),
            ".codegen.lazy_init_registry_wrapper_tests": (
                "TestsFlextInfraLazyInitCleanup",
            ),
            ".codegen.lazy_init_runtime_tests": ("TestsFlextInfraLazyInitRuntime",),
            ".codegen.lazy_init_service_tests": (
                "TestsFlextInfraCodegenLazyInitService",
            ),
            ".codegen.lazy_init_tests": (
                "TestAllDirectoriesScanned",
                "TestCheckOnlyMode",
                "TestEdgeCases",
                "TestExcludedDirectories",
            ),
            ".codegen.lazy_init_transforms_tests": (
                "TestsFlextInfraLazyInitTransforms",
            ),
            ".codegen.make_test_selector_tests": ("TestsMakeTestSelector",),
            ".codegen.scaffolder_naming_tests": (
                "TestGeneratedClassNamingConvention",
                "TestGeneratedFilesAreValidPython",
            ),
            ".codegen.test_codegen_artifact_ssot": ("TestsCodegenArtifactSsot",),
            ".codegen.test_codegen_beads_ledger": ("TestCodegenBeadsLedger",),
            ".codegen.test_codegen_conform_progress": (
                "TestsFlextInfraCodegenConformProgress",
            ),
            ".codegen.test_codegen_hook_conformance": ("TestGitHookConformance",),
            ".codegen.test_codegen_linked_worktree_manifest": (
                "TestCodegenLinkedWorktreeManifest",
            ),
            ".codegen.test_codegen_make_environment": ("TestsCodegenMakeEnvironment",),
            ".codegen.test_codegen_pyproject_conform": (
                "TestsFlextInfraCodegenPyprojectConform",
            ),
            ".codegen.test_codegen_uv_exclude_newer_overlay": (
                "TestCodegenUvExcludeNewerOverlay",
            ),
            ".codegen.test_managed_conflicts": (
                "TestsFlextInfraCodegenManagedConflicts",
            ),
            ".codegen.test_managed_maintenance_headers": (
                "TestsFlextInfraManagedMaintenanceHeaders",
            ),
            ".codegen.test_review_mro_vw2w_template_contracts": (
                "TestsReviewTemplateContracts",
            ),
            ".codegen.test_vscode_owner_merge": ("TestsVscodeOwnerMerge",),
            ".codegen.test_workspace_root_setup_submodules": (
                "TestsWorkspaceRootSetupSubmodules",
            ),
            ".codegen.worktree_verb_tests": ("TestsCodegenWorkVerb",),
            ".codemod": ("codemod",),
            ".codemod.test_mod_circuit": (
                "TestsFlextInfraModCircuitApply",
                "TestsFlextInfraModCircuitDecision",
                "TestsFlextInfraModCliRoute",
            ),
            ".conftest": ("conftest",),
            ".container": ("container",),
            ".container.test_infra_container": (
                "TestsFlextInfraContainerInfraContainer",
            ),
            ".deps": ("deps",),
            ".deps.test_detection_classify": ("TestsFlextInfraDepsDetectionClassify",),
            ".deps.test_detection_deptry": ("TestsFlextInfraDepsDetectionDeptry",),
            ".deps.test_detection_discover": ("TestsFlextInfraDepsDetectionDiscover",),
            ".deps.test_detection_models": ("TestsFlextInfraDepsDetectionModels",),
            ".deps.test_detection_typings": ("TestsFlextInfraDepsDetectionTypings",),
            ".deps.test_detection_typings_flow": (
                "TestsFlextInfraDepsDetectionTypingsFlow",
            ),
            ".deps.test_detection_uncovered": (
                "TestsFlextInfraDepsDetectionUncovered",
            ),
            ".deps.test_detector_detect": ("TestsFlextInfraDepsDetectorDetect",),
            ".deps.test_detector_detect_failures": (
                "TestsFlextInfraDepsDetectorDetectFailures",
            ),
            ".deps.test_detector_init": ("TestsFlextInfraDepsDetectorInit",),
            ".deps.test_detector_main": ("TestsFlextInfraDepsDetectorMain",),
            ".deps.test_detector_models": ("TestsFlextInfraDepsDetectorModels",),
            ".deps.test_detector_report": ("TestsFlextInfraDepsDetectorReport",),
            ".deps.test_detector_report_flags": (
                "TestsFlextInfraDepsDetectorReportFlags",
            ),
            ".deps.test_extra_paths_manager": ("TestsFlextInfraExtraPathsManager",),
            ".deps.test_extra_paths_search_paths": (
                "TestsFlextInfraExtraPathsSearchPaths",
            ),
            ".deps.test_extra_paths_sync": ("TestsFlextInfraDepsExtraPathsSync",),
            ".deps.test_init": ("TestsFlextInfraDepsInit",),
            ".deps.test_main_dispatch": ("TestsFlextInfraDepsMainDispatch",),
            ".deps.test_modernizer_comments": (
                "TestsFlextInfraDepsModernizerComments",
            ),
            ".deps.test_modernizer_consolidate": (
                "TestsFlextInfraDepsModernizerConsolidate",
            ),
            ".deps.test_modernizer_coverage": (
                "TestsFlextInfraDepsModernizerCoverage",
            ),
            ".deps.test_modernizer_helpers": ("TestsFlextInfraDepsModernizerHelpers",),
            ".deps.test_modernizer_main": ("TestsFlextInfraDepsModernizerMain",),
            ".deps.test_modernizer_main_extra": (
                "TestsFlextInfraDepsModernizerMainExtra",
            ),
            ".deps.test_modernizer_mypy": ("TestsFlextInfraDepsModernizerMypy",),
            ".deps.test_modernizer_pyrefly": ("TestsFlextInfraModernizerPyrefly",),
            ".deps.test_modernizer_pyright": ("TestsFlextInfraDepsModernizerPyright",),
            ".deps.test_modernizer_pytest": ("TestsFlextInfraDepsModernizerPytest",),
            ".deps.test_modernizer_tooling": ("TestsFlextInfraDepsModernizerTooling",),
            ".deps.test_modernizer_workspace": (
                "TestsFlextInfraDepsModernizerWorkspace",
            ),
            ".deps.test_pytest_fail_closed_config": (
                "TestsFlextInfraPytestFailClosedConfig",
            ),
            ".deps.test_pytest_timeout_config": ("TestsFlextInfraPytestTimeoutConfig",),
            ".detectors": ("detectors",),
            ".detectors.test_deferred_self_reference_ast": (
                "TestsFlextInfraDeferredSelfReferenceDetector",
            ),
            ".detectors.test_internal_import_detector": (
                "TestsFlextInfraInternalImportDetector",
            ),
            ".detectors.test_loose_object_detector": (
                "TestsFlextInfraLooseObjectDetector",
            ),
            ".detectors.test_loose_object_detector_characterization": (
                "TestsFlextInfraLooseObjectCharacterization",
            ),
            ".detectors.test_loose_test_function_detector": (
                "TestsFlextInfraLooseTestFunctionDetector",
            ),
            ".detectors.test_pattern_smell_detector": (
                "TestsFlextInfraPatternSmellDetector",
            ),
            ".discovery": ("discovery",),
            ".discovery.test_infra_discovery_edge_cases": (
                "TestsFlextInfraDiscoveryInfraDiscoveryEdgeCases",
            ),
            ".docs": ("docs",),
            ".docs.auditor_budgets_tests": ("TestLoadAuditBudgets",),
            ".docs.auditor_docstring_tests": ("TestsDocstringCoverage",),
            ".docs.auditor_links_tests": (
                "TestAuditorBrokenLinks",
                "TestAuditorGithubLinks",
                "TestAuditorToMarkdown",
            ),
            ".docs.auditor_scope_tests": (
                "TestAuditorForbiddenTerms",
                "TestAuditorScope",
            ),
            ".docs.auditor_tests": ("TestAuditorCore", "TestAuditorNormalize"),
            ".docs.builder_tests": ("TestBuilderCore",),
            ".docs.main_entry_tests": ("TestsDocsCli",),
            ".docs.render_tests": ("TestsDocsRenderExcludeDocs",),
            ".docs.server_tests": ("TestsFlextInfraDocServer",),
            ".docs.shared_iter_tests": ("TestIterMarkdownFiles",),
            ".fixtures": (
                "deptry_report_payload",
                "models_resource",
                "modernizer_workspace",
                "modernizer_workspace_with_projects",
                "real_docs_project",
                "real_makefile_project",
                "real_python_package",
                "real_toml_project",
                "real_workspace",
                "rope_workspace",
                "services_resource",
                "tool_config_document",
            ),
            ".fixtures_git": ("real_git_repo",),
            ".github": ("github",),
            ".github.main_tests": ("TestsInfraGithub",),
            ".io": ("io",),
            ".io.test_infra_terminal_detection": (
                "TestsFlextInfraIoInfraTerminalDetection",
            ),
            ".refactor": ("refactor",),
            ".refactor.test_apply_renames_cli": ("TestsFlextInfraApplyRenamesCli",),
            ".refactor.test_declarative_enforcement": (
                "TestsFlextInfraRefactorDeclarativeEnforcement",
                "TestsFlextInfraRefactorDeclarativeEnforcementInCensus",
            ),
            ".refactor.test_infra_refactor_class_and_propagation": (
                "TestsFlextInfraRefactorInfraRefactorClassAndPropagation",
            ),
            ".refactor.test_infra_refactor_class_placement": (
                "TestsFlextInfraRefactorInfraRefactorClassPlacement",
            ),
            ".refactor.test_infra_refactor_cli_models_workflow": (
                "TestsFlextInfraRefactorInfraRefactorCliModelsWorkflow",
            ),
            ".refactor.test_infra_refactor_import_modernizer": (
                "TestsFlextInfraRefactorInfraRefactorImportModernizer",
            ),
            ".refactor.test_infra_refactor_legacy_and_annotations": (
                "TestsFlextInfraRefactorInfraRefactorLegacyAndAnnotations",
            ),
            ".refactor.test_infra_refactor_migrate_to_class_mro": (
                "TestsFlextInfraRefactorInfraRefactorMigrateToClassMro",
            ),
            ".refactor.test_infra_refactor_mro_completeness": (
                "TestsFlextInfraRefactorInfraRefactorMroCompleteness",
            ),
            ".refactor.test_infra_refactor_mro_shape": (
                "TestsFlextInfraRefactorInfraRefactorMroShape",
            ),
            ".refactor.test_infra_refactor_namespace_aliases": (
                "TestsFlextInfraRefactorInfraRefactorNamespaceAliases",
            ),
            ".refactor.test_infra_refactor_namespace_enforcer": (
                "TestsFlextInfraRefactorInfraRefactorNamespaceEnforcer",
            ),
            ".refactor.test_infra_refactor_namespace_moves": (
                "TestsFlextInfraRefactorInfraRefactorNamespaceMoves",
            ),
            ".refactor.test_infra_refactor_pattern_corrections": (
                "TestsFlextInfraRefactorInfraRefactorPatternCorrections",
            ),
            ".refactor.test_infra_refactor_policy_family_rules": (
                "TestsFlextInfraRefactorInfraRefactorPolicyFamilyRules",
            ),
            ".refactor.test_infra_refactor_project_classifier": (
                "TestsFlextInfraRefactorInfraRefactorProjectClassifier",
            ),
            ".refactor.test_infra_refactor_safety": (
                "RefactorSafetyStub",
                "TestsFlextInfraRefactorInfraRefactorSafety",
            ),
            ".refactor.test_infra_refactor_service": (
                "TestsFlextInfraRefactorInfraRefactorService",
            ),
            ".refactor.test_infra_refactor_typing_unifier": (
                "FlextInfraRefactorTypingUnificationRule",
                "TestsFlextInfraRefactorInfraRefactorTypingUnifier",
            ),
            ".refactor.test_main_cli": ("TestsFlextInfraRefactorMainCli",),
            ".release": ("release",),
            ".release.flow_tests": ("TestsFlextInfraReleaseFlow",),
            ".release.main_tests": ("TestsFlextInfraReleaseCli",),
            ".release.orchestrator_git_tests": ("TestsFlextInfraReleaseGit",),
            ".release.orchestrator_helpers_tests": ("TestsFlextInfraReleaseHelpers",),
            ".release.orchestrator_publish_tests": ("TestsFlextInfraReleasePublish",),
            ".release.orchestrator_tests": ("TestsFlextInfraReleaseOrchestration",),
            ".release.policy_fixture_root_tests": ("TestsReleasePolicyFixtureRoot",),
            ".release.test_release_dag": ("TestsFlextInfraReleaseDag",),
            ".release.version_resolution_tests": (
                "TestsFlextInfraReleaseVersionResolution",
            ),
            ".runner_service": ("RealSubprocessRunner",),
            ".test_cprofile_entry": ("test_cprofile_entry",),
            ".test_custom_handler_policy_is_profile_aware": (
                "TestsFlextInfraCustomHandlerPolicyIsProfileAware",
            ),
            ".test_custom_make_surface_is_derived": (
                "TestsFlextInfraCustomMakeSurfaceIsDerived",
            ),
            ".test_custom_make_surface_is_single": (
                "TestsFlextInfraCustomMakeSurfaceIsSingle",
            ),
            ".test_custom_surface_never_shadows_public_verbs": (
                "TestsFlextInfraCustomSurfaceNeverShadowsPublicVerbs",
            ),
            ".test_engine_is_consumer_agnostic": (
                "TestsFlextInfraEngineIsConsumerAgnostic",
            ),
            ".test_git_fixture_isolation": ("test_git_fixture_isolation",),
            ".test_gitignore_is_generated_from_ssot": (
                "TestsFlextInfraGitignoreIsGeneratedFromSsot",
            ),
            ".test_infra_constants_core": ("TestsFlextInfraInfraConstantsCore",),
            ".test_infra_constants_extra": ("TestsFlextInfraInfraConstantsExtra",),
            ".test_infra_git_identity_submodules": ("TestInfraGitIdentitySubmodules",),
            ".test_infra_main": ("TestsFlextInfraInfraMain",),
            ".test_infra_maintenance_cli": ("TestsFlextInfraInfraMaintenanceCli",),
            ".test_infra_maintenance_init": ("TestsFlextInfraInfraMaintenanceInit",),
            ".test_infra_maintenance_main": ("TestsFlextInfraInfraMaintenanceMain",),
            ".test_infra_maintenance_python_version": (
                "TestsFlextInfraInfraMaintenancePythonVersion",
            ),
            ".test_infra_paths": ("TestsFlextInfraInfraPaths",),
            ".test_infra_patterns_core": ("TestsFlextInfraInfraPatternsCore",),
            ".test_infra_patterns_extra": ("TestsFlextInfraInfraPatternsExtra",),
            ".test_infra_protocols": ("TestsFlextInfraInfraProtocols",),
            ".test_infra_public_api": ("TestsFlextInfraPublicApi",),
            ".test_infra_refactor_rope_migrations": (
                "TestsFlextInfraInfraRefactorRopeMigrations",
            ),
            ".test_infra_reporting_core": ("TestsFlextInfraInfraReportingCore",),
            ".test_infra_reporting_extra": ("TestsFlextInfraInfraReportingExtra",),
            ".test_infra_root_export_contract": ("TestsFlextInfraRootExportContract",),
            ".test_infra_rope_imports": ("TestsFlextInfraRopeImports",),
            ".test_infra_rope_service": ("TestsFlextInfraInfraRopeService",),
            ".test_infra_selection": ("TestsFlextInfraInfraSelection",),
            ".test_infra_typings": ("TestsFlextInfraInfraTypings",),
            ".test_infra_utilities": ("TestsFlextInfraInfraUtilities",),
            ".test_infra_version_core": ("TestsFlextInfraInfraVersionCore",),
            ".test_infra_version_extra": ("TestsFlextInfraInfraVersionExtra",),
            ".test_infra_versioning": ("TestsFlextInfraInfraVersioning",),
            ".test_infra_workspace_detector": (
                "TestsFlextInfraInfraWorkspaceDetector",
            ),
            ".test_infra_workspace_orchestrator": (
                "TestsFlextInfraInfraWorkspaceOrchestrator",
            ),
            ".test_lockfile_is_tracked_at_the_resolution_root": (
                "TestsFlextInfraLockfileIsTrackedAtTheResolutionRoot",
            ),
            ".test_make_parse_is_side_effect_free": (
                "TestsFlextInfraMakeParseIsSideEffectFree",
            ),
            ".test_make_surface_never_silences_failures": (
                "TestsFlextInfraMakeSurfaceNeverSilencesFailures",
            ),
            ".test_mro_service_base_alias": ("test_mro_service_base_alias",),
            ".test_pyproject_conform_preserves_lint_scope": (
                "TestsFlextInfraPyprojectConformPreservesLintScope",
            ),
            ".test_pyproject_conform_topology_sources": (
                "TestsFlextInfraPyprojectConformTopologySources",
            ),
            ".test_python_selector_render": ("TestsFlextInfraPythonSelectorRender",),
            ".test_repository_baseline_branch": ("test_repository_baseline_branch",),
            ".test_root_makefile_single_owner": ("test_root_makefile_single_owner",),
            ".test_version_diag": ("test_version_diag",),
            ".test_version_diag2": ("test_version_diag2",),
            ".test_workspace_check_scope": ("TestsFlextInfraWorkspaceCheckScope",),
            ".transformers": ("transformers",),
            ".transformers.test_infra_transformer_cast_remover": (
                "TestsFlextInfraTransformersCastRemover",
            ),
            ".transformers.test_infra_transformer_class_nesting": (
                "TestsFlextInfraTransformersInfraTransformerClassNesting",
            ),
            ".transformers.test_infra_transformer_cli_modernizer": (
                "TestsFlextInfraTransformersCliModernizer",
            ),
            ".transformers.test_infra_transformer_enforcement_fixers": (
                "TestsFlextInfraTransformersCompatibilityAlias",
                "TestsFlextInfraTransformersFutureImport",
                "TestsFlextInfraTransformersHardcodedVersion",
                "TestsFlextInfraTransformersOpenEncoding",
                "TestsFlextInfraTransformersPattern",
                "TestsFlextInfraTransformersPatternList",
                "TestsFlextInfraTransformersPatternStructlog",
                "TestsFlextInfraTransformersTypingDictAttr",
                "TestsFlextInfraTransformersTypingDictImport",
                "TestsFlextInfraTransformersTypingUnifier",
            ),
            ".transformers.test_infra_transformer_helper_consolidation": (
                "TestsFlextInfraTransformersInfraTransformerHelperConsolidation",
            ),
            ".transformers.test_infra_transformer_logging_modernizer": (
                "TestsFlextInfraTransformersLoggingModernizer",
            ),
            ".transformers.test_infra_transformer_nested_class_propagation": (
                "TestsFlextInfraTransformersInfraTransformerNestedClassPropagation",
            ),
            ".transformers.test_infra_transformer_pattern_modernizer": (
                "TestsFlextInfraTransformersPatternModernizer",
            ),
            ".transformers.test_infra_transformer_pydantic_modernizer": (
                "TestsFlextInfraTransformersPydanticModernizer",
            ),
            ".transformers.test_infra_transformer_result_di_modernizer": (
                "TestsFlextInfraTransformersResultDiModernizer",
            ),
            ".transformers.test_project_alias_migrator": (
                "TestsFlextInfraRefactorProjectAliasMigrator",
            ),
            ".validate": ("validate",),
            ".validate.cprofile_report_tests": ("TestsFlextInfraCProfileReport",),
            ".validate.main_cli_tests": ("TestValidateCli",),
            ".validate.namespace_validator_tests": (
                "TestFlextInfraNamespaceValidator",
            ),
            ".validate.pytest_runner_tests": ("TestsFlextInfraPytestRunner",),
            ".validate.pytest_selector_tests": (
                "TestsFlextInfraPytestSelectorValidator",
            ),
            ".validate.testmon_db_tests": ("TestsFlextInfraTestmonDbInspector",),
            ".workspace": ("workspace",),
            ".workspace.test_detector_owns_no_project_registry": (
                "TestsDetectorOwnsNoProjectRegistry",
            ),
            ".workspace.test_environment_provenance": (
                "TestsFlextInfraWorkspaceEnvironmentProvenance",
            ),
            ".workspace.test_facade_environment_sync": (
                "TestsFlextInfraFacadeBaseMk",
                "TestsFlextInfraFacadeEnvironmentSync",
            ),
            ".workspace.test_main": ("TestsFlextInfraWorkspaceMain",),
            ".workspace.test_manifest_v2_contract": (
                "TestsWorkspaceManifestV2Contract",
            ),
            ".workspace.test_vscode": ("TestsFlextInfraCodegenVscode",),
            ".workspace.test_work_finish_recovery": ("TestsWorkFinishRecovery",),
            ".workspace.test_work_service": ("TestsFlextInfraWorkService",),
            ".workspace.test_workspace_root_make_contract": (
                "TestsWorkspaceRootMakeContract",
            ),
            ".workspace.work_public_adversarial_fixture": (
                "MetadataSnapshot",
                "WorkAdversarialFixture",
            ),
            ".workspace.work_public_finish_fixture": (
                "ChildFinishState",
                "WorkInvocation",
                "WorkPublicFinishFixture",
            ),
            ".workspace.work_public_service_fixture": (
                "PullRequestCreateReceipt",
                "WorkPublicServiceFixture",
            ),
            ".workspace.worktree_fixture": ("WorktreeFixture",),
            ".workspace_factory": ("TestsFlextInfraWorkspaceFactory",),
            "flext_tests": (
                "c",
                "d",
                "e",
                "h",
                "m",
                "p",
                "r",
                "s",
                "t",
                "td",
                "tf",
                "tk",
                "tm",
                "tv",
                "u",
                "x",
            ),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
