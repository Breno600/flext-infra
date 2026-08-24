# AUTO-GENERATED FILE — Regenerate with: make gen
"""Tests.unit.codegen package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from types import MappingProxyType

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from . import autofix_workspace_tests as autofix_workspace_tests
    from . import census_models_tests as census_models_tests
    from . import census_tests as census_tests
    from . import consolidator_tests as consolidator_tests
    from . import constants_quality_gate_tests as constants_quality_gate_tests
    from . import docs_apply_contract_tests as docs_apply_contract_tests
    from . import docs_workflow_profile_tests as docs_workflow_profile_tests
    from . import init_tests as init_tests
    from . import layout_make_root_tests as layout_make_root_tests
    from . import layout_tests as layout_tests
    from . import main_tests as main_tests
    from . import pipeline_tests as pipeline_tests
    from . import scaffolder_tests as scaffolder_tests
    from . import submodule_recipe_shell_tests as submodule_recipe_shell_tests
    from . import test_codegen_catalog_extensions as test_codegen_catalog_extensions
    from . import test_codegen_ci_matrix as test_codegen_ci_matrix
    from . import test_codegen_conform as test_codegen_conform
    from . import (
        test_codegen_gitignore_profile_aware as test_codegen_gitignore_profile_aware,
    )
    from . import (
        test_codegen_manifestless_existing as test_codegen_manifestless_existing,
    )
    from . import test_codegen_py_typed as test_codegen_py_typed
    from . import test_codegen_setup_submodules as test_codegen_setup_submodules
    from . import test_codegen_version_file as test_codegen_version_file
    from . import (
        test_codegen_workspace_root_fanout as test_codegen_workspace_root_fanout,
    )
    from . import (
        test_gen_respects_invocation_scope as test_gen_respects_invocation_scope,
    )
    from . import test_pipeline_toolchain_stage as test_pipeline_toolchain_stage
    from . import test_root_artifact_ownership as test_root_artifact_ownership
    from . import (
        test_setup_isolates_worktree_environments as test_setup_isolates_worktree_environments,
    )
    from . import test_setup_never_destroys as test_setup_never_destroys
    from . import (
        test_template_formatter_fixed_point as test_template_formatter_fixed_point,
    )
    from . import test_violation_key as test_violation_key
    from . import (
        test_workspace_integration_overlay as test_workspace_integration_overlay,
    )
    from . import (
        toolchain_beads_distribution_tests as toolchain_beads_distribution_tests,
    )
    from . import toolchain_go_backend_tests as toolchain_go_backend_tests
    from . import toolchain_requirement_tests as toolchain_requirement_tests
    from . import workflow_orphan_guard_tests as workflow_orphan_guard_tests
    from flext_tests import c, d, e, h, m, p, r, s, t, td, tf, tk, tm, tv, u, x

    from .lazy_init_fixture_settings_tests import (
        TestsFlextInfraLazyInitFixtureSettingsCollision,
    )
    from .lazy_init_generation_tests import TestsFlextInfraCodegenGeneration
    from .lazy_init_helpers_tests import TestsFlextInfraLazyInitHelpers
    from .lazy_init_process_tests import TestsFlextInfraLazyInitProcessing
    from .lazy_init_registry_wrapper_tests import TestsFlextInfraLazyInitCleanup
    from .lazy_init_runtime_tests import TestsFlextInfraLazyInitRuntime
    from .lazy_init_service_tests import TestsFlextInfraCodegenLazyInitService
    from .lazy_init_tests import (
        TestAllDirectoriesScanned,
        TestCheckOnlyMode,
        TestEdgeCases,
        TestExcludedDirectories,
    )
    from .lazy_init_transforms_tests import TestsFlextInfraLazyInitTransforms
    from .make_test_selector_tests import TestsMakeTestSelector
    from .scaffolder_naming_tests import (
        TestGeneratedClassNamingConvention,
        TestGeneratedFilesAreValidPython,
    )
    from .test_codegen_artifact_ssot import TestsCodegenArtifactSsot
    from .test_codegen_beads_ledger import TestCodegenBeadsLedger
    from .test_codegen_conform_progress import TestsFlextInfraCodegenConformProgress
    from .test_codegen_hook_conformance import TestGitHookConformance
    from .test_codegen_linked_worktree_manifest import TestCodegenLinkedWorktreeManifest
    from .test_codegen_make_environment import TestsCodegenMakeEnvironment
    from .test_codegen_pyproject_conform import TestsFlextInfraCodegenPyprojectConform
    from .test_codegen_uv_exclude_newer_overlay import TestCodegenUvExcludeNewerOverlay
    from .test_managed_conflicts import TestsFlextInfraCodegenManagedConflicts
    from .test_managed_maintenance_headers import (
        TestsFlextInfraManagedMaintenanceHeaders,
    )
    from .test_review_mro_vw2w_template_contracts import TestsReviewTemplateContracts
    from .test_vscode_owner_merge import TestsVscodeOwnerMerge
    from .test_workspace_root_setup_submodules import TestsWorkspaceRootSetupSubmodules
    from .worktree_verb_tests import TestsCodegenWorkVerb
__all__: tuple[str, ...] = (
    "TestAllDirectoriesScanned",
    "TestCheckOnlyMode",
    "TestCodegenBeadsLedger",
    "TestCodegenLinkedWorktreeManifest",
    "TestCodegenUvExcludeNewerOverlay",
    "TestEdgeCases",
    "TestExcludedDirectories",
    "TestGeneratedClassNamingConvention",
    "TestGeneratedFilesAreValidPython",
    "TestGitHookConformance",
    "TestsCodegenArtifactSsot",
    "TestsCodegenMakeEnvironment",
    "TestsCodegenWorkVerb",
    "TestsFlextInfraCodegenConformProgress",
    "TestsFlextInfraCodegenGeneration",
    "TestsFlextInfraCodegenLazyInitService",
    "TestsFlextInfraCodegenManagedConflicts",
    "TestsFlextInfraCodegenPyprojectConform",
    "TestsFlextInfraLazyInitCleanup",
    "TestsFlextInfraLazyInitFixtureSettingsCollision",
    "TestsFlextInfraLazyInitHelpers",
    "TestsFlextInfraLazyInitProcessing",
    "TestsFlextInfraLazyInitRuntime",
    "TestsFlextInfraLazyInitTransforms",
    "TestsFlextInfraManagedMaintenanceHeaders",
    "TestsMakeTestSelector",
    "TestsReviewTemplateContracts",
    "TestsVscodeOwnerMerge",
    "TestsWorkspaceRootSetupSubmodules",
    "autofix_workspace_tests",
    "c",
    "census_models_tests",
    "census_tests",
    "consolidator_tests",
    "constants_quality_gate_tests",
    "d",
    "docs_apply_contract_tests",
    "docs_workflow_profile_tests",
    "e",
    "h",
    "init_tests",
    "layout_make_root_tests",
    "layout_tests",
    "m",
    "main_tests",
    "p",
    "pipeline_tests",
    "r",
    "s",
    "scaffolder_tests",
    "submodule_recipe_shell_tests",
    "t",
    "td",
    "test_codegen_catalog_extensions",
    "test_codegen_ci_matrix",
    "test_codegen_conform",
    "test_codegen_gitignore_profile_aware",
    "test_codegen_manifestless_existing",
    "test_codegen_py_typed",
    "test_codegen_setup_submodules",
    "test_codegen_version_file",
    "test_codegen_workspace_root_fanout",
    "test_gen_respects_invocation_scope",
    "test_pipeline_toolchain_stage",
    "test_root_artifact_ownership",
    "test_setup_isolates_worktree_environments",
    "test_setup_never_destroys",
    "test_template_formatter_fixed_point",
    "test_violation_key",
    "test_workspace_integration_overlay",
    "tf",
    "tk",
    "tm",
    "toolchain_beads_distribution_tests",
    "toolchain_go_backend_tests",
    "toolchain_requirement_tests",
    "tv",
    "u",
    "workflow_orphan_guard_tests",
    "x",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".autofix_workspace_tests": ("autofix_workspace_tests",),
            ".census_models_tests": ("census_models_tests",),
            ".census_tests": ("census_tests",),
            ".consolidator_tests": ("consolidator_tests",),
            ".constants_quality_gate_tests": ("constants_quality_gate_tests",),
            ".docs_apply_contract_tests": ("docs_apply_contract_tests",),
            ".docs_workflow_profile_tests": ("docs_workflow_profile_tests",),
            ".init_tests": ("init_tests",),
            ".layout_make_root_tests": ("layout_make_root_tests",),
            ".layout_tests": ("layout_tests",),
            ".lazy_init_fixture_settings_tests": (
                "TestsFlextInfraLazyInitFixtureSettingsCollision",
            ),
            ".lazy_init_generation_tests": ("TestsFlextInfraCodegenGeneration",),
            ".lazy_init_helpers_tests": ("TestsFlextInfraLazyInitHelpers",),
            ".lazy_init_process_tests": ("TestsFlextInfraLazyInitProcessing",),
            ".lazy_init_registry_wrapper_tests": ("TestsFlextInfraLazyInitCleanup",),
            ".lazy_init_runtime_tests": ("TestsFlextInfraLazyInitRuntime",),
            ".lazy_init_service_tests": ("TestsFlextInfraCodegenLazyInitService",),
            ".lazy_init_tests": (
                "TestAllDirectoriesScanned",
                "TestCheckOnlyMode",
                "TestEdgeCases",
                "TestExcludedDirectories",
            ),
            ".lazy_init_transforms_tests": ("TestsFlextInfraLazyInitTransforms",),
            ".main_tests": ("main_tests",),
            ".make_test_selector_tests": ("TestsMakeTestSelector",),
            ".pipeline_tests": ("pipeline_tests",),
            ".scaffolder_naming_tests": (
                "TestGeneratedClassNamingConvention",
                "TestGeneratedFilesAreValidPython",
            ),
            ".scaffolder_tests": ("scaffolder_tests",),
            ".submodule_recipe_shell_tests": ("submodule_recipe_shell_tests",),
            ".test_codegen_artifact_ssot": ("TestsCodegenArtifactSsot",),
            ".test_codegen_beads_ledger": ("TestCodegenBeadsLedger",),
            ".test_codegen_catalog_extensions": ("test_codegen_catalog_extensions",),
            ".test_codegen_ci_matrix": ("test_codegen_ci_matrix",),
            ".test_codegen_conform": ("test_codegen_conform",),
            ".test_codegen_conform_progress": (
                "TestsFlextInfraCodegenConformProgress",
            ),
            ".test_codegen_gitignore_profile_aware": (
                "test_codegen_gitignore_profile_aware",
            ),
            ".test_codegen_hook_conformance": ("TestGitHookConformance",),
            ".test_codegen_linked_worktree_manifest": (
                "TestCodegenLinkedWorktreeManifest",
            ),
            ".test_codegen_make_environment": ("TestsCodegenMakeEnvironment",),
            ".test_codegen_manifestless_existing": (
                "test_codegen_manifestless_existing",
            ),
            ".test_codegen_py_typed": ("test_codegen_py_typed",),
            ".test_codegen_pyproject_conform": (
                "TestsFlextInfraCodegenPyprojectConform",
            ),
            ".test_codegen_setup_submodules": ("test_codegen_setup_submodules",),
            ".test_codegen_uv_exclude_newer_overlay": (
                "TestCodegenUvExcludeNewerOverlay",
            ),
            ".test_codegen_version_file": ("test_codegen_version_file",),
            ".test_codegen_workspace_root_fanout": (
                "test_codegen_workspace_root_fanout",
            ),
            ".test_gen_respects_invocation_scope": (
                "test_gen_respects_invocation_scope",
            ),
            ".test_managed_conflicts": ("TestsFlextInfraCodegenManagedConflicts",),
            ".test_managed_maintenance_headers": (
                "TestsFlextInfraManagedMaintenanceHeaders",
            ),
            ".test_pipeline_toolchain_stage": ("test_pipeline_toolchain_stage",),
            ".test_review_mro_vw2w_template_contracts": (
                "TestsReviewTemplateContracts",
            ),
            ".test_root_artifact_ownership": ("test_root_artifact_ownership",),
            ".test_setup_isolates_worktree_environments": (
                "test_setup_isolates_worktree_environments",
            ),
            ".test_setup_never_destroys": ("test_setup_never_destroys",),
            ".test_template_formatter_fixed_point": (
                "test_template_formatter_fixed_point",
            ),
            ".test_violation_key": ("test_violation_key",),
            ".test_vscode_owner_merge": ("TestsVscodeOwnerMerge",),
            ".test_workspace_integration_overlay": (
                "test_workspace_integration_overlay",
            ),
            ".test_workspace_root_setup_submodules": (
                "TestsWorkspaceRootSetupSubmodules",
            ),
            ".toolchain_beads_distribution_tests": (
                "toolchain_beads_distribution_tests",
            ),
            ".toolchain_go_backend_tests": ("toolchain_go_backend_tests",),
            ".toolchain_requirement_tests": ("toolchain_requirement_tests",),
            ".workflow_orphan_guard_tests": ("workflow_orphan_guard_tests",),
            ".worktree_verb_tests": ("TestsCodegenWorkVerb",),
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
