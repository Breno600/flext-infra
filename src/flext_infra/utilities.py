"""Utilities facade for flext-infra.

Re-exports flext_core utilities and adds infrastructure-specific
utility namespaces. All methods are exposed directly as ``u.Infra.<method>()``.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import FlextCliUtilities

from flext_infra._utilities import FlextInfraUtilitiesDocsGithubLinks
from flext_infra._utilities import FlextInfraUtilitiesBase
from flext_infra._utilities import FlextInfraUtilitiesRefactorCensus
from flext_infra._utilities import FlextInfraUtilitiesCodegen
from flext_infra._utilities import FlextInfraUtilitiesCodegenFilePlan
from flext_infra._utilities import FlextInfraUtilitiesCodemodProject
from flext_infra._utilities import FlextInfraUtilitiesDeferredSelfReferenceRewrite
from flext_infra._utilities import FlextInfraUtilitiesDependencies
from flext_infra._utilities import FlextInfraUtilitiesDiscovery
from flext_infra._utilities import FlextInfraUtilitiesDocs
from flext_infra._utilities import FlextInfraUtilitiesDocsApi
from flext_infra._utilities import FlextInfraUtilitiesDocsAudit
from flext_infra._utilities import FlextInfraUtilitiesDocsBuild
from flext_infra._utilities import FlextInfraUtilitiesDocsContract
from flext_infra._utilities import FlextInfraUtilitiesDocsFix
from flext_infra._utilities import FlextInfraUtilitiesDocsGenerate
from flext_infra._utilities import FlextInfraUtilitiesDocsRender
from flext_infra._utilities import FlextInfraUtilitiesDocsScope
from flext_infra._utilities import FlextInfraUtilitiesDocsValidate
from flext_infra._utilities import FlextInfraUtilitiesGit
from flext_infra._utilities import FlextInfraUtilitiesIteration
from flext_infra._utilities import FlextInfraUtilitiesLintRecipes
from flext_infra._utilities import FlextInfraUtilitiesLogParser
from flext_infra._utilities import FlextInfraUtilitiesManagedConflicts
from flext_infra._utilities import FlextInfraUtilitiesCodegenNamespace
from flext_infra._utilities import FlextInfraUtilitiesRefactorNamespaceFlext
from flext_infra._utilities import FlextInfraUtilitiesRefactorNamespaceCommon
from flext_infra._utilities import FlextInfraUtilitiesRefactorNamespaceMoves
from flext_infra._utilities import FlextInfraUtilitiesNetwork
from flext_infra._utilities import FlextInfraUtilitiesPrivateImportAncestry
from flext_infra._utilities import FlextInfraUtilitiesPrivateImportFacades
from flext_infra._utilities import FlextInfraUtilitiesProcess
from flext_infra._utilities import FlextInfraUtilitiesProjectManagedArtifacts
from flext_infra._utilities import FlextInfraUtilitiesPromoted
from flext_infra._utilities import FlextInfraUtilitiesProtectedEdit
from flext_infra._utilities import FlextInfraUtilitiesPyprojectConform
from flext_infra._utilities import FlextInfraUtilitiesPyrefly
from flext_infra._utilities import FlextInfraUtilitiesQualifiedNames
from flext_infra._utilities import FlextInfraUtilitiesRefactor
from flext_infra._utilities import FlextInfraUtilitiesRelease
from flext_infra._utilities import FlextInfraUtilitiesRepository
from flext_infra._utilities import FlextInfraUtilitiesResourceLimits
from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysis
from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysisIntrospection
from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysisWorkspace
from flext_infra._utilities import FlextInfraUtilitiesRopeClassMove
from flext_infra._utilities import FlextInfraUtilitiesRopeCore
from flext_infra._utilities import FlextInfraUtilitiesRopeHelpers
from flext_infra._utilities import FlextInfraUtilitiesRopeImports
from flext_infra._utilities import FlextInfraUtilitiesRopeInventory
from flext_infra._utilities import FlextInfraUtilitiesRopeModulePatch
from flext_infra._utilities import FlextInfraUtilitiesRopeRuntime
from flext_infra._utilities import FlextInfraUtilitiesRopeSource
from flext_infra._utilities import FlextInfraUtilitiesRopeStructure
from flext_infra._utilities import FlextInfraUtilitiesSemanticCutover
from flext_infra._utilities import FlextInfraUtilitiesTransformerHeader
from flext_infra._utilities import FlextInfraUtilitiesVersioning
from flext_infra._utilities import FlextInfraUtilitiesWorkspaceFingerprint
from flext_infra._utilities import FlextInfraUtilitiesWorkspaceManifest
from flext_infra._utilities import FlextInfraWorktreeLifecycle
from flext_infra._utilities import FlextInfraWorktreeProvisioning


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
