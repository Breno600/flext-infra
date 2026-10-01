# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

from .__version__ import (
    __author__ as __author__,
    __author_email__ as __author_email__,
    __description__ as __description__,
    __license__ as __license__,
    __title__ as __title__,
    __url__ as __url__,
    __version__ as __version__,
    __version_info__ as __version_info__,
)

if TYPE_CHECKING:
    from flext_cli import d, e, h, r, x

    from . import (
        check,
        codegen,
        codemod,
        deps,
        detectors,
        docs,
        gates,
        maintenance,
        refactor,
        release,
        services,
        transformers,
        validate,
        workspace,
    )
    from ._config import FlextInfraConfig, config
    from ._settings import FlextInfraSettings, settings
    from .api import FlextInfra, infra
    from .base import FlextInfraServiceBase, s
    from .base_selection import FlextInfraProjectSelectionServiceBase
    from .check.gate_registry import FlextInfraGateRegistry
    from .check.workspace_check import FlextInfraWorkspaceChecker
    from .check.workspace_check_gates import FlextInfraWorkspaceCheckGatesMixin
    from .cli import FlextInfraCli, docs_main, main
    from .codegen.census import FlextInfraCodegenCensus
    from .codegen.codegen_generation import FlextInfraCodegenGeneration
    from .codegen.codegen_transaction import FlextInfraCodegenTransaction
    from .codegen.conform import FlextInfraCodegenConform
    from .codegen.consolidator import FlextInfraCodegenConsolidator
    from .codegen.constants_quality_gate import FlextInfraCodegenQualityGate
    from .codegen.file_leases import FlextInfraCodegenFileLeases
    from .codegen.fixer import FlextInfraCodegenFixer
    from .codegen.layout import FlextInfraCodegenLayout
    from .codegen.lazy_init import FlextInfraCodegenLazyInit
    from .codegen.lazy_init_planner import FlextInfraCodegenLazyInitPlanner
    from .codegen.make_bootstrap import FlextInfraCodegenMakeBootstrap
    from .codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts
    from .codegen.mise_artifacts_workspace import FlextInfraMiseWorkspacePlanner
    from .codegen.pipeline import (
        FlextInfraCodegenLazyInitGenerationMixin,
        FlextInfraCodegenPipeline,
        FlextInfraCodegenPipelineStagesMixin,
        FlextInfraMiseArtifactsFiles,
        publish_file_plan,
    )
    from .codegen.project_new import FlextInfraCodegenProjectNew
    from .codegen.protocol_models import FlextInfraCodegenProtocolModels
    from .codegen.py_typed import FlextInfraCodegenPyTyped
    from .codegen.scaffolder import FlextInfraCodegenScaffolder
    from .codegen.version_file import FlextInfraCodegenVersionFile
    from .codemod.apply_renames import FlextInfraApplyRenames
    from .codemod.ast_scan import FlextInfraCodemodAstScan
    from .codemod.batch_apply import FlextInfraCodemodBatchApply
    from .codemod.batch_gates import FlextInfraModGateEngine
    from .codemod.batch_replacements import FlextInfraModReplacements
    from .codemod.sed_apply import FlextInfraCodemodSedApply
    from .codemod.semantic_apply import FlextInfraCodemodSemanticApply
    from .codemod.snapshot_reconciler import FlextInfraCodemodSnapshotReconciler
    from .codemod.snapshot_refresh import FlextInfraCodemodSnapshotRefresh
    from .codemod.text_gates import FlextInfraModTextGateEngine
    from .constants import FlextInfraConstants, FlextInfraConstants as c
    from .deps.detection import FlextInfraDependencyDetectionService
    from .deps.detection_analysis import FlextInfraDependencyDetectionAnalysis
    from .deps.detector import FlextInfraRuntimeDevDependencyDetector
    from .deps.detector_runtime import FlextInfraDependencyDetectorRuntime
    from .deps.extra_paths import FlextInfraExtraPathsManager
    from .deps.fix_pyrefly_config import FlextInfraConfigFixer
    from .deps.lock_integrity import FlextInfraLockIntegrityVerifier
    from .deps.modernizer import FlextInfraPyprojectModernizer
    from .deps.phases.consolidate_groups import FlextInfraConsolidateGroupsPhase
    from .deps.phases.ensure_packaging import FlextInfraEnsurePackagingPhase
    from .deps.phases.ensure_pyrefly import FlextInfraEnsurePyreflyConfigPhase
    from .deps.phases.ensure_pyright import FlextInfraEnsurePyrightConfigPhase
    from .deps.phases.ensure_ruff import FlextInfraEnsureRuffConfigPhase
    from .deps.phases.inject_comments import FlextInfraInjectCommentsPhase
    from .deps.phases.tool_tables import FlextInfraToolTablesPhase
    from .detectors.class_placement_detector import FlextInfraClassPlacementDetector
    from .detectors.compatibility_alias_detector import (
        FlextInfraCompatibilityAliasDetector,
    )
    from .detectors.cyclic_import_detector import FlextInfraCyclicImportDetector
    from .detectors.deferred_self_reference_detector import (
        FlextInfraDeferredSelfReferenceDetector,
    )
    from .detectors.import_alias_detector import FlextInfraImportAliasDetector
    from .detectors.internal_import_detector import FlextInfraInternalImportDetector
    from .detectors.loose_object_detector import FlextInfraLooseObjectDetector
    from .detectors.lsp_diagnostics import FlextInfraLspDiagnosticsDetector
    from .detectors.namespace_source_detector import FlextInfraNamespaceSourceDetector
    from .detectors.private_import_bypass_detector import (
        FlextInfraPrivateImportBypassDetector,
    )
    from .detectors.runtime_alias_detector import FlextInfraRuntimeAliasDetector
    from .docs.auditor import FlextInfraDocAuditor
    from .docs.auditor_mixin import FlextInfraDocAuditorMixin
    from .docs.base import FlextInfraDocServiceBase
    from .docs.builder import FlextInfraDocBuilder
    from .docs.collector import FlextInfraDocCollector
    from .docs.fixer import FlextInfraDocFixer
    from .docs.formatter import FlextInfraDocFormatter
    from .docs.generator import FlextInfraDocGenerator
    from .docs.server import FlextInfraDocServer
    from .docs.validator import FlextInfraDocValidator
    from .gates.bandit import FlextInfraBanditGate
    from .gates.base_gate import FlextInfraGate
    from .gates.canonical_alias import FlextInfraCanonicalAliasGate
    from .gates.deferred_self_reference import FlextInfraDeferredSelfReferenceGate
    from .gates.direnv import FlextInfraDirenvGate
    from .gates.duplication import FlextInfraDuplicationGate
    from .gates.index_declarations import FlextInfraIndexDeclarationsGate
    from .gates.layout import FlextInfraLayoutGate
    from .gates.loc_cap import FlextInfraLocCapGate
    from .gates.markdown import FlextInfraMarkdownGate
    from .gates.markdown_code import FlextInfraMarkdownCodeGate
    from .gates.markdown_code_sources import (
        is_syntax_broken,
        source_name,
        write_docstring_sources,
        write_fenced_block_sources,
    )
    from .gates.markdown_format import FlextInfraMarkdownFormatGate
    from .gates.markdown_support import (
        FlextInfraMarkdownGateBase,
        collect_markdown_files,
        read_ignore_patterns,
    )
    from .gates.mypy import FlextInfraMypyGate
    from .gates.namespace import FlextInfraNamespaceGate
    from .gates.pyrefly import FlextInfraPyreflyGate
    from .gates.pyright import FlextInfraPyrightGate
    from .gates.ruff_format import FlextInfraRuffFormatGate
    from .gates.ruff_lint import FlextInfraRuffLintGate
    from .gates.runtime_census import FlextInfraRuntimeCensusGate
    from .gates.scanner_gate import FlextInfraScannerGateMixin
    from .gates.smells import FlextInfraSmellsGate
    from .git import FlextInfraGitService
    from .maintenance.clean import FlextInfraCleanService
    from .maintenance.python_version import FlextInfraPythonVersionEnforcer
    from .maintenance.sonarcloud import FlextInfraSonarcloudSettingsSync
    from .models import FlextInfraModels, FlextInfraModels as m
    from .promoted import FlextInfraPromoted
    from .protocols import (
        FlextInfraProtocols,
        FlextInfraProtocols as p,
        FlextInfraProtocolsBase,
    )
    from .refactor.accessor_migration import FlextInfraAccessorMigrationOrchestrator
    from .refactor.census import FlextInfraRefactorCensus
    from .refactor.classvar_constant_autofix import (
        FlextInfraRefactorClassvarConstantAutofix,
    )
    from .refactor.namespace_enforcer import FlextInfraNamespaceEnforcer
    from .refactor.namespace_enforcer_phases import (
        FlextInfraNamespaceEnforcerPhasesMixin,
    )
    from .refactor.project_alias_migrator import FlextInfraRefactorProjectAliasMigrator
    from .refactor.project_classifier import FlextInfraProjectClassifier
    from .refactor.wrapper_root_namespace import FlextInfraWrapperRootNamespaceRefactor
    from .release.orchestrator import FlextInfraReleaseOrchestrator
    from .services.candidate_bootstrap import FlextInfraCandidateBootstrapService
    from .services.cli_dispatch import FlextInfraCliDispatchService
    from .services.cli_route_base import FlextInfraCliRouteBase
    from .services.cli_routes import FlextInfraCliRouteService
    from .services.cli_routes_codegen import FlextInfraCodegenRoutes
    from .services.cli_routes_refactor import FlextInfraRefactorRoutes
    from .services.cli_routes_validate import FlextInfraValidationRoutes
    from .services.cli_routes_validate_commands import FlextInfraValidationCommandRoutes
    from .services.cli_routes_workspace import FlextInfraWorkspaceRoutes
    from .services.codegen import FlextInfraCodegen
    from .transformers.rope_transformer import FlextInfraRopeTransformer
    from .typings import FlextInfraTypes, FlextInfraTypes as t
    from .utilities import FlextInfraUtilities, FlextInfraUtilities as u
    from .validate.cprofile_report import FlextInfraCProfileReport
    from .validate.fresh_import import FlextInfraValidateFreshImport
    from .validate.import_cycles import FlextInfraValidateImportCycles
    from .validate.inventory import FlextInfraInventoryService
    from .validate.lazy_map_freshness import FlextInfraValidateLazyMapFreshness
    from .validate.loc_delta import FlextInfraLocDeltaValidator
    from .validate.manual_command import FlextInfraManualCommandValidator
    from .validate.namespace_rules import FlextInfraNamespaceRules
    from .validate.namespace_validator import FlextInfraNamespaceValidator
    from .validate.pytest_diag import FlextInfraPytestDiagExtractor
    from .validate.pytest_runner import FlextInfraPytestRunner
    from .validate.runtime_census import FlextInfraRuntimeCensusValidator
    from .validate.scanner import FlextInfraTextPatternScanner
    from .validate.skill_validator import FlextInfraSkillValidator
    from .validate.stub_chain import FlextInfraStubSupplyChain
    from .validate.testmon_db import FlextInfraTestmonDbInspector
    from .workspace.detector import FlextInfraWorkspaceDetector
    from .workspace.environment import FlextInfraWorkspaceEnvironmentMixin
    from .workspace.environment_contracts import FlextInfraWorkspaceEnvironmentContracts
    from .workspace.environment_provenance import (
        FlextInfraWorkspaceEnvironmentProvenance,
    )
    from .workspace.flext_binding import FlextInfraFlextBindingService
    from .workspace.propagation import FlextInfraWorkspacePropagation
    from .workspace.rope import FlextInfraRopeWorkspace
    from .worktree import FlextInfraWorktreeService


__all__: tuple[str, ...] = (
    "FlextInfra",
    "FlextInfraAccessorMigrationOrchestrator",
    "FlextInfraApplyRenames",
    "FlextInfraBanditGate",
    "FlextInfraCProfileReport",
    "FlextInfraCandidateBootstrapService",
    "FlextInfraCanonicalAliasGate",
    "FlextInfraClassPlacementDetector",
    "FlextInfraCleanService",
    "FlextInfraCli",
    "FlextInfraCliDispatchService",
    "FlextInfraCliRouteBase",
    "FlextInfraCliRouteService",
    "FlextInfraCodegen",
    "FlextInfraCodegenCensus",
    "FlextInfraCodegenConform",
    "FlextInfraCodegenConsolidator",
    "FlextInfraCodegenFileLeases",
    "FlextInfraCodegenFixer",
    "FlextInfraCodegenGeneration",
    "FlextInfraCodegenLayout",
    "FlextInfraCodegenLazyInit",
    "FlextInfraCodegenLazyInitGenerationMixin",
    "FlextInfraCodegenLazyInitPlanner",
    "FlextInfraCodegenMakeBootstrap",
    "FlextInfraCodegenMiseArtifacts",
    "FlextInfraCodegenPipeline",
    "FlextInfraCodegenPipelineStagesMixin",
    "FlextInfraCodegenProjectNew",
    "FlextInfraCodegenProtocolModels",
    "FlextInfraCodegenPyTyped",
    "FlextInfraCodegenQualityGate",
    "FlextInfraCodegenRoutes",
    "FlextInfraCodegenScaffolder",
    "FlextInfraCodegenTransaction",
    "FlextInfraCodegenVersionFile",
    "FlextInfraCodemodAstScan",
    "FlextInfraCodemodBatchApply",
    "FlextInfraCodemodSedApply",
    "FlextInfraCodemodSemanticApply",
    "FlextInfraCodemodSnapshotReconciler",
    "FlextInfraCodemodSnapshotRefresh",
    "FlextInfraCompatibilityAliasDetector",
    "FlextInfraConfig",
    "FlextInfraConfigFixer",
    "FlextInfraConsolidateGroupsPhase",
    "FlextInfraConstants",
    "FlextInfraCyclicImportDetector",
    "FlextInfraDeferredSelfReferenceDetector",
    "FlextInfraDeferredSelfReferenceGate",
    "FlextInfraDependencyDetectionAnalysis",
    "FlextInfraDependencyDetectionService",
    "FlextInfraDependencyDetectorRuntime",
    "FlextInfraDirenvGate",
    "FlextInfraDocAuditor",
    "FlextInfraDocAuditorMixin",
    "FlextInfraDocBuilder",
    "FlextInfraDocCollector",
    "FlextInfraDocFixer",
    "FlextInfraDocFormatter",
    "FlextInfraDocGenerator",
    "FlextInfraDocServer",
    "FlextInfraDocServiceBase",
    "FlextInfraDocValidator",
    "FlextInfraDuplicationGate",
    "FlextInfraEnsurePackagingPhase",
    "FlextInfraEnsurePyreflyConfigPhase",
    "FlextInfraEnsurePyrightConfigPhase",
    "FlextInfraEnsureRuffConfigPhase",
    "FlextInfraExtraPathsManager",
    "FlextInfraFlextBindingService",
    "FlextInfraGate",
    "FlextInfraGateRegistry",
    "FlextInfraGitService",
    "FlextInfraImportAliasDetector",
    "FlextInfraIndexDeclarationsGate",
    "FlextInfraInjectCommentsPhase",
    "FlextInfraInternalImportDetector",
    "FlextInfraInventoryService",
    "FlextInfraLayoutGate",
    "FlextInfraLocCapGate",
    "FlextInfraLocDeltaValidator",
    "FlextInfraLockIntegrityVerifier",
    "FlextInfraLooseObjectDetector",
    "FlextInfraLspDiagnosticsDetector",
    "FlextInfraManualCommandValidator",
    "FlextInfraMarkdownCodeGate",
    "FlextInfraMarkdownFormatGate",
    "FlextInfraMarkdownGate",
    "FlextInfraMarkdownGateBase",
    "FlextInfraMiseArtifactsFiles",
    "FlextInfraMiseWorkspacePlanner",
    "FlextInfraModGateEngine",
    "FlextInfraModReplacements",
    "FlextInfraModTextGateEngine",
    "FlextInfraModels",
    "FlextInfraMypyGate",
    "FlextInfraNamespaceEnforcer",
    "FlextInfraNamespaceEnforcerPhasesMixin",
    "FlextInfraNamespaceGate",
    "FlextInfraNamespaceRules",
    "FlextInfraNamespaceSourceDetector",
    "FlextInfraNamespaceValidator",
    "FlextInfraPrivateImportBypassDetector",
    "FlextInfraProjectClassifier",
    "FlextInfraProjectSelectionServiceBase",
    "FlextInfraPromoted",
    "FlextInfraProtocols",
    "FlextInfraProtocolsBase",
    "FlextInfraPyprojectModernizer",
    "FlextInfraPyreflyGate",
    "FlextInfraPyrightGate",
    "FlextInfraPytestDiagExtractor",
    "FlextInfraPytestRunner",
    "FlextInfraPythonVersionEnforcer",
    "FlextInfraRefactorCensus",
    "FlextInfraRefactorClassvarConstantAutofix",
    "FlextInfraRefactorProjectAliasMigrator",
    "FlextInfraRefactorRoutes",
    "FlextInfraReleaseOrchestrator",
    "FlextInfraRopeTransformer",
    "FlextInfraRopeWorkspace",
    "FlextInfraRuffFormatGate",
    "FlextInfraRuffLintGate",
    "FlextInfraRuntimeAliasDetector",
    "FlextInfraRuntimeCensusGate",
    "FlextInfraRuntimeCensusValidator",
    "FlextInfraRuntimeDevDependencyDetector",
    "FlextInfraScannerGateMixin",
    "FlextInfraServiceBase",
    "FlextInfraSettings",
    "FlextInfraSkillValidator",
    "FlextInfraSmellsGate",
    "FlextInfraSonarcloudSettingsSync",
    "FlextInfraStubSupplyChain",
    "FlextInfraTestmonDbInspector",
    "FlextInfraTextPatternScanner",
    "FlextInfraToolTablesPhase",
    "FlextInfraTypes",
    "FlextInfraUtilities",
    "FlextInfraValidateFreshImport",
    "FlextInfraValidateImportCycles",
    "FlextInfraValidateLazyMapFreshness",
    "FlextInfraValidationCommandRoutes",
    "FlextInfraValidationRoutes",
    "FlextInfraWorkspaceCheckGatesMixin",
    "FlextInfraWorkspaceChecker",
    "FlextInfraWorkspaceDetector",
    "FlextInfraWorkspaceEnvironmentContracts",
    "FlextInfraWorkspaceEnvironmentMixin",
    "FlextInfraWorkspaceEnvironmentProvenance",
    "FlextInfraWorkspacePropagation",
    "FlextInfraWorkspaceRoutes",
    "FlextInfraWorktreeService",
    "FlextInfraWrapperRootNamespaceRefactor",
    "__author__",
    "__author_email__",
    "__description__",
    "__license__",
    "__title__",
    "__url__",
    "__version__",
    "__version_info__",
    "c",
    "check",
    "codegen",
    "codemod",
    "collect_markdown_files",
    "config",
    "d",
    "deps",
    "detectors",
    "docs",
    "docs_main",
    "e",
    "gates",
    "h",
    "infra",
    "is_syntax_broken",
    "m",
    "main",
    "maintenance",
    "p",
    "publish_file_plan",
    "r",
    "read_ignore_patterns",
    "refactor",
    "release",
    "s",
    "services",
    "settings",
    "source_name",
    "t",
    "transformers",
    "u",
    "validate",
    "workspace",
    "write_docstring_sources",
    "write_fenced_block_sources",
    "x",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._config": ("FlextInfraConfig", "config"),
            "._settings": ("FlextInfraSettings", "settings"),
            ".api": ("FlextInfra", "infra"),
            ".base": ("FlextInfraServiceBase", "s"),
            ".base_selection": ("FlextInfraProjectSelectionServiceBase",),
            ".check": ("check",),
            ".check.gate_registry": ("FlextInfraGateRegistry",),
            ".check.workspace_check": ("FlextInfraWorkspaceChecker",),
            ".check.workspace_check_gates": ("FlextInfraWorkspaceCheckGatesMixin",),
            ".cli": ("FlextInfraCli", "docs_main", "main"),
            ".codegen": ("codegen",),
            ".codegen.census": ("FlextInfraCodegenCensus",),
            ".codegen.codegen_generation": ("FlextInfraCodegenGeneration",),
            ".codegen.codegen_transaction": ("FlextInfraCodegenTransaction",),
            ".codegen.conform": ("FlextInfraCodegenConform",),
            ".codegen.consolidator": ("FlextInfraCodegenConsolidator",),
            ".codegen.constants_quality_gate": ("FlextInfraCodegenQualityGate",),
            ".codegen.file_leases": ("FlextInfraCodegenFileLeases",),
            ".codegen.fixer": ("FlextInfraCodegenFixer",),
            ".codegen.layout": ("FlextInfraCodegenLayout",),
            ".codegen.lazy_init": ("FlextInfraCodegenLazyInit",),
            ".codegen.lazy_init_planner": ("FlextInfraCodegenLazyInitPlanner",),
            ".codegen.make_bootstrap": ("FlextInfraCodegenMakeBootstrap",),
            ".codegen.mise_artifacts": ("FlextInfraCodegenMiseArtifacts",),
            ".codegen.mise_artifacts_workspace": ("FlextInfraMiseWorkspacePlanner",),
            ".codegen.pipeline": (
                "FlextInfraCodegenLazyInitGenerationMixin",
                "FlextInfraCodegenPipeline",
                "FlextInfraCodegenPipelineStagesMixin",
                "FlextInfraMiseArtifactsFiles",
                "publish_file_plan",
            ),
            ".codegen.project_new": ("FlextInfraCodegenProjectNew",),
            ".codegen.protocol_models": ("FlextInfraCodegenProtocolModels",),
            ".codegen.py_typed": ("FlextInfraCodegenPyTyped",),
            ".codegen.scaffolder": ("FlextInfraCodegenScaffolder",),
            ".codegen.version_file": ("FlextInfraCodegenVersionFile",),
            ".codemod": ("codemod",),
            ".codemod.apply_renames": ("FlextInfraApplyRenames",),
            ".codemod.ast_scan": ("FlextInfraCodemodAstScan",),
            ".codemod.batch_apply": ("FlextInfraCodemodBatchApply",),
            ".codemod.batch_gates": ("FlextInfraModGateEngine",),
            ".codemod.batch_replacements": ("FlextInfraModReplacements",),
            ".codemod.sed_apply": ("FlextInfraCodemodSedApply",),
            ".codemod.semantic_apply": ("FlextInfraCodemodSemanticApply",),
            ".codemod.snapshot_reconciler": ("FlextInfraCodemodSnapshotReconciler",),
            ".codemod.snapshot_refresh": ("FlextInfraCodemodSnapshotRefresh",),
            ".codemod.text_gates": ("FlextInfraModTextGateEngine",),
            ".constants": ("FlextInfraConstants", "c"),
            ".deps": ("deps",),
            ".deps.detection": ("FlextInfraDependencyDetectionService",),
            ".deps.detection_analysis": ("FlextInfraDependencyDetectionAnalysis",),
            ".deps.detector": ("FlextInfraRuntimeDevDependencyDetector",),
            ".deps.detector_runtime": ("FlextInfraDependencyDetectorRuntime",),
            ".deps.extra_paths": ("FlextInfraExtraPathsManager",),
            ".deps.fix_pyrefly_config": ("FlextInfraConfigFixer",),
            ".deps.lock_integrity": ("FlextInfraLockIntegrityVerifier",),
            ".deps.modernizer": ("FlextInfraPyprojectModernizer",),
            ".deps.phases.consolidate_groups": ("FlextInfraConsolidateGroupsPhase",),
            ".deps.phases.ensure_packaging": ("FlextInfraEnsurePackagingPhase",),
            ".deps.phases.ensure_pyrefly": ("FlextInfraEnsurePyreflyConfigPhase",),
            ".deps.phases.ensure_pyright": ("FlextInfraEnsurePyrightConfigPhase",),
            ".deps.phases.ensure_ruff": ("FlextInfraEnsureRuffConfigPhase",),
            ".deps.phases.inject_comments": ("FlextInfraInjectCommentsPhase",),
            ".deps.phases.tool_tables": ("FlextInfraToolTablesPhase",),
            ".detectors": ("detectors",),
            ".detectors.class_placement_detector": (
                "FlextInfraClassPlacementDetector",
            ),
            ".detectors.compatibility_alias_detector": (
                "FlextInfraCompatibilityAliasDetector",
            ),
            ".detectors.cyclic_import_detector": ("FlextInfraCyclicImportDetector",),
            ".detectors.deferred_self_reference_detector": (
                "FlextInfraDeferredSelfReferenceDetector",
            ),
            ".detectors.import_alias_detector": ("FlextInfraImportAliasDetector",),
            ".detectors.internal_import_detector": (
                "FlextInfraInternalImportDetector",
            ),
            ".detectors.loose_object_detector": ("FlextInfraLooseObjectDetector",),
            ".detectors.lsp_diagnostics": ("FlextInfraLspDiagnosticsDetector",),
            ".detectors.namespace_source_detector": (
                "FlextInfraNamespaceSourceDetector",
            ),
            ".detectors.private_import_bypass_detector": (
                "FlextInfraPrivateImportBypassDetector",
            ),
            ".detectors.runtime_alias_detector": ("FlextInfraRuntimeAliasDetector",),
            ".docs": ("docs",),
            ".docs.auditor": ("FlextInfraDocAuditor",),
            ".docs.auditor_mixin": ("FlextInfraDocAuditorMixin",),
            ".docs.base": ("FlextInfraDocServiceBase",),
            ".docs.builder": ("FlextInfraDocBuilder",),
            ".docs.collector": ("FlextInfraDocCollector",),
            ".docs.fixer": ("FlextInfraDocFixer",),
            ".docs.formatter": ("FlextInfraDocFormatter",),
            ".docs.generator": ("FlextInfraDocGenerator",),
            ".docs.server": ("FlextInfraDocServer",),
            ".docs.validator": ("FlextInfraDocValidator",),
            ".gates": ("gates",),
            ".gates.bandit": ("FlextInfraBanditGate",),
            ".gates.base_gate": ("FlextInfraGate",),
            ".gates.canonical_alias": ("FlextInfraCanonicalAliasGate",),
            ".gates.deferred_self_reference": ("FlextInfraDeferredSelfReferenceGate",),
            ".gates.direnv": ("FlextInfraDirenvGate",),
            ".gates.duplication": ("FlextInfraDuplicationGate",),
            ".gates.index_declarations": ("FlextInfraIndexDeclarationsGate",),
            ".gates.layout": ("FlextInfraLayoutGate",),
            ".gates.loc_cap": ("FlextInfraLocCapGate",),
            ".gates.markdown": ("FlextInfraMarkdownGate",),
            ".gates.markdown_code": ("FlextInfraMarkdownCodeGate",),
            ".gates.markdown_code_sources": (
                "is_syntax_broken",
                "source_name",
                "write_docstring_sources",
                "write_fenced_block_sources",
            ),
            ".gates.markdown_format": ("FlextInfraMarkdownFormatGate",),
            ".gates.markdown_support": (
                "FlextInfraMarkdownGateBase",
                "collect_markdown_files",
                "read_ignore_patterns",
            ),
            ".gates.mypy": ("FlextInfraMypyGate",),
            ".gates.namespace": ("FlextInfraNamespaceGate",),
            ".gates.pyrefly": ("FlextInfraPyreflyGate",),
            ".gates.pyright": ("FlextInfraPyrightGate",),
            ".gates.ruff_format": ("FlextInfraRuffFormatGate",),
            ".gates.ruff_lint": ("FlextInfraRuffLintGate",),
            ".gates.runtime_census": ("FlextInfraRuntimeCensusGate",),
            ".gates.scanner_gate": ("FlextInfraScannerGateMixin",),
            ".gates.smells": ("FlextInfraSmellsGate",),
            ".git": ("FlextInfraGitService",),
            ".maintenance": ("maintenance",),
            ".maintenance.clean": ("FlextInfraCleanService",),
            ".maintenance.python_version": ("FlextInfraPythonVersionEnforcer",),
            ".maintenance.sonarcloud": ("FlextInfraSonarcloudSettingsSync",),
            ".models": ("FlextInfraModels", "m"),
            ".promoted": ("FlextInfraPromoted",),
            ".protocols": ("FlextInfraProtocols", "FlextInfraProtocolsBase", "p"),
            ".refactor": ("refactor",),
            ".refactor.accessor_migration": (
                "FlextInfraAccessorMigrationOrchestrator",
            ),
            ".refactor.census": ("FlextInfraRefactorCensus",),
            ".refactor.classvar_constant_autofix": (
                "FlextInfraRefactorClassvarConstantAutofix",
            ),
            ".refactor.namespace_enforcer": ("FlextInfraNamespaceEnforcer",),
            ".refactor.namespace_enforcer_phases": (
                "FlextInfraNamespaceEnforcerPhasesMixin",
            ),
            ".refactor.project_alias_migrator": (
                "FlextInfraRefactorProjectAliasMigrator",
            ),
            ".refactor.project_classifier": ("FlextInfraProjectClassifier",),
            ".refactor.wrapper_root_namespace": (
                "FlextInfraWrapperRootNamespaceRefactor",
            ),
            ".release": ("release",),
            ".release.orchestrator": ("FlextInfraReleaseOrchestrator",),
            ".services": ("services",),
            ".services.candidate_bootstrap": ("FlextInfraCandidateBootstrapService",),
            ".services.cli_dispatch": ("FlextInfraCliDispatchService",),
            ".services.cli_route_base": ("FlextInfraCliRouteBase",),
            ".services.cli_routes": ("FlextInfraCliRouteService",),
            ".services.cli_routes_codegen": ("FlextInfraCodegenRoutes",),
            ".services.cli_routes_refactor": ("FlextInfraRefactorRoutes",),
            ".services.cli_routes_validate": ("FlextInfraValidationRoutes",),
            ".services.cli_routes_validate_commands": (
                "FlextInfraValidationCommandRoutes",
            ),
            ".services.cli_routes_workspace": ("FlextInfraWorkspaceRoutes",),
            ".services.codegen": ("FlextInfraCodegen",),
            ".transformers": ("transformers",),
            ".transformers.rope_transformer": ("FlextInfraRopeTransformer",),
            ".typings": ("FlextInfraTypes", "t"),
            ".utilities": ("FlextInfraUtilities", "u"),
            ".validate": ("validate",),
            ".validate.cprofile_report": ("FlextInfraCProfileReport",),
            ".validate.fresh_import": ("FlextInfraValidateFreshImport",),
            ".validate.import_cycles": ("FlextInfraValidateImportCycles",),
            ".validate.inventory": ("FlextInfraInventoryService",),
            ".validate.lazy_map_freshness": ("FlextInfraValidateLazyMapFreshness",),
            ".validate.loc_delta": ("FlextInfraLocDeltaValidator",),
            ".validate.manual_command": ("FlextInfraManualCommandValidator",),
            ".validate.namespace_rules": ("FlextInfraNamespaceRules",),
            ".validate.namespace_validator": ("FlextInfraNamespaceValidator",),
            ".validate.pytest_diag": ("FlextInfraPytestDiagExtractor",),
            ".validate.pytest_runner": ("FlextInfraPytestRunner",),
            ".validate.runtime_census": ("FlextInfraRuntimeCensusValidator",),
            ".validate.scanner": ("FlextInfraTextPatternScanner",),
            ".validate.skill_validator": ("FlextInfraSkillValidator",),
            ".validate.stub_chain": ("FlextInfraStubSupplyChain",),
            ".validate.testmon_db": ("FlextInfraTestmonDbInspector",),
            ".workspace": ("workspace",),
            ".workspace.detector": ("FlextInfraWorkspaceDetector",),
            ".workspace.environment": ("FlextInfraWorkspaceEnvironmentMixin",),
            ".workspace.environment_contracts": (
                "FlextInfraWorkspaceEnvironmentContracts",
            ),
            ".workspace.environment_provenance": (
                "FlextInfraWorkspaceEnvironmentProvenance",
            ),
            ".workspace.flext_binding": ("FlextInfraFlextBindingService",),
            ".workspace.propagation": ("FlextInfraWorkspacePropagation",),
            ".workspace.rope": ("FlextInfraRopeWorkspace",),
            ".worktree": ("FlextInfraWorktreeService",),
            "flext_cli": ("d", "e", "h", "r", "x"),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
