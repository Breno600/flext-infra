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
        fixers,
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
    from .check.workspace_check import FlextInfraWorkspaceChecker
    from .check.workspace_check_gates import (
        FlextInfraGateRegistry,
        FlextInfraWorkspaceCheckGatesMixin,
    )
    from .cli import FlextInfraCli, docs_main, main
    from .codegen.census import FlextInfraCodegenCensus
    from .codegen.codegen_generation import FlextInfraCodegenGeneration
    from .codegen.codegen_transaction import FlextInfraCodegenTransaction
    from .codegen.conform import FlextInfraCodegenConform
    from .codegen.consolidator import FlextInfraCodegenConsolidator
    from .codegen.constants_quality_gate import FlextInfraCodegenQualityGate
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
    from .codemod.text_gates import FlextInfraModTextGateEngine
    from .constants import FlextInfraConstants, FlextInfraConstants as c
    from .deps.detection import FlextInfraDependencyDetectionService
    from .deps.detection_analysis import FlextInfraDependencyDetectionAnalysis
    from .deps.detector import FlextInfraRuntimeDevDependencyDetector
    from .deps.detector_runtime import FlextInfraDependencyDetectorRuntime
    from .deps.extra_paths import FlextInfraExtraPathsManager
    from .deps.fix_pyrefly_config import FlextInfraConfigFixer
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
    from .detectors.consumer_import_violations_detector import (
        FlextInfraConsumerImportViolationsDetector,
    )
    from .detectors.cyclic_import_detector import FlextInfraCyclicImportDetector
    from .detectors.deferred_self_reference_detector import (
        FlextInfraDeferredSelfReferenceDetector,
    )
    from .detectors.future_annotations_detector import (
        FlextInfraFutureAnnotationsDetector,
    )
    from .detectors.import_alias_detector import FlextInfraImportAliasDetector
    from .detectors.inline_import_detector import FlextInfraInlineImportDetector
    from .detectors.internal_import_detector import FlextInfraInternalImportDetector
    from .detectors.loose_object_detector import FlextInfraLooseObjectDetector
    from .detectors.loose_test_function_detector import (
        FlextInfraLooseTestFunctionDetector,
    )
    from .detectors.lsp_diagnostics import FlextInfraLspDiagnosticsDetector
    from .detectors.manual_protocol_detector import FlextInfraManualProtocolDetector
    from .detectors.manual_typing_alias_detector import (
        FlextInfraManualTypingAliasDetector,
    )
    from .detectors.namespace_source_detector import FlextInfraNamespaceSourceDetector
    from .detectors.private_import_bypass_detector import (
        FlextInfraPrivateImportBypassDetector,
    )
    from .detectors.runtime_alias_detector import FlextInfraRuntimeAliasDetector
    from .detectors.silent_failure_detector import FlextInfraSilentFailureDetector
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
    from .fixers.base import FlextInfraFixerAdapter
    from .fixers.gate_fixer import FlextInfraGateFixerAdapter
    from .fixers.orchestrator import FlextInfraEnforcementFixerOrchestrator
    from .fixers.transformer_fixer import FlextInfraTransformerFixerAdapter
    from .gates.abstraction_boundary import FlextInfraAbstractionBoundaryGate
    from .gates.bandit import FlextInfraBanditGate
    from .gates.base_gate import FlextInfraGate, FlextInfraScannerGateMixin
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
    from .gates.silent_failure import FlextInfraSilentFailureGate
    from .gates.smells import FlextInfraSmellsGate
    from .gates.tier_whitelist import FlextInfraTierWhitelistGate
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
    from .refactor.modernize_orchestrator import FlextInfraModernizeOrchestrator
    from .refactor.namespace_enforcer import FlextInfraNamespaceEnforcer
    from .refactor.namespace_enforcer_phases import (
        FlextInfraNamespaceEnforcerPhasesMixin,
    )
    from .refactor.project_alias_migrator import FlextInfraRefactorProjectAliasMigrator
    from .refactor.project_classifier import FlextInfraProjectClassifier
    from .refactor.signature_propagation import FlextInfraRefactorSignaturePropagation
    from .refactor.wrapper_root_namespace import FlextInfraWrapperRootNamespaceRefactor
    from .release.orchestrator import FlextInfraReleaseOrchestrator
    from .services.cli_dispatch import CliDispatchService
    from .services.cli_route_base import CliRouteBase
    from .services.cli_routes import CliRouteService
    from .services.cli_routes_codegen import CodegenRoutes
    from .services.cli_routes_refactor import RefactorRoutes
    from .services.cli_routes_validate import ValidationRoutes
    from .services.cli_routes_validate_commands import ValidationCommandRoutes
    from .services.cli_routes_workspace import WorkspaceRoutes
    from .services.codegen import FlextInfraCodegen
    from .transformers.class_reconstructor import FlextInfraRefactorClassReconstructor
    from .transformers.compatibility_alias import FlextInfraRefactorCompatibilityAlias
    from .transformers.dataclass_modelizer import FlextInfraRefactorDataclassModelizer
    from .transformers.deprecated_remover import FlextInfraRefactorDeprecatedRemover
    from .transformers.future_import import FlextInfraRefactorFutureImport
    from .transformers.hardcoded_version import FlextInfraRefactorHardcodedVersion
    from .transformers.import_bypass_remover import (
        FlextInfraRefactorImportBypassRemover,
    )
    from .transformers.import_modernizer import FlextInfraRefactorImportModernizer
    from .transformers.lazy_import_fixer import FlextInfraRefactorLazyImportFixer
    from .transformers.mro_remover import FlextInfraRefactorMroRemover
    from .transformers.open_encoding import FlextInfraRefactorOpenEncoding
    from .transformers.pattern import FlextInfraRefactorPatternTransformer
    from .transformers.pydantic_modernizer import FlextInfraRefactorPydanticModernizer
    from .transformers.signature_propagator import FlextInfraRefactorSignaturePropagator
    from .transformers.smells.base import FlextInfraSmellFixer
    from .transformers.smells.boolean_logic import FlextInfraBooleanLogicFixer
    from .transformers.symbol_propagator import FlextInfraRefactorSymbolPropagator
    from .transformers.typing_unifier import FlextInfraRefactorTypingUnifier
    from .typings import FlextInfraTypes, FlextInfraTypes as t
    from .utilities import FlextInfraUtilities, FlextInfraUtilities as u
    from .validate.cprofile_report import FlextInfraCProfileReport
    from .validate.fresh_import import FlextInfraValidateFreshImport
    from .validate.gate_contract import FlextInfraGateContractValidator
    from .validate.gate_contract_checks import FlextInfraGateContractChecksMixin
    from .validate.gate_contract_content import FlextInfraGateContractContentMixin
    from .validate.gate_contract_errors import (
        GateContractInfraError,
        GateContractUsageError,
    )
    from .validate.gate_contract_report import FlextInfraGateContractReportMixin
    from .validate.gate_contract_scan import FlextInfraGateContractScanMixin
    from .validate.import_cycles import FlextInfraValidateImportCycles
    from .validate.inventory import FlextInfraInventoryService
    from .validate.lazy_map_freshness import FlextInfraValidateLazyMapFreshness
    from .validate.loc_delta import FlextInfraLocDeltaValidator
    from .validate.manual_command import FlextInfraManualCommandValidator
    from .validate.metadata_discipline import FlextInfraValidateMetadataDiscipline
    from .validate.namespace_rules import FlextInfraNamespaceRules
    from .validate.namespace_validator import FlextInfraNamespaceValidator
    from .validate.pytest_diag import FlextInfraPytestDiagExtractor
    from .validate.pytest_runner import FlextInfraPytestRunner
    from .validate.runtime_census import FlextInfraRuntimeCensusValidator
    from .validate.scanner import FlextInfraTextPatternScanner
    from .validate.silent_failure import FlextInfraSilentFailureValidator
    from .validate.skill_validator import FlextInfraSkillValidator
    from .validate.stub_chain import FlextInfraStubSupplyChain
    from .validate.testmon_db import FlextInfraTestmonDbInspector
    from .validate.tier_whitelist import FlextInfraValidateTierWhitelist
    from .workspace.detector import FlextInfraWorkspaceDetector
    from .workspace.environment import FlextInfraWorkspaceEnvironmentMixin
    from .workspace.environment_beads import (
        FlextInfraWorkspaceBeadsEnvironmentMixin,
        FlextInfraWorkspaceEnvironmentSync,
    )
    from .workspace.environment_contracts import FlextInfraWorkspaceEnvironmentContracts
    from .workspace.environment_provenance import (
        FlextInfraWorkspaceEnvironmentProvenance,
    )
    from .workspace.flext_binding import FlextInfraFlextBindingService
    from .workspace.orchestrator import FlextInfraOrchestratorService
    from .workspace.propagation import FlextInfraWorkspacePropagation
    from .workspace.rope import FlextInfraRopeWorkspace
    from .worktree import FlextInfraWorktreeService


__all__: tuple[str, ...] = (
    "CliDispatchService",
    "CliRouteBase",
    "CliRouteService",
    "CodegenRoutes",
    "FlextInfra",
    "FlextInfraAbstractionBoundaryGate",
    "FlextInfraAccessorMigrationOrchestrator",
    "FlextInfraApplyRenames",
    "FlextInfraBanditGate",
    "FlextInfraBooleanLogicFixer",
    "FlextInfraCProfileReport",
    "FlextInfraCanonicalAliasGate",
    "FlextInfraClassPlacementDetector",
    "FlextInfraCleanService",
    "FlextInfraCli",
    "FlextInfraCodegen",
    "FlextInfraCodegenCensus",
    "FlextInfraCodegenConform",
    "FlextInfraCodegenConsolidator",
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
    "FlextInfraCodegenScaffolder",
    "FlextInfraCodegenTransaction",
    "FlextInfraCodegenVersionFile",
    "FlextInfraCodemodAstScan",
    "FlextInfraCodemodBatchApply",
    "FlextInfraCodemodSedApply",
    "FlextInfraCodemodSemanticApply",
    "FlextInfraCodemodSnapshotReconciler",
    "FlextInfraCompatibilityAliasDetector",
    "FlextInfraConfig",
    "FlextInfraConfigFixer",
    "FlextInfraConsolidateGroupsPhase",
    "FlextInfraConstants",
    "FlextInfraConsumerImportViolationsDetector",
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
    "FlextInfraEnforcementFixerOrchestrator",
    "FlextInfraEnsurePackagingPhase",
    "FlextInfraEnsurePyreflyConfigPhase",
    "FlextInfraEnsurePyrightConfigPhase",
    "FlextInfraEnsureRuffConfigPhase",
    "FlextInfraExtraPathsManager",
    "FlextInfraFixerAdapter",
    "FlextInfraFlextBindingService",
    "FlextInfraFutureAnnotationsDetector",
    "FlextInfraGate",
    "FlextInfraGateContractChecksMixin",
    "FlextInfraGateContractContentMixin",
    "FlextInfraGateContractReportMixin",
    "FlextInfraGateContractScanMixin",
    "FlextInfraGateContractValidator",
    "FlextInfraGateFixerAdapter",
    "FlextInfraGateRegistry",
    "FlextInfraGitService",
    "FlextInfraImportAliasDetector",
    "FlextInfraIndexDeclarationsGate",
    "FlextInfraInjectCommentsPhase",
    "FlextInfraInlineImportDetector",
    "FlextInfraInternalImportDetector",
    "FlextInfraInventoryService",
    "FlextInfraLayoutGate",
    "FlextInfraLocCapGate",
    "FlextInfraLocDeltaValidator",
    "FlextInfraLooseObjectDetector",
    "FlextInfraLooseTestFunctionDetector",
    "FlextInfraLspDiagnosticsDetector",
    "FlextInfraManualCommandValidator",
    "FlextInfraManualProtocolDetector",
    "FlextInfraManualTypingAliasDetector",
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
    "FlextInfraModernizeOrchestrator",
    "FlextInfraMypyGate",
    "FlextInfraNamespaceEnforcer",
    "FlextInfraNamespaceEnforcerPhasesMixin",
    "FlextInfraNamespaceGate",
    "FlextInfraNamespaceRules",
    "FlextInfraNamespaceSourceDetector",
    "FlextInfraNamespaceValidator",
    "FlextInfraOrchestratorService",
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
    "FlextInfraRefactorClassReconstructor",
    "FlextInfraRefactorClassvarConstantAutofix",
    "FlextInfraRefactorCompatibilityAlias",
    "FlextInfraRefactorDataclassModelizer",
    "FlextInfraRefactorDeprecatedRemover",
    "FlextInfraRefactorFutureImport",
    "FlextInfraRefactorHardcodedVersion",
    "FlextInfraRefactorImportBypassRemover",
    "FlextInfraRefactorImportModernizer",
    "FlextInfraRefactorLazyImportFixer",
    "FlextInfraRefactorMroRemover",
    "FlextInfraRefactorOpenEncoding",
    "FlextInfraRefactorPatternTransformer",
    "FlextInfraRefactorProjectAliasMigrator",
    "FlextInfraRefactorPydanticModernizer",
    "FlextInfraRefactorSignaturePropagation",
    "FlextInfraRefactorSignaturePropagator",
    "FlextInfraRefactorSymbolPropagator",
    "FlextInfraRefactorTypingUnifier",
    "FlextInfraReleaseOrchestrator",
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
    "FlextInfraSilentFailureDetector",
    "FlextInfraSilentFailureGate",
    "FlextInfraSilentFailureValidator",
    "FlextInfraSkillValidator",
    "FlextInfraSmellFixer",
    "FlextInfraSmellsGate",
    "FlextInfraSonarcloudSettingsSync",
    "FlextInfraStubSupplyChain",
    "FlextInfraTestmonDbInspector",
    "FlextInfraTextPatternScanner",
    "FlextInfraTierWhitelistGate",
    "FlextInfraToolTablesPhase",
    "FlextInfraTransformerFixerAdapter",
    "FlextInfraTypes",
    "FlextInfraUtilities",
    "FlextInfraValidateFreshImport",
    "FlextInfraValidateImportCycles",
    "FlextInfraValidateLazyMapFreshness",
    "FlextInfraValidateMetadataDiscipline",
    "FlextInfraValidateTierWhitelist",
    "FlextInfraWorkspaceBeadsEnvironmentMixin",
    "FlextInfraWorkspaceCheckGatesMixin",
    "FlextInfraWorkspaceChecker",
    "FlextInfraWorkspaceDetector",
    "FlextInfraWorkspaceEnvironmentContracts",
    "FlextInfraWorkspaceEnvironmentMixin",
    "FlextInfraWorkspaceEnvironmentProvenance",
    "FlextInfraWorkspaceEnvironmentSync",
    "FlextInfraWorkspacePropagation",
    "FlextInfraWorktreeService",
    "FlextInfraWrapperRootNamespaceRefactor",
    "GateContractInfraError",
    "GateContractUsageError",
    "RefactorRoutes",
    "ValidationCommandRoutes",
    "ValidationRoutes",
    "WorkspaceRoutes",
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
    "fixers",
    "gates",
    "h",
    "infra",
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
            ".check.workspace_check": ("FlextInfraWorkspaceChecker",),
            ".check.workspace_check_gates": (
                "FlextInfraGateRegistry",
                "FlextInfraWorkspaceCheckGatesMixin",
            ),
            ".cli": ("FlextInfraCli", "docs_main", "main"),
            ".codegen": ("codegen",),
            ".codegen.census": ("FlextInfraCodegenCensus",),
            ".codegen.codegen_generation": ("FlextInfraCodegenGeneration",),
            ".codegen.codegen_transaction": ("FlextInfraCodegenTransaction",),
            ".codegen.conform": ("FlextInfraCodegenConform",),
            ".codegen.consolidator": ("FlextInfraCodegenConsolidator",),
            ".codegen.constants_quality_gate": ("FlextInfraCodegenQualityGate",),
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
            ".codemod.text_gates": ("FlextInfraModTextGateEngine",),
            ".constants": ("FlextInfraConstants", "c"),
            ".deps": ("deps",),
            ".deps.detection": ("FlextInfraDependencyDetectionService",),
            ".deps.detection_analysis": ("FlextInfraDependencyDetectionAnalysis",),
            ".deps.detector": ("FlextInfraRuntimeDevDependencyDetector",),
            ".deps.detector_runtime": ("FlextInfraDependencyDetectorRuntime",),
            ".deps.extra_paths": ("FlextInfraExtraPathsManager",),
            ".deps.fix_pyrefly_config": ("FlextInfraConfigFixer",),
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
            ".detectors.consumer_import_violations_detector": (
                "FlextInfraConsumerImportViolationsDetector",
            ),
            ".detectors.cyclic_import_detector": ("FlextInfraCyclicImportDetector",),
            ".detectors.deferred_self_reference_detector": (
                "FlextInfraDeferredSelfReferenceDetector",
            ),
            ".detectors.future_annotations_detector": (
                "FlextInfraFutureAnnotationsDetector",
            ),
            ".detectors.import_alias_detector": ("FlextInfraImportAliasDetector",),
            ".detectors.inline_import_detector": ("FlextInfraInlineImportDetector",),
            ".detectors.internal_import_detector": (
                "FlextInfraInternalImportDetector",
            ),
            ".detectors.loose_object_detector": ("FlextInfraLooseObjectDetector",),
            ".detectors.loose_test_function_detector": (
                "FlextInfraLooseTestFunctionDetector",
            ),
            ".detectors.lsp_diagnostics": ("FlextInfraLspDiagnosticsDetector",),
            ".detectors.manual_protocol_detector": (
                "FlextInfraManualProtocolDetector",
            ),
            ".detectors.manual_typing_alias_detector": (
                "FlextInfraManualTypingAliasDetector",
            ),
            ".detectors.namespace_source_detector": (
                "FlextInfraNamespaceSourceDetector",
            ),
            ".detectors.private_import_bypass_detector": (
                "FlextInfraPrivateImportBypassDetector",
            ),
            ".detectors.runtime_alias_detector": ("FlextInfraRuntimeAliasDetector",),
            ".detectors.silent_failure_detector": ("FlextInfraSilentFailureDetector",),
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
            ".fixers": ("fixers",),
            ".fixers.base": ("FlextInfraFixerAdapter",),
            ".fixers.gate_fixer": ("FlextInfraGateFixerAdapter",),
            ".fixers.orchestrator": ("FlextInfraEnforcementFixerOrchestrator",),
            ".fixers.transformer_fixer": ("FlextInfraTransformerFixerAdapter",),
            ".gates": ("gates",),
            ".gates.abstraction_boundary": ("FlextInfraAbstractionBoundaryGate",),
            ".gates.bandit": ("FlextInfraBanditGate",),
            ".gates.base_gate": ("FlextInfraGate", "FlextInfraScannerGateMixin"),
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
            ".gates.silent_failure": ("FlextInfraSilentFailureGate",),
            ".gates.smells": ("FlextInfraSmellsGate",),
            ".gates.tier_whitelist": ("FlextInfraTierWhitelistGate",),
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
            ".refactor.modernize_orchestrator": ("FlextInfraModernizeOrchestrator",),
            ".refactor.namespace_enforcer": ("FlextInfraNamespaceEnforcer",),
            ".refactor.namespace_enforcer_phases": (
                "FlextInfraNamespaceEnforcerPhasesMixin",
            ),
            ".refactor.project_alias_migrator": (
                "FlextInfraRefactorProjectAliasMigrator",
            ),
            ".refactor.project_classifier": ("FlextInfraProjectClassifier",),
            ".refactor.signature_propagation": (
                "FlextInfraRefactorSignaturePropagation",
            ),
            ".refactor.wrapper_root_namespace": (
                "FlextInfraWrapperRootNamespaceRefactor",
            ),
            ".release": ("release",),
            ".release.orchestrator": ("FlextInfraReleaseOrchestrator",),
            ".services": ("services",),
            ".services.cli_dispatch": ("CliDispatchService",),
            ".services.cli_route_base": ("CliRouteBase",),
            ".services.cli_routes": ("CliRouteService",),
            ".services.cli_routes_codegen": ("CodegenRoutes",),
            ".services.cli_routes_refactor": ("RefactorRoutes",),
            ".services.cli_routes_validate": ("ValidationRoutes",),
            ".services.cli_routes_validate_commands": ("ValidationCommandRoutes",),
            ".services.cli_routes_workspace": ("WorkspaceRoutes",),
            ".services.codegen": ("FlextInfraCodegen",),
            ".transformers": ("transformers",),
            ".transformers.class_reconstructor": (
                "FlextInfraRefactorClassReconstructor",
            ),
            ".transformers.compatibility_alias": (
                "FlextInfraRefactorCompatibilityAlias",
            ),
            ".transformers.dataclass_modelizer": (
                "FlextInfraRefactorDataclassModelizer",
            ),
            ".transformers.deprecated_remover": (
                "FlextInfraRefactorDeprecatedRemover",
            ),
            ".transformers.future_import": ("FlextInfraRefactorFutureImport",),
            ".transformers.hardcoded_version": ("FlextInfraRefactorHardcodedVersion",),
            ".transformers.import_bypass_remover": (
                "FlextInfraRefactorImportBypassRemover",
            ),
            ".transformers.import_modernizer": ("FlextInfraRefactorImportModernizer",),
            ".transformers.lazy_import_fixer": ("FlextInfraRefactorLazyImportFixer",),
            ".transformers.mro_remover": ("FlextInfraRefactorMroRemover",),
            ".transformers.open_encoding": ("FlextInfraRefactorOpenEncoding",),
            ".transformers.pattern": ("FlextInfraRefactorPatternTransformer",),
            ".transformers.pydantic_modernizer": (
                "FlextInfraRefactorPydanticModernizer",
            ),
            ".transformers.signature_propagator": (
                "FlextInfraRefactorSignaturePropagator",
            ),
            ".transformers.smells.base": ("FlextInfraSmellFixer",),
            ".transformers.smells.boolean_logic": ("FlextInfraBooleanLogicFixer",),
            ".transformers.symbol_propagator": ("FlextInfraRefactorSymbolPropagator",),
            ".transformers.typing_unifier": ("FlextInfraRefactorTypingUnifier",),
            ".typings": ("FlextInfraTypes", "t"),
            ".utilities": ("FlextInfraUtilities", "u"),
            ".validate": ("validate",),
            ".validate.cprofile_report": ("FlextInfraCProfileReport",),
            ".validate.fresh_import": ("FlextInfraValidateFreshImport",),
            ".validate.gate_contract": ("FlextInfraGateContractValidator",),
            ".validate.gate_contract_checks": ("FlextInfraGateContractChecksMixin",),
            ".validate.gate_contract_content": ("FlextInfraGateContractContentMixin",),
            ".validate.gate_contract_errors": (
                "GateContractInfraError",
                "GateContractUsageError",
            ),
            ".validate.gate_contract_report": ("FlextInfraGateContractReportMixin",),
            ".validate.gate_contract_scan": ("FlextInfraGateContractScanMixin",),
            ".validate.import_cycles": ("FlextInfraValidateImportCycles",),
            ".validate.inventory": ("FlextInfraInventoryService",),
            ".validate.lazy_map_freshness": ("FlextInfraValidateLazyMapFreshness",),
            ".validate.loc_delta": ("FlextInfraLocDeltaValidator",),
            ".validate.manual_command": ("FlextInfraManualCommandValidator",),
            ".validate.metadata_discipline": ("FlextInfraValidateMetadataDiscipline",),
            ".validate.namespace_rules": ("FlextInfraNamespaceRules",),
            ".validate.namespace_validator": ("FlextInfraNamespaceValidator",),
            ".validate.pytest_diag": ("FlextInfraPytestDiagExtractor",),
            ".validate.pytest_runner": ("FlextInfraPytestRunner",),
            ".validate.runtime_census": ("FlextInfraRuntimeCensusValidator",),
            ".validate.scanner": ("FlextInfraTextPatternScanner",),
            ".validate.silent_failure": ("FlextInfraSilentFailureValidator",),
            ".validate.skill_validator": ("FlextInfraSkillValidator",),
            ".validate.stub_chain": ("FlextInfraStubSupplyChain",),
            ".validate.testmon_db": ("FlextInfraTestmonDbInspector",),
            ".validate.tier_whitelist": ("FlextInfraValidateTierWhitelist",),
            ".workspace": ("workspace",),
            ".workspace.detector": ("FlextInfraWorkspaceDetector",),
            ".workspace.environment": ("FlextInfraWorkspaceEnvironmentMixin",),
            ".workspace.environment_beads": (
                "FlextInfraWorkspaceBeadsEnvironmentMixin",
                "FlextInfraWorkspaceEnvironmentSync",
            ),
            ".workspace.environment_contracts": (
                "FlextInfraWorkspaceEnvironmentContracts",
            ),
            ".workspace.environment_provenance": (
                "FlextInfraWorkspaceEnvironmentProvenance",
            ),
            ".workspace.flext_binding": ("FlextInfraFlextBindingService",),
            ".workspace.orchestrator": ("FlextInfraOrchestratorService",),
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
