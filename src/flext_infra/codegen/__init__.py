# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.codegen package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.codegen import _conform
    from flext_infra.codegen._codegen_generation_file import (
        FlextInfraCodegenGenerationFileMixin,
    )
    from flext_infra.codegen._codegen_generation_imports import (
        FlextInfraCodegenGenerationImportsMixin,
    )
    from flext_infra.codegen._codegen_generation_lazy_entries import (
        FlextInfraCodegenGenerationLazyEntriesMixin,
    )
    from flext_infra.codegen._codegen_generation_paths import (
        FlextInfraCodegenGenerationPathsMixin,
    )
    from flext_infra.codegen._codegen_generation_renderers import (
        FlextInfraCodegenGenerationRenderersMixin,
    )
    from flext_infra.codegen._codegen_generation_standard import (
        FlextInfraCodegenGenerationStandardMixin,
    )
    from flext_infra.codegen._codegen_generation_type_checking import (
        FlextInfraCodegenGenerationTypeCheckingMixin,
    )
    from flext_infra.codegen._codegen_staging import FlextInfraCodegenStaging
    from flext_infra.codegen._conform.artifact_render import (
        FlextInfraCodegenConformArtifactRender,
    )
    from flext_infra.codegen._conform.beads_routes import (
        FlextInfraCodegenConformBeadsRoutes,
    )
    from flext_infra.codegen._conform.bootstrap import FlextInfraCodegenConformBootstrap
    from flext_infra.codegen._conform.context_render import (
        FlextInfraCodegenConformContextRender,
    )
    from flext_infra.codegen._conform.docs_ownership import (
        FlextInfraCodegenConformDocsOwnership,
    )
    from flext_infra.codegen._conform.execute import FlextInfraCodegenConformExecute
    from flext_infra.codegen._conform.existing_plan import (
        FlextInfraCodegenConformExistingPlan,
    )
    from flext_infra.codegen._conform.file_plans import (
        FlextInfraCodegenConformFilePlans,
    )
    from flext_infra.codegen._conform.gitignore import FlextInfraCodegenConformGitignore
    from flext_infra.codegen._conform.plan import FlextInfraCodegenConformPlan
    from flext_infra.codegen._conform.pyproject_policy import (
        FlextInfraCodegenConformPyprojectPolicy,
    )
    from flext_infra.codegen._conform.scaffold_plan import (
        FlextInfraCodegenConformScaffoldPlan,
    )
    from flext_infra.codegen._consolidator_steps import (
        FlextInfraCodegenConsolidatorStepsMixin,
    )
    from flext_infra.codegen._execution import FlextInfraCodegenExecutionBase
    from flext_infra.codegen._fixer_passes import FlextInfraCodegenFixerPassesMixin
    from flext_infra.codegen._fixer_results import FlextInfraCodegenFixerResultsMixin
    from flext_infra.codegen._fixer_workspace import (
        FlextInfraCodegenFixerWorkspaceMixin,
    )
    from flext_infra.codegen._layout_apply import FlextInfraCodegenLayoutApplyMixin
    from flext_infra.codegen._layout_files import FlextInfraCodegenLayoutFilesMixin
    from flext_infra.codegen._layout_gitignore import (
        FlextInfraCodegenLayoutGitignoreMixin,
    )
    from flext_infra.codegen._layout_plan import FlextInfraCodegenLayoutPlanMixin
    from flext_infra.codegen._lazy_init_generation_files import (
        FlextInfraCodegenLazyInitGenerationFilePlanMixin,
    )
    from flext_infra.codegen._lazy_init_generation_registry import (
        FlextInfraCodegenLazyInitGenerationRegistryMixin,
    )
    from flext_infra.codegen._lazy_init_planner_public_root import (
        FlextInfraCodegenLazyInitPlannerPublicRootMixin,
    )
    from flext_infra.codegen._lazy_init_projection_manifest import (
        FlextInfraCodegenLazyInitProjectionManifest,
    )
    from flext_infra.codegen._mise_artifacts_candidates import (
        FlextInfraMiseArtifactsCandidates,
    )
    from flext_infra.codegen._mise_artifacts_cold_start import FlextInfraMiseColdStart
    from flext_infra.codegen._mise_artifacts_derivation import (
        FlextInfraMiseArtifactsDerivation,
    )
    from flext_infra.codegen._mise_artifacts_journal import (
        FlextInfraMiseArtifactsJournal,
    )
    from flext_infra.codegen._mise_artifacts_process import (
        FlextInfraMiseArtifactsProcess,
    )
    from flext_infra.codegen._mise_artifacts_recovery import FlextInfraMiseRecovery
    from flext_infra.codegen._mise_artifacts_staging import FlextInfraMiseStaging
    from flext_infra.codegen._mise_artifacts_state import FlextInfraMiseArtifactsState
    from flext_infra.codegen._mise_artifacts_verification import (
        FlextInfraMiseArtifactsVerification,
    )
    from flext_infra.codegen._protocol_model_annotations import (
        FlextInfraCodegenProtocolModelAnnotations,
    )
    from flext_infra.codegen._protocol_model_render import (
        FlextInfraCodegenProtocolModelRender,
    )
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


__all__: tuple[str, ...] = (
    "FlextInfraCodegenCensus",
    "FlextInfraCodegenConform",
    "FlextInfraCodegenConformArtifactRender",
    "FlextInfraCodegenConformBeadsRoutes",
    "FlextInfraCodegenConformBootstrap",
    "FlextInfraCodegenConformContextRender",
    "FlextInfraCodegenConformDocsOwnership",
    "FlextInfraCodegenConformExecute",
    "FlextInfraCodegenConformExistingPlan",
    "FlextInfraCodegenConformFilePlans",
    "FlextInfraCodegenConformGitignore",
    "FlextInfraCodegenConformPlan",
    "FlextInfraCodegenConformPyprojectPolicy",
    "FlextInfraCodegenConformScaffoldPlan",
    "FlextInfraCodegenConsolidator",
    "FlextInfraCodegenConsolidatorStepsMixin",
    "FlextInfraCodegenExecutionBase",
    "FlextInfraCodegenFileLeases",
    "FlextInfraCodegenFixer",
    "FlextInfraCodegenFixerPassesMixin",
    "FlextInfraCodegenFixerResultsMixin",
    "FlextInfraCodegenFixerWorkspaceMixin",
    "FlextInfraCodegenGeneration",
    "FlextInfraCodegenGenerationFileMixin",
    "FlextInfraCodegenGenerationImportsMixin",
    "FlextInfraCodegenGenerationLazyEntriesMixin",
    "FlextInfraCodegenGenerationPathsMixin",
    "FlextInfraCodegenGenerationRenderersMixin",
    "FlextInfraCodegenGenerationStandardMixin",
    "FlextInfraCodegenGenerationTypeCheckingMixin",
    "FlextInfraCodegenLayout",
    "FlextInfraCodegenLayoutApplyMixin",
    "FlextInfraCodegenLayoutFilesMixin",
    "FlextInfraCodegenLayoutGitignoreMixin",
    "FlextInfraCodegenLayoutPlanMixin",
    "FlextInfraCodegenLazyInit",
    "FlextInfraCodegenLazyInitGenerationFilePlanMixin",
    "FlextInfraCodegenLazyInitGenerationMixin",
    "FlextInfraCodegenLazyInitGenerationRegistryMixin",
    "FlextInfraCodegenLazyInitPlanner",
    "FlextInfraCodegenLazyInitPlannerPublicRootMixin",
    "FlextInfraCodegenLazyInitProjectionManifest",
    "FlextInfraCodegenMakeBootstrap",
    "FlextInfraCodegenMiseArtifacts",
    "FlextInfraCodegenPipeline",
    "FlextInfraCodegenPipelineStagesMixin",
    "FlextInfraCodegenProjectNew",
    "FlextInfraCodegenProtocolModelAnnotations",
    "FlextInfraCodegenProtocolModelRender",
    "FlextInfraCodegenProtocolModels",
    "FlextInfraCodegenPyTyped",
    "FlextInfraCodegenQualityGate",
    "FlextInfraCodegenScaffolder",
    "FlextInfraCodegenStaging",
    "FlextInfraCodegenTransaction",
    "FlextInfraCodegenVersionFile",
    "FlextInfraMiseArtifactsCandidates",
    "FlextInfraMiseArtifactsDerivation",
    "FlextInfraMiseArtifactsFiles",
    "FlextInfraMiseArtifactsJournal",
    "FlextInfraMiseArtifactsProcess",
    "FlextInfraMiseArtifactsState",
    "FlextInfraMiseArtifactsVerification",
    "FlextInfraMiseColdStart",
    "FlextInfraMisePublication",
    "FlextInfraMiseRecovery",
    "FlextInfraMiseStaging",
    "FlextInfraMiseWorkspacePlanner",
    "_conform",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraCodegenCensus": ".census",
        "FlextInfraCodegenConform": ".conform",
        "FlextInfraCodegenConformArtifactRender": "._conform.artifact_render",
        "FlextInfraCodegenConformBeadsRoutes": "._conform.beads_routes",
        "FlextInfraCodegenConformBootstrap": "._conform.bootstrap",
        "FlextInfraCodegenConformContextRender": "._conform.context_render",
        "FlextInfraCodegenConformDocsOwnership": "._conform.docs_ownership",
        "FlextInfraCodegenConformExecute": "._conform.execute",
        "FlextInfraCodegenConformExistingPlan": "._conform.existing_plan",
        "FlextInfraCodegenConformFilePlans": "._conform.file_plans",
        "FlextInfraCodegenConformGitignore": "._conform.gitignore",
        "FlextInfraCodegenConformPlan": "._conform.plan",
        "FlextInfraCodegenConformPyprojectPolicy": "._conform.pyproject_policy",
        "FlextInfraCodegenConformScaffoldPlan": "._conform.scaffold_plan",
        "FlextInfraCodegenConsolidator": ".consolidator",
        "FlextInfraCodegenConsolidatorStepsMixin": "._consolidator_steps",
        "FlextInfraCodegenExecutionBase": "._execution",
        "FlextInfraCodegenFileLeases": ".file_leases",
        "FlextInfraCodegenFixer": ".fixer",
        "FlextInfraCodegenFixerPassesMixin": "._fixer_passes",
        "FlextInfraCodegenFixerResultsMixin": "._fixer_results",
        "FlextInfraCodegenFixerWorkspaceMixin": "._fixer_workspace",
        "FlextInfraCodegenGeneration": ".codegen_generation",
        "FlextInfraCodegenGenerationFileMixin": "._codegen_generation_file",
        "FlextInfraCodegenGenerationImportsMixin": "._codegen_generation_imports",
        "FlextInfraCodegenGenerationLazyEntriesMixin": (
            "._codegen_generation_lazy_entries"
        ),
        "FlextInfraCodegenGenerationPathsMixin": "._codegen_generation_paths",
        "FlextInfraCodegenGenerationRenderersMixin": "._codegen_generation_renderers",
        "FlextInfraCodegenGenerationStandardMixin": "._codegen_generation_standard",
        "FlextInfraCodegenGenerationTypeCheckingMixin": (
            "._codegen_generation_type_checking"
        ),
        "FlextInfraCodegenLayout": ".layout",
        "FlextInfraCodegenLayoutApplyMixin": "._layout_apply",
        "FlextInfraCodegenLayoutFilesMixin": "._layout_files",
        "FlextInfraCodegenLayoutGitignoreMixin": "._layout_gitignore",
        "FlextInfraCodegenLayoutPlanMixin": "._layout_plan",
        "FlextInfraCodegenLazyInit": ".lazy_init",
        "FlextInfraCodegenLazyInitGenerationFilePlanMixin": (
            "._lazy_init_generation_files"
        ),
        "FlextInfraCodegenLazyInitGenerationMixin": ".pipeline",
        "FlextInfraCodegenLazyInitGenerationRegistryMixin": (
            "._lazy_init_generation_registry"
        ),
        "FlextInfraCodegenLazyInitPlanner": ".lazy_init_planner",
        "FlextInfraCodegenLazyInitPlannerPublicRootMixin": (
            "._lazy_init_planner_public_root"
        ),
        "FlextInfraCodegenLazyInitProjectionManifest": (
            "._lazy_init_projection_manifest"
        ),
        "FlextInfraCodegenMakeBootstrap": ".make_bootstrap",
        "FlextInfraCodegenMiseArtifacts": ".mise_artifacts",
        "FlextInfraCodegenPipeline": ".pipeline",
        "FlextInfraCodegenPipelineStagesMixin": ".pipeline",
        "FlextInfraCodegenProjectNew": ".project_new",
        "FlextInfraCodegenProtocolModelAnnotations": "._protocol_model_annotations",
        "FlextInfraCodegenProtocolModelRender": "._protocol_model_render",
        "FlextInfraCodegenProtocolModels": ".protocol_models",
        "FlextInfraCodegenPyTyped": ".py_typed",
        "FlextInfraCodegenQualityGate": ".constants_quality_gate",
        "FlextInfraCodegenScaffolder": ".scaffolder",
        "FlextInfraCodegenStaging": "._codegen_staging",
        "FlextInfraCodegenTransaction": ".codegen_transaction",
        "FlextInfraCodegenVersionFile": ".version_file",
        "FlextInfraMiseArtifactsCandidates": "._mise_artifacts_candidates",
        "FlextInfraMiseArtifactsDerivation": "._mise_artifacts_derivation",
        "FlextInfraMiseArtifactsFiles": ".pipeline",
        "FlextInfraMiseArtifactsJournal": "._mise_artifacts_journal",
        "FlextInfraMiseArtifactsProcess": "._mise_artifacts_process",
        "FlextInfraMiseArtifactsState": "._mise_artifacts_state",
        "FlextInfraMiseArtifactsVerification": "._mise_artifacts_verification",
        "FlextInfraMiseColdStart": "._mise_artifacts_cold_start",
        "FlextInfraMisePublication": ".pipeline",
        "FlextInfraMiseRecovery": "._mise_artifacts_recovery",
        "FlextInfraMiseStaging": "._mise_artifacts_staging",
        "FlextInfraMiseWorkspacePlanner": ".mise_artifacts_workspace",
        "_conform": "._conform",
    }),
    public_exports=__all__,
)
