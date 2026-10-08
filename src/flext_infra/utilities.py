"""Utilities facade for flext-infra.

Re-exports flext_core utilities and adds infrastructure-specific
utility namespaces. All methods are exposed directly as ``u.Infra.<method>()``.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import FlextCliUtilities

from flext_infra._utilities import (
    FlextInfraUtilitiesBase,
    FlextInfraUtilitiesCodegen,
    FlextInfraUtilitiesCodegenFilePlan,
    FlextInfraUtilitiesCodegenNamespace,
    FlextInfraUtilitiesCodegenPathCutover,
    FlextInfraUtilitiesCodemodProject,
    FlextInfraUtilitiesDeferredSelfReferenceRewrite,
    FlextInfraUtilitiesDependencies,
    FlextInfraUtilitiesDiscovery,
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
    FlextInfraUtilitiesGit,
    FlextInfraUtilitiesIteration,
    FlextInfraUtilitiesLintRecipes,
    FlextInfraUtilitiesLogParser,
    FlextInfraUtilitiesManagedConflicts,
    FlextInfraUtilitiesNetwork,
    FlextInfraUtilitiesPrivateImportAncestry,
    FlextInfraUtilitiesPrivateImportFacades,
    FlextInfraUtilitiesProcess,
    FlextInfraUtilitiesProjectManagedArtifacts,
    FlextInfraUtilitiesPromoted,
    FlextInfraUtilitiesProtectedEdit,
    FlextInfraUtilitiesPyprojectConform,
    FlextInfraUtilitiesPyrefly,
    FlextInfraUtilitiesQualifiedNames,
    FlextInfraUtilitiesRefactor,
    FlextInfraUtilitiesRefactorCensus,
    FlextInfraUtilitiesRefactorNamespaceCommon,
    FlextInfraUtilitiesRefactorNamespaceFlext,
    FlextInfraUtilitiesRefactorNamespaceMoves,
    FlextInfraUtilitiesRelease,
    FlextInfraUtilitiesRepository,
    FlextInfraUtilitiesResourceLimits,
    FlextInfraUtilitiesRopeAnalysis,
    FlextInfraUtilitiesRopeAnalysisIntrospection,
    FlextInfraUtilitiesRopeAnalysisWorkspace,
    FlextInfraUtilitiesRopeClassMove,
    FlextInfraUtilitiesRopeCore,
    FlextInfraUtilitiesRopeHelpers,
    FlextInfraUtilitiesRopeImports,
    FlextInfraUtilitiesRopeInventory,
    FlextInfraUtilitiesRopeModulePatch,
    FlextInfraUtilitiesRopeRuntime,
    FlextInfraUtilitiesRopeSource,
    FlextInfraUtilitiesRopeStructure,
    FlextInfraUtilitiesSemanticCutover,
    FlextInfraUtilitiesTransformerHeader,
    FlextInfraUtilitiesVersioning,
    FlextInfraUtilitiesWorkspaceFingerprint,
    FlextInfraUtilitiesWorkspaceManifest,
    FlextInfraWorktreeLifecycle,
    FlextInfraWorktreeProvisioning,
)


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
        FlextInfraUtilitiesCodegenPathCutover,
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
        FlextInfraUtilitiesDeferredSelfReferenceRewrite,
        FlextInfraUtilitiesGit,
        FlextInfraUtilitiesIteration,
        FlextInfraUtilitiesLintRecipes,
        FlextInfraUtilitiesLogParser,
        FlextInfraUtilitiesManagedConflicts,
        FlextInfraUtilitiesSemanticCutover,
        FlextInfraUtilitiesProtectedEdit,
        FlextInfraUtilitiesRefactor,
        FlextInfraUtilitiesRefactorCensus,
        FlextInfraUtilitiesRefactorNamespaceFlext,
        FlextInfraUtilitiesRefactorNamespaceCommon,
        FlextInfraUtilitiesRefactorNamespaceMoves,
        FlextInfraUtilitiesRelease,
        FlextInfraUtilitiesRepository,
        FlextInfraUtilitiesVersioning,
        FlextInfraWorktreeLifecycle,
        FlextInfraWorktreeProvisioning,
        FlextInfraUtilitiesWorkspaceFingerprint,
        FlextInfraUtilitiesCodemodProject,
        FlextInfraUtilitiesPrivateImportAncestry,
        FlextInfraUtilitiesPrivateImportFacades,
    ):
        """Infrastructure-domain utilities - all methods exposed directly."""


u = FlextInfraUtilities

__all__: list[str] = ["FlextInfraUtilities", "u"]
