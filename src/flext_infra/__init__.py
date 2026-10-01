# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports
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
            ".cli": ("FlextInfraCli", "main"),
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
                "FlextInfraMisePublication",
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
            ".gates.direnv": ("FlextInfraDirenvGate",),
            ".gates.duplication": ("FlextInfraDuplicationGate",),
            ".gates.index_declarations": ("FlextInfraIndexDeclarationsGate",),
            ".gates.layout": ("FlextInfraLayoutGate",),
            ".gates.loc_cap": ("FlextInfraLocCapGate",),
            ".gates.markdown": ("FlextInfraMarkdownGate",),
            ".gates.markdown_code": ("FlextInfraMarkdownCodeGate",),
            ".gates.markdown_code_sources": ("FlextInfraMarkdownCodeSources",),
            ".gates.markdown_format": ("FlextInfraMarkdownFormatGate",),
            ".gates.markdown_support": ("FlextInfraMarkdownGateBase",),
            ".gates.mypy": ("FlextInfraMypyGate",),
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
            ".refactor.namespace_enforcer": ("FlextInfraNamespaceEnforcer",),
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
            ".validate.inventory": ("FlextInfraInventoryService",),
            ".validate.lazy_map_freshness": ("FlextInfraValidateLazyMapFreshness",),
            ".validate.loc_delta": ("FlextInfraLocDeltaValidator",),
            ".validate.manual_command": ("FlextInfraManualCommandValidator",),
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
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
