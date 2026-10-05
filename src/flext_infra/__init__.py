# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports
from flext_infra.__version__ import (
    __author__,
    __author_email__,
    __description__,
    __license__,
    __title__,
    __url__,
    __version__,
    __version_info__,
)

if TYPE_CHECKING:
    from flext_cli import d, e, h, r, x

    from flext_infra import (
        check,
        codegen,
        codemod,
        deps,
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
    from flext_infra._config import FlextInfraConfig, config
    from flext_infra._settings import FlextInfraSettings, settings
    from flext_infra.api import FlextInfra, infra
    from flext_infra.base import FlextInfraServiceBase, s
    from flext_infra.base_selection import FlextInfraProjectSelectionServiceBase
    from flext_infra.check.gate_registry import FlextInfraGateRegistry
    from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker
    from flext_infra.check.workspace_check_gates import (
        FlextInfraWorkspaceCheckGatesMixin,
    )
    from flext_infra.cli import FlextInfraCli, main
    from flext_infra.codegen.census import FlextInfraCodegenCensus
    from flext_infra.codegen.codegen_generation import FlextInfraCodegenGeneration
    from flext_infra.codegen.codegen_transaction import FlextInfraCodegenTransaction
    from flext_infra.codegen.conform import FlextInfraCodegenConform
    from flext_infra.codegen.consolidator import FlextInfraCodegenConsolidator
    from flext_infra.codegen.constants_quality_gate import FlextInfraCodegenQualityGate
    from flext_infra.codegen.file_leases import FlextInfraCodegenFileLeases
    from flext_infra.codegen.fixer import FlextInfraCodegenFixer
    from flext_infra.codegen.layout import FlextInfraCodegenLayout
    from flext_infra.codegen.lazy_init import FlextInfraCodegenLazyInit
    from flext_infra.codegen.lazy_init_planner import FlextInfraCodegenLazyInitPlanner
    from flext_infra.codegen.make_bootstrap import FlextInfraCodegenMakeBootstrap
    from flext_infra.codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts
    from flext_infra.codegen.mise_artifacts_workspace import (
        FlextInfraMiseWorkspacePlanner,
    )
    from flext_infra.codegen.pipeline import (
        FlextInfraCodegenLazyInitGenerationMixin,
        FlextInfraCodegenPipeline,
        FlextInfraCodegenPipelineStagesMixin,
        FlextInfraMiseArtifactsFiles,
        FlextInfraMisePublication,
    )
    from flext_infra.codegen.project_new import FlextInfraCodegenProjectNew
    from flext_infra.codegen.protocol_models import FlextInfraCodegenProtocolModels
    from flext_infra.codegen.py_typed import FlextInfraCodegenPyTyped
    from flext_infra.codegen.scaffolder import FlextInfraCodegenScaffolder
    from flext_infra.codegen.version_file import FlextInfraCodegenVersionFile
    from flext_infra.codemod.apply_renames import FlextInfraApplyRenames
    from flext_infra.codemod.ast_scan import FlextInfraCodemodAstScan
    from flext_infra.codemod.batch_apply import FlextInfraCodemodBatchApply
    from flext_infra.codemod.batch_gates import FlextInfraModGateEngine
    from flext_infra.codemod.batch_replacements import FlextInfraModReplacements
    from flext_infra.codemod.semantic_apply import FlextInfraCodemodSemanticApply
    from flext_infra.codemod.snapshot_reconciler import (
        FlextInfraCodemodSnapshotReconciler,
    )
    from flext_infra.codemod.snapshot_refresh import FlextInfraCodemodSnapshotRefresh
    from flext_infra.codemod.text_gates import FlextInfraModTextGateEngine
    from flext_infra.constants import FlextInfraConstants, c
    from flext_infra.deps.detection import FlextInfraDependencyDetectionService
    from flext_infra.deps.detection_analysis import (
        FlextInfraDependencyDetectionAnalysis,
    )
    from flext_infra.deps.detector import FlextInfraRuntimeDevDependencyDetector
    from flext_infra.deps.detector_runtime import FlextInfraDependencyDetectorRuntime
    from flext_infra.deps.extra_paths import FlextInfraExtraPathsManager
    from flext_infra.deps.fix_pyrefly_config import FlextInfraConfigFixer
    from flext_infra.deps.lock_integrity import FlextInfraLockIntegrityVerifier
    from flext_infra.deps.modernizer import FlextInfraPyprojectModernizer
    from flext_infra.deps.phases.consolidate_groups import (
        FlextInfraConsolidateGroupsPhase,
    )
    from flext_infra.deps.phases.ensure_packaging import FlextInfraEnsurePackagingPhase
    from flext_infra.deps.phases.ensure_pyrefly import (
        FlextInfraEnsurePyreflyConfigPhase,
    )
    from flext_infra.deps.phases.ensure_pyright import (
        FlextInfraEnsurePyrightConfigPhase,
    )
    from flext_infra.deps.phases.ensure_ruff import FlextInfraEnsureRuffConfigPhase
    from flext_infra.deps.phases.inject_comments import FlextInfraInjectCommentsPhase
    from flext_infra.deps.phases.tool_tables import FlextInfraToolTablesPhase
    from flext_infra.docs.auditor import FlextInfraDocAuditor
    from flext_infra.docs.auditor_mixin import FlextInfraDocAuditorMixin
    from flext_infra.docs.base import FlextInfraDocServiceBase
    from flext_infra.docs.builder import FlextInfraDocBuilder
    from flext_infra.docs.collector import FlextInfraDocCollector
    from flext_infra.docs.fixer import FlextInfraDocFixer
    from flext_infra.docs.formatter import FlextInfraDocFormatter
    from flext_infra.docs.generator import FlextInfraDocGenerator
    from flext_infra.docs.server import FlextInfraDocServer
    from flext_infra.docs.validator import FlextInfraDocValidator
    from flext_infra.gates.bandit import FlextInfraBanditGate
    from flext_infra.gates.base_gate import FlextInfraGate
    from flext_infra.gates.direnv import FlextInfraDirenvGate
    from flext_infra.gates.duplication import FlextInfraDuplicationGate
    from flext_infra.gates.fresh_import import FlextInfraFreshImportGate
    from flext_infra.gates.index_declarations import FlextInfraIndexDeclarationsGate
    from flext_infra.gates.layout import FlextInfraLayoutGate
    from flext_infra.gates.loc_cap import FlextInfraLocCapGate
    from flext_infra.gates.markdown import FlextInfraMarkdownGate
    from flext_infra.gates.markdown_code import FlextInfraMarkdownCodeGate
    from flext_infra.gates.markdown_code_sources import FlextInfraMarkdownCodeSources
    from flext_infra.gates.markdown_format import FlextInfraMarkdownFormatGate
    from flext_infra.gates.markdown_support import FlextInfraMarkdownGateBase
    from flext_infra.gates.mypy import FlextInfraMypyGate
    from flext_infra.gates.pyrefly import FlextInfraPyreflyGate
    from flext_infra.gates.pyright import FlextInfraPyrightGate
    from flext_infra.gates.ruff_format import FlextInfraRuffFormatGate
    from flext_infra.gates.ruff_lint import FlextInfraRuffLintGate
    from flext_infra.gates.runtime_census import FlextInfraRuntimeCensusGate
    from flext_infra.gates.scanner_gate import FlextInfraScannerGateMixin
    from flext_infra.gates.smells import FlextInfraSmellsGate
    from flext_infra.git import FlextInfraGitService
    from flext_infra.maintenance.clean import FlextInfraCleanService
    from flext_infra.maintenance.python_version import FlextInfraPythonVersionEnforcer
    from flext_infra.maintenance.sonarcloud import FlextInfraSonarcloudSettingsSync
    from flext_infra.maintenance.sonarcloud_client import FlextInfraSonarcloudClient
    from flext_infra.maintenance.sonarcloud_issues import FlextInfraSonarcloudIssues
    from flext_infra.models import FlextInfraModels, m
    from flext_infra.promoted import FlextInfraPromoted
    from flext_infra.protocols import FlextInfraProtocols, FlextInfraProtocolsBase, p
    from flext_infra.refactor.accessor_migration import (
        FlextInfraAccessorMigrationOrchestrator,
    )
    from flext_infra.refactor.census import FlextInfraRefactorCensus
    from flext_infra.refactor.namespace_enforcer import FlextInfraNamespaceEnforcer
    from flext_infra.refactor.project_classifier import FlextInfraProjectClassifier
    from flext_infra.refactor.wrapper_root_namespace import (
        FlextInfraWrapperRootNamespaceRefactor,
    )
    from flext_infra.release.orchestrator import FlextInfraReleaseOrchestrator
    from flext_infra.services.candidate_bootstrap import (
        FlextInfraCandidateBootstrapService,
    )
    from flext_infra.services.cli_dispatch import FlextInfraCliDispatchService
    from flext_infra.services.cli_mod_progress import FlextInfraCliModProgress
    from flext_infra.services.cli_route_base import FlextInfraCliRouteBase
    from flext_infra.services.cli_routes import FlextInfraCliRouteService
    from flext_infra.services.cli_routes_codegen import FlextInfraCodegenRoutes
    from flext_infra.services.cli_routes_refactor import FlextInfraRefactorRoutes
    from flext_infra.services.cli_routes_validate import FlextInfraValidationRoutes
    from flext_infra.services.cli_routes_validate_commands import (
        FlextInfraValidationCommandRoutes,
    )
    from flext_infra.services.cli_routes_workspace import FlextInfraWorkspaceRoutes
    from flext_infra.services.codegen import FlextInfraCodegen
    from flext_infra.transformers.rope_transformer import FlextInfraRopeTransformer
    from flext_infra.typings import FlextInfraTypes, t
    from flext_infra.utilities import FlextInfraUtilities, u
    from flext_infra.validate.cprofile_report import FlextInfraCProfileReport
    from flext_infra.validate.fresh_import import FlextInfraValidateFreshImport
    from flext_infra.validate.inventory import FlextInfraInventoryService
    from flext_infra.validate.lazy_map_freshness import (
        FlextInfraValidateLazyMapFreshness,
    )
    from flext_infra.validate.loc_delta import FlextInfraLocDeltaValidator
    from flext_infra.validate.manual_command import FlextInfraManualCommandValidator
    from flext_infra.validate.namespace_validator import FlextInfraNamespaceValidator
    from flext_infra.validate.pytest_diag import FlextInfraPytestDiagExtractor
    from flext_infra.validate.pytest_runner import FlextInfraPytestRunner
    from flext_infra.validate.runtime_census import FlextInfraRuntimeCensusValidator
    from flext_infra.validate.scanner import FlextInfraTextPatternScanner
    from flext_infra.validate.skill_validator import FlextInfraSkillValidator
    from flext_infra.validate.stub_chain import FlextInfraStubSupplyChain
    from flext_infra.validate.testmon_db import FlextInfraTestmonDbInspector
    from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
    from flext_infra.workspace.environment import FlextInfraWorkspaceEnvironmentMixin
    from flext_infra.workspace.environment_contracts import (
        FlextInfraWorkspaceEnvironmentContracts,
    )
    from flext_infra.workspace.environment_provenance import (
        FlextInfraWorkspaceEnvironmentProvenance,
    )
    from flext_infra.workspace.flext_binding import FlextInfraFlextBindingService
    from flext_infra.workspace.propagation import FlextInfraWorkspacePropagation
    from flext_infra.workspace.rope import FlextInfraRopeWorkspace
    from flext_infra.worktree import FlextInfraWorktreeService


__all__: tuple[str, ...] = (
    "FlextInfra",
    "FlextInfraAccessorMigrationOrchestrator",
    "FlextInfraApplyRenames",
    "FlextInfraBanditGate",
    "FlextInfraCProfileReport",
    "FlextInfraCandidateBootstrapService",
    "FlextInfraCleanService",
    "FlextInfraCli",
    "FlextInfraCliDispatchService",
    "FlextInfraCliModProgress",
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
    "FlextInfraCodemodSemanticApply",
    "FlextInfraCodemodSnapshotReconciler",
    "FlextInfraCodemodSnapshotRefresh",
    "FlextInfraConfig",
    "FlextInfraConfigFixer",
    "FlextInfraConsolidateGroupsPhase",
    "FlextInfraConstants",
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
    "FlextInfraFreshImportGate",
    "FlextInfraGate",
    "FlextInfraGateRegistry",
    "FlextInfraGitService",
    "FlextInfraIndexDeclarationsGate",
    "FlextInfraInjectCommentsPhase",
    "FlextInfraInventoryService",
    "FlextInfraLayoutGate",
    "FlextInfraLocCapGate",
    "FlextInfraLocDeltaValidator",
    "FlextInfraLockIntegrityVerifier",
    "FlextInfraManualCommandValidator",
    "FlextInfraMarkdownCodeGate",
    "FlextInfraMarkdownCodeSources",
    "FlextInfraMarkdownFormatGate",
    "FlextInfraMarkdownGate",
    "FlextInfraMarkdownGateBase",
    "FlextInfraMiseArtifactsFiles",
    "FlextInfraMisePublication",
    "FlextInfraMiseWorkspacePlanner",
    "FlextInfraModGateEngine",
    "FlextInfraModReplacements",
    "FlextInfraModTextGateEngine",
    "FlextInfraModels",
    "FlextInfraMypyGate",
    "FlextInfraNamespaceEnforcer",
    "FlextInfraNamespaceValidator",
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
    "FlextInfraRefactorRoutes",
    "FlextInfraReleaseOrchestrator",
    "FlextInfraRopeTransformer",
    "FlextInfraRopeWorkspace",
    "FlextInfraRuffFormatGate",
    "FlextInfraRuffLintGate",
    "FlextInfraRuntimeCensusGate",
    "FlextInfraRuntimeCensusValidator",
    "FlextInfraRuntimeDevDependencyDetector",
    "FlextInfraScannerGateMixin",
    "FlextInfraServiceBase",
    "FlextInfraSettings",
    "FlextInfraSkillValidator",
    "FlextInfraSmellsGate",
    "FlextInfraSonarcloudClient",
    "FlextInfraSonarcloudIssues",
    "FlextInfraSonarcloudSettingsSync",
    "FlextInfraStubSupplyChain",
    "FlextInfraTestmonDbInspector",
    "FlextInfraTextPatternScanner",
    "FlextInfraToolTablesPhase",
    "FlextInfraTypes",
    "FlextInfraUtilities",
    "FlextInfraValidateFreshImport",
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
    "config",
    "d",
    "deps",
    "docs",
    "e",
    "gates",
    "h",
    "infra",
    "m",
    "main",
    "maintenance",
    "p",
    "r",
    "refactor",
    "release",
    "s",
    "services",
    "settings",
    "t",
    "transformers",
    "u",
    "validate",
    "workspace",
    "x",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfra": ".api",
        "FlextInfraAccessorMigrationOrchestrator": ".refactor.accessor_migration",
        "FlextInfraApplyRenames": ".codemod.apply_renames",
        "FlextInfraBanditGate": ".gates.bandit",
        "FlextInfraCProfileReport": ".validate.cprofile_report",
        "FlextInfraCandidateBootstrapService": ".services.candidate_bootstrap",
        "FlextInfraCleanService": ".maintenance.clean",
        "FlextInfraCli": ".cli",
        "FlextInfraCliDispatchService": ".services.cli_dispatch",
        "FlextInfraCliModProgress": ".services.cli_mod_progress",
        "FlextInfraCliRouteBase": ".services.cli_route_base",
        "FlextInfraCliRouteService": ".services.cli_routes",
        "FlextInfraCodegen": ".services.codegen",
        "FlextInfraCodegenCensus": ".codegen.census",
        "FlextInfraCodegenConform": ".codegen.conform",
        "FlextInfraCodegenConsolidator": ".codegen.consolidator",
        "FlextInfraCodegenFileLeases": ".codegen.file_leases",
        "FlextInfraCodegenFixer": ".codegen.fixer",
        "FlextInfraCodegenGeneration": ".codegen.codegen_generation",
        "FlextInfraCodegenLayout": ".codegen.layout",
        "FlextInfraCodegenLazyInit": ".codegen.lazy_init",
        "FlextInfraCodegenLazyInitGenerationMixin": ".codegen.pipeline",
        "FlextInfraCodegenLazyInitPlanner": ".codegen.lazy_init_planner",
        "FlextInfraCodegenMakeBootstrap": ".codegen.make_bootstrap",
        "FlextInfraCodegenMiseArtifacts": ".codegen.mise_artifacts",
        "FlextInfraCodegenPipeline": ".codegen.pipeline",
        "FlextInfraCodegenPipelineStagesMixin": ".codegen.pipeline",
        "FlextInfraCodegenProjectNew": ".codegen.project_new",
        "FlextInfraCodegenProtocolModels": ".codegen.protocol_models",
        "FlextInfraCodegenPyTyped": ".codegen.py_typed",
        "FlextInfraCodegenQualityGate": ".codegen.constants_quality_gate",
        "FlextInfraCodegenRoutes": ".services.cli_routes_codegen",
        "FlextInfraCodegenScaffolder": ".codegen.scaffolder",
        "FlextInfraCodegenTransaction": ".codegen.codegen_transaction",
        "FlextInfraCodegenVersionFile": ".codegen.version_file",
        "FlextInfraCodemodAstScan": ".codemod.ast_scan",
        "FlextInfraCodemodBatchApply": ".codemod.batch_apply",
        "FlextInfraCodemodSemanticApply": ".codemod.semantic_apply",
        "FlextInfraCodemodSnapshotReconciler": ".codemod.snapshot_reconciler",
        "FlextInfraCodemodSnapshotRefresh": ".codemod.snapshot_refresh",
        "FlextInfraConfig": "._config",
        "FlextInfraConfigFixer": ".deps.fix_pyrefly_config",
        "FlextInfraConsolidateGroupsPhase": ".deps.phases.consolidate_groups",
        "FlextInfraConstants": ".constants",
        "FlextInfraDependencyDetectionAnalysis": ".deps.detection_analysis",
        "FlextInfraDependencyDetectionService": ".deps.detection",
        "FlextInfraDependencyDetectorRuntime": ".deps.detector_runtime",
        "FlextInfraDirenvGate": ".gates.direnv",
        "FlextInfraDocAuditor": ".docs.auditor",
        "FlextInfraDocAuditorMixin": ".docs.auditor_mixin",
        "FlextInfraDocBuilder": ".docs.builder",
        "FlextInfraDocCollector": ".docs.collector",
        "FlextInfraDocFixer": ".docs.fixer",
        "FlextInfraDocFormatter": ".docs.formatter",
        "FlextInfraDocGenerator": ".docs.generator",
        "FlextInfraDocServer": ".docs.server",
        "FlextInfraDocServiceBase": ".docs.base",
        "FlextInfraDocValidator": ".docs.validator",
        "FlextInfraDuplicationGate": ".gates.duplication",
        "FlextInfraEnsurePackagingPhase": ".deps.phases.ensure_packaging",
        "FlextInfraEnsurePyreflyConfigPhase": ".deps.phases.ensure_pyrefly",
        "FlextInfraEnsurePyrightConfigPhase": ".deps.phases.ensure_pyright",
        "FlextInfraEnsureRuffConfigPhase": ".deps.phases.ensure_ruff",
        "FlextInfraExtraPathsManager": ".deps.extra_paths",
        "FlextInfraFlextBindingService": ".workspace.flext_binding",
        "FlextInfraFreshImportGate": ".gates.fresh_import",
        "FlextInfraGate": ".gates.base_gate",
        "FlextInfraGateRegistry": ".check.gate_registry",
        "FlextInfraGitService": ".git",
        "FlextInfraIndexDeclarationsGate": ".gates.index_declarations",
        "FlextInfraInjectCommentsPhase": ".deps.phases.inject_comments",
        "FlextInfraInventoryService": ".validate.inventory",
        "FlextInfraLayoutGate": ".gates.layout",
        "FlextInfraLocCapGate": ".gates.loc_cap",
        "FlextInfraLocDeltaValidator": ".validate.loc_delta",
        "FlextInfraLockIntegrityVerifier": ".deps.lock_integrity",
        "FlextInfraManualCommandValidator": ".validate.manual_command",
        "FlextInfraMarkdownCodeGate": ".gates.markdown_code",
        "FlextInfraMarkdownCodeSources": ".gates.markdown_code_sources",
        "FlextInfraMarkdownFormatGate": ".gates.markdown_format",
        "FlextInfraMarkdownGate": ".gates.markdown",
        "FlextInfraMarkdownGateBase": ".gates.markdown_support",
        "FlextInfraMiseArtifactsFiles": ".codegen.pipeline",
        "FlextInfraMisePublication": ".codegen.pipeline",
        "FlextInfraMiseWorkspacePlanner": ".codegen.mise_artifacts_workspace",
        "FlextInfraModGateEngine": ".codemod.batch_gates",
        "FlextInfraModReplacements": ".codemod.batch_replacements",
        "FlextInfraModTextGateEngine": ".codemod.text_gates",
        "FlextInfraModels": ".models",
        "FlextInfraMypyGate": ".gates.mypy",
        "FlextInfraNamespaceEnforcer": ".refactor.namespace_enforcer",
        "FlextInfraNamespaceValidator": ".validate.namespace_validator",
        "FlextInfraProjectClassifier": ".refactor.project_classifier",
        "FlextInfraProjectSelectionServiceBase": ".base_selection",
        "FlextInfraPromoted": ".promoted",
        "FlextInfraProtocols": ".protocols",
        "FlextInfraProtocolsBase": ".protocols",
        "FlextInfraPyprojectModernizer": ".deps.modernizer",
        "FlextInfraPyreflyGate": ".gates.pyrefly",
        "FlextInfraPyrightGate": ".gates.pyright",
        "FlextInfraPytestDiagExtractor": ".validate.pytest_diag",
        "FlextInfraPytestRunner": ".validate.pytest_runner",
        "FlextInfraPythonVersionEnforcer": ".maintenance.python_version",
        "FlextInfraRefactorCensus": ".refactor.census",
        "FlextInfraRefactorRoutes": ".services.cli_routes_refactor",
        "FlextInfraReleaseOrchestrator": ".release.orchestrator",
        "FlextInfraRopeTransformer": ".transformers.rope_transformer",
        "FlextInfraRopeWorkspace": ".workspace.rope",
        "FlextInfraRuffFormatGate": ".gates.ruff_format",
        "FlextInfraRuffLintGate": ".gates.ruff_lint",
        "FlextInfraRuntimeCensusGate": ".gates.runtime_census",
        "FlextInfraRuntimeCensusValidator": ".validate.runtime_census",
        "FlextInfraRuntimeDevDependencyDetector": ".deps.detector",
        "FlextInfraScannerGateMixin": ".gates.scanner_gate",
        "FlextInfraServiceBase": ".base",
        "FlextInfraSettings": "._settings",
        "FlextInfraSkillValidator": ".validate.skill_validator",
        "FlextInfraSmellsGate": ".gates.smells",
        "FlextInfraSonarcloudClient": ".maintenance.sonarcloud_client",
        "FlextInfraSonarcloudIssues": ".maintenance.sonarcloud_issues",
        "FlextInfraSonarcloudSettingsSync": ".maintenance.sonarcloud",
        "FlextInfraStubSupplyChain": ".validate.stub_chain",
        "FlextInfraTestmonDbInspector": ".validate.testmon_db",
        "FlextInfraTextPatternScanner": ".validate.scanner",
        "FlextInfraToolTablesPhase": ".deps.phases.tool_tables",
        "FlextInfraTypes": ".typings",
        "FlextInfraUtilities": ".utilities",
        "FlextInfraValidateFreshImport": ".validate.fresh_import",
        "FlextInfraValidateLazyMapFreshness": ".validate.lazy_map_freshness",
        "FlextInfraValidationCommandRoutes": ".services.cli_routes_validate_commands",
        "FlextInfraValidationRoutes": ".services.cli_routes_validate",
        "FlextInfraWorkspaceCheckGatesMixin": ".check.workspace_check_gates",
        "FlextInfraWorkspaceChecker": ".check.workspace_check",
        "FlextInfraWorkspaceDetector": ".workspace.detector",
        "FlextInfraWorkspaceEnvironmentContracts": ".workspace.environment_contracts",
        "FlextInfraWorkspaceEnvironmentMixin": ".workspace.environment",
        "FlextInfraWorkspaceEnvironmentProvenance": ".workspace.environment_provenance",
        "FlextInfraWorkspacePropagation": ".workspace.propagation",
        "FlextInfraWorkspaceRoutes": ".services.cli_routes_workspace",
        "FlextInfraWorktreeService": ".worktree",
        "FlextInfraWrapperRootNamespaceRefactor": ".refactor.wrapper_root_namespace",
        "c": ".constants",
        "check": ".check",
        "codegen": ".codegen",
        "codemod": ".codemod",
        "config": "._config",
        "d": "flext_cli",
        "deps": ".deps",
        "docs": ".docs",
        "e": "flext_cli",
        "gates": ".gates",
        "h": "flext_cli",
        "infra": ".api",
        "m": ".models",
        "main": ".cli",
        "maintenance": ".maintenance",
        "p": ".protocols",
        "r": "flext_cli",
        "refactor": ".refactor",
        "release": ".release",
        "s": ".base",
        "services": ".services",
        "settings": "._settings",
        "t": ".typings",
        "transformers": ".transformers",
        "u": ".utilities",
        "validate": ".validate",
        "workspace": ".workspace",
        "x": "flext_cli",
    }),
    public_exports=__all__,
)
