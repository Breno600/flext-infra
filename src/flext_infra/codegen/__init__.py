# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.codegen package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

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

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._codegen_generation_file": ("FlextInfraCodegenGenerationFileMixin",),
            "._codegen_generation_imports": (
                "FlextInfraCodegenGenerationImportsMixin",
            ),
            "._codegen_generation_lazy_entries": (
                "FlextInfraCodegenGenerationLazyEntriesMixin",
            ),
            "._codegen_generation_paths": ("FlextInfraCodegenGenerationPathsMixin",),
            "._codegen_generation_renderers": (
                "FlextInfraCodegenGenerationRenderersMixin",
            ),
            "._codegen_generation_standard": (
                "FlextInfraCodegenGenerationStandardMixin",
            ),
            "._codegen_generation_type_checking": (
                "FlextInfraCodegenGenerationTypeCheckingMixin",
            ),
            "._codegen_staging": ("FlextInfraCodegenStaging",),
            "._conform": ("_conform",),
            "._conform.artifact_render": ("FlextInfraCodegenConformArtifactRender",),
            "._conform.beads_routes": ("FlextInfraCodegenConformBeadsRoutes",),
            "._conform.bootstrap": ("FlextInfraCodegenConformBootstrap",),
            "._conform.context_render": ("FlextInfraCodegenConformContextRender",),
            "._conform.docs_ownership": ("FlextInfraCodegenConformDocsOwnership",),
            "._conform.execute": ("FlextInfraCodegenConformExecute",),
            "._conform.existing_plan": ("FlextInfraCodegenConformExistingPlan",),
            "._conform.file_plans": ("FlextInfraCodegenConformFilePlans",),
            "._conform.gitignore": ("FlextInfraCodegenConformGitignore",),
            "._conform.plan": ("FlextInfraCodegenConformPlan",),
            "._conform.pyproject_policy": ("FlextInfraCodegenConformPyprojectPolicy",),
            "._conform.scaffold_plan": ("FlextInfraCodegenConformScaffoldPlan",),
            "._consolidator_steps": ("FlextInfraCodegenConsolidatorStepsMixin",),
            "._execution": ("FlextInfraCodegenExecutionBase",),
            "._fixer_passes": ("FlextInfraCodegenFixerPassesMixin",),
            "._fixer_results": ("FlextInfraCodegenFixerResultsMixin",),
            "._fixer_workspace": ("FlextInfraCodegenFixerWorkspaceMixin",),
            "._layout_apply": ("FlextInfraCodegenLayoutApplyMixin",),
            "._layout_files": ("FlextInfraCodegenLayoutFilesMixin",),
            "._layout_gitignore": ("FlextInfraCodegenLayoutGitignoreMixin",),
            "._layout_plan": ("FlextInfraCodegenLayoutPlanMixin",),
            "._lazy_init_generation_files": (
                "FlextInfraCodegenLazyInitGenerationFilePlanMixin",
            ),
            "._lazy_init_generation_registry": (
                "FlextInfraCodegenLazyInitGenerationRegistryMixin",
            ),
            "._lazy_init_planner_public_root": (
                "FlextInfraCodegenLazyInitPlannerPublicRootMixin",
            ),
            "._lazy_init_projection_manifest": (
                "FlextInfraCodegenLazyInitProjectionManifest",
            ),
            "._mise_artifacts_candidates": ("FlextInfraMiseArtifactsCandidates",),
            "._mise_artifacts_cold_start": ("FlextInfraMiseColdStart",),
            "._mise_artifacts_derivation": ("FlextInfraMiseArtifactsDerivation",),
            "._mise_artifacts_journal": ("FlextInfraMiseArtifactsJournal",),
            "._mise_artifacts_process": ("FlextInfraMiseArtifactsProcess",),
            "._mise_artifacts_recovery": ("FlextInfraMiseRecovery",),
            "._mise_artifacts_staging": ("FlextInfraMiseStaging",),
            "._mise_artifacts_state": ("FlextInfraMiseArtifactsState",),
            "._mise_artifacts_verification": ("FlextInfraMiseArtifactsVerification",),
            "._protocol_model_annotations": (
                "FlextInfraCodegenProtocolModelAnnotations",
            ),
            "._protocol_model_render": ("FlextInfraCodegenProtocolModelRender",),
            ".census": ("FlextInfraCodegenCensus",),
            ".codegen_generation": ("FlextInfraCodegenGeneration",),
            ".codegen_transaction": ("FlextInfraCodegenTransaction",),
            ".conform": ("FlextInfraCodegenConform",),
            ".consolidator": ("FlextInfraCodegenConsolidator",),
            ".constants_quality_gate": ("FlextInfraCodegenQualityGate",),
            ".file_leases": ("FlextInfraCodegenFileLeases",),
            ".fixer": ("FlextInfraCodegenFixer",),
            ".layout": ("FlextInfraCodegenLayout",),
            ".lazy_init": ("FlextInfraCodegenLazyInit",),
            ".lazy_init_planner": ("FlextInfraCodegenLazyInitPlanner",),
            ".make_bootstrap": ("FlextInfraCodegenMakeBootstrap",),
            ".mise_artifacts": ("FlextInfraCodegenMiseArtifacts",),
            ".mise_artifacts_workspace": ("FlextInfraMiseWorkspacePlanner",),
            ".pipeline": (
                "FlextInfraCodegenLazyInitGenerationMixin",
                "FlextInfraCodegenPipeline",
                "FlextInfraCodegenPipelineStagesMixin",
                "FlextInfraMiseArtifactsFiles",
                "FlextInfraMisePublication",
            ),
            ".project_new": ("FlextInfraCodegenProjectNew",),
            ".protocol_models": ("FlextInfraCodegenProtocolModels",),
            ".py_typed": ("FlextInfraCodegenPyTyped",),
            ".scaffolder": ("FlextInfraCodegenScaffolder",),
            ".version_file": ("FlextInfraCodegenVersionFile",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
