"""Utilities facade for flext-infra.

Re-exports flext_core utilities and adds infrastructure-specific
utility namespaces. All methods are exposed directly as ``u.Infra.<method>()``.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import FlextCliUtilities

from flext_infra._utilities.private_import_ancestry import (
    FlextInfraUtilitiesPrivateImportAncestry,
)
from flext_infra._utilities.private_import_facades import (
    FlextInfraUtilitiesPrivateImportFacades,
)

from ._utilities._docs_github_links import FlextInfraUtilitiesDocsGithubLinks
from ._utilities._rope.pep695_patch import FlextInfraUtilitiesRopePep695Patch
from ._utilities._rope.signature_patch import FlextInfraUtilitiesRopeSignaturePatch
from ._utilities.base import FlextInfraUtilitiesBase
from ._utilities.census import FlextInfraUtilitiesRefactorCensus
from ._utilities.codegen import FlextInfraUtilitiesCodegen
from ._utilities.codegen_file_plan import FlextInfraUtilitiesCodegenFilePlan
from ._utilities.codemod_rules import FlextInfraUtilitiesCodemodRules
from ._utilities.deferred_self_reference_ast import (
    FlextInfraUtilitiesDeferredSelfReference,
)
from ._utilities.dependencies import FlextInfraUtilitiesDependencies
from ._utilities.discovery import FlextInfraUtilitiesDiscovery
from ._utilities.docs import FlextInfraUtilitiesDocs
from ._utilities.docs_api import FlextInfraUtilitiesDocsApi
from ._utilities.docs_audit import FlextInfraUtilitiesDocsAudit
from ._utilities.docs_build import FlextInfraUtilitiesDocsBuild
from ._utilities.docs_contract import FlextInfraUtilitiesDocsContract
from ._utilities.docs_fix import FlextInfraUtilitiesDocsFix
from ._utilities.docs_generate import FlextInfraUtilitiesDocsGenerate
from ._utilities.docs_render import FlextInfraUtilitiesDocsRender
from ._utilities.docs_scope import FlextInfraUtilitiesDocsScope
from ._utilities.docs_validate import FlextInfraUtilitiesDocsValidate
from ._utilities.git import FlextInfraUtilitiesGit
from ._utilities.iteration import FlextInfraUtilitiesIteration
from ._utilities.log_parser import FlextInfraUtilitiesLogParser
from ._utilities.managed_conflicts import FlextInfraUtilitiesManagedConflicts
from ._utilities.namespace import FlextInfraUtilitiesCodegenNamespace
from ._utilities.namespace_analysis import FlextInfraUtilitiesRefactorNamespaceFlext
from ._utilities.namespace_common import FlextInfraUtilitiesRefactorNamespaceCommon
from ._utilities.namespace_facades import FlextInfraUtilitiesRefactorNamespaceFacades
from ._utilities.namespace_moves import FlextInfraUtilitiesRefactorNamespaceMoves
from ._utilities.network import FlextInfraUtilitiesNetwork
from ._utilities.private_import_ancestry import FlextInfraUtilitiesPrivateImportAncestry
from ._utilities.private_import_facades import FlextInfraUtilitiesPrivateImportFacades
from ._utilities.process import FlextInfraUtilitiesProcess
from ._utilities.project_managed_artifacts import (
    FlextInfraUtilitiesProjectManagedArtifacts,
)
from ._utilities.promoted import FlextInfraUtilitiesPromoted
from ._utilities.protected_edit import FlextInfraUtilitiesProtectedEdit
from ._utilities.pyproject_conform import FlextInfraUtilitiesPyprojectConform
from ._utilities.pyrefly import FlextInfraUtilitiesPyrefly
from ._utilities.qualified_names import FlextInfraUtilitiesQualifiedNames
from ._utilities.refactor import FlextInfraUtilitiesRefactor
from ._utilities.release import FlextInfraUtilitiesRelease
from ._utilities.repository import FlextInfraUtilitiesRepository
from ._utilities.resource_limits import FlextInfraUtilitiesResourceLimits
from ._utilities.rope_analysis import FlextInfraUtilitiesRopeAnalysis
from ._utilities.rope_analysis_introspection import (
    FlextInfraUtilitiesRopeAnalysisIntrospection,
)
from ._utilities.rope_analysis_workspace import FlextInfraUtilitiesRopeAnalysisWorkspace
from ._utilities.rope_class_move import FlextInfraUtilitiesRopeClassMove
from ._utilities.rope_core import FlextInfraUtilitiesRopeCore
from ._utilities.rope_helpers import FlextInfraUtilitiesRopeHelpers
from ._utilities.rope_imports import FlextInfraUtilitiesRopeImports
from ._utilities.rope_inventory import FlextInfraUtilitiesRopeInventory
from ._utilities.rope_module_patch import FlextInfraUtilitiesRopeModulePatch
from ._utilities.rope_runtime import FlextInfraUtilitiesRopeRuntime
from ._utilities.rope_source import FlextInfraUtilitiesRopeSource
from ._utilities.rope_structure import FlextInfraUtilitiesRopeStructure
from ._utilities.safety import FlextInfraUtilitiesSafety
from ._utilities.semantic_cutover import FlextInfraUtilitiesSemanticCutover
from ._utilities.signature_rules import FlextInfraUtilitiesSignatureRules
from ._utilities.silent_failure_ast import FlextInfraUtilitiesSilentFailureAst
from ._utilities.transformer_header import FlextInfraUtilitiesTransformerHeader
from ._utilities.versioning import FlextInfraUtilitiesVersioning
from ._utilities.workspace_fingerprint import FlextInfraUtilitiesWorkspaceFingerprint
from ._utilities.workspace_manifest import FlextInfraUtilitiesWorkspaceManifest
from ._utilities.worktree_lifecycle import FlextInfraWorktreeLifecycle
from ._utilities.worktree_provisioning import FlextInfraWorktreeProvisioning


class FlextInfraUtilities(FlextCliUtilities):
    """Utility namespace for flext-infra; extends FlextUtilities.

    Usage::

        from flext_infra import m, u

        u.Infra.git_status(m.Infra.GitStatusRequest(repo_root=Path(".")))
        u.Cli.toml_read_json(path)
        u.Infra.discover_projects(repository_root)
        u.Infra.parse_semver("1.2.3")
    """

    class Infra(
        FlextInfraUtilitiesBase,
        FlextInfraUtilitiesProcess,
        FlextInfraUtilitiesPromoted,
        FlextInfraUtilitiesNetwork,
        FlextInfraUtilitiesResourceLimits,
        FlextInfraUtilitiesCodegen,
        FlextInfraUtilitiesCodegenFilePlan,
        FlextInfraUtilitiesCodegenNamespace,
        FlextInfraUtilitiesPyprojectConform,
        FlextInfraUtilitiesPyrefly,
        FlextInfraUtilitiesProjectManagedArtifacts,
        FlextInfraUtilitiesQualifiedNames,
        FlextInfraUtilitiesDiscovery,
        FlextInfraUtilitiesRopeCore,
        FlextInfraUtilitiesRopeAnalysis,
        FlextInfraUtilitiesRopeAnalysisWorkspace,
        FlextInfraUtilitiesRopeAnalysisIntrospection,
        FlextInfraUtilitiesRopeClassMove,
        FlextInfraUtilitiesRopeHelpers,
        FlextInfraUtilitiesRopeInventory,
        FlextInfraUtilitiesRopeImports,
        FlextInfraUtilitiesRopeModulePatch,
        FlextInfraUtilitiesRopeRuntime,
        FlextInfraUtilitiesRopeSource,
        FlextInfraUtilitiesRopeStructure,
        FlextInfraUtilitiesRopePep695Patch,
        FlextInfraUtilitiesTransformerHeader,
        FlextInfraUtilitiesDocs,
        FlextInfraUtilitiesDocsApi,
        FlextInfraUtilitiesDocsAudit,
        FlextInfraUtilitiesDocsBuild,
        FlextInfraUtilitiesDocsContract,
        FlextInfraUtilitiesDocsFix,
        FlextInfraUtilitiesDocsGenerate,
        FlextInfraUtilitiesDocsGithubLinks,
        FlextInfraUtilitiesDocsRender,
        FlextInfraUtilitiesDocsScope,
        FlextInfraUtilitiesDocsValidate,
        FlextInfraUtilitiesWorkspaceManifest,
        FlextInfraUtilitiesDependencies,
        FlextInfraUtilitiesDeferredSelfReference,
        FlextInfraUtilitiesGit,
        FlextInfraUtilitiesIteration,
        FlextInfraUtilitiesLogParser,
        FlextInfraUtilitiesManagedConflicts,
        FlextInfraUtilitiesSemanticCutover,
        FlextInfraUtilitiesProtectedEdit,
        FlextInfraUtilitiesRefactor,
        FlextInfraUtilitiesRefactorCensus,
        FlextInfraUtilitiesRefactorNamespaceFlext,
        FlextInfraUtilitiesRefactorNamespaceCommon,
        FlextInfraUtilitiesRefactorNamespaceFacades,
        FlextInfraUtilitiesRefactorNamespaceMoves,
        FlextInfraUtilitiesRelease,
        FlextInfraUtilitiesRepository,
        FlextInfraUtilitiesSafety,
        FlextInfraUtilitiesSilentFailureAst,
        FlextInfraUtilitiesVersioning,
        FlextInfraWorktreeLifecycle,
        FlextInfraWorktreeProvisioning,
        FlextInfraUtilitiesWorkspaceFingerprint,
        FlextInfraUtilitiesCodemodRules,
        FlextInfraUtilitiesSignatureRules,
        FlextInfraUtilitiesPrivateImportAncestry,
        FlextInfraUtilitiesPrivateImportFacades,
    ):
        """Infrastructure-domain utilities - all methods exposed directly."""

        _rope_pep695_patch_applied: bool = (
            FlextInfraUtilitiesRopePep695Patch.apply() or True
        )
        _rope_signature_patch_applied: bool = (
            FlextInfraUtilitiesRopeSignaturePatch.apply() or True
        )


u = FlextInfraUtilities

__all__: list[str] = ["FlextInfraUtilities", "u"]
