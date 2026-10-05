# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Models package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._models import _codegen, _config, _git
    from flext_infra._models._codegen.base import FlextInfraCodegen
    from flext_infra._models._codegen.fix import FlextInfraModelsCodegenFixModels
    from flext_infra._models._codegen.journal import (
        FlextInfraModelsCodegenJournalModels,
    )
    from flext_infra._models._codegen.lazy_init import (
        FlextInfraModelsCodegenLazyInitModels,
    )
    from flext_infra._models._codegen.pipeline import (
        FlextInfraModelsCodegenPipelineModels,
    )
    from flext_infra._models._codegen.scaffold import (
        FlextInfraModelsCodegenScaffoldModels,
    )
    from flext_infra._models._codegen.transaction import (
        FlextInfraModelsCodegenTransactionModels,
    )
    from flext_infra._models._config.artifact import FlextInfraConfigModelsArtifact
    from flext_infra._models._config.base import FlextInfraConfigModels
    from flext_infra._models._config.beads import FlextInfraConfigModelsBeads
    from flext_infra._models._config.contexts import FlextInfraConfigModelsContexts
    from flext_infra._models._config.contract import FlextInfraConfigModelsContract
    from flext_infra._models._config.external_cache import (
        FlextInfraExternalCacheDirectorySpec,
    )
    from flext_infra._models._config.make import FlextInfraConfigModelsMake
    from flext_infra._models._config.provider import FlextInfraConfigModelsProvider
    from flext_infra._models._config.release import FlextInfraConfigModelsRelease
    from flext_infra._models._config.render import FlextInfraConfigModelsRender
    from flext_infra._models._config.root import FlextInfraConfigModelsRoot
    from flext_infra._models._config.scaffold import FlextInfraConfigModelsScaffold
    from flext_infra._models._config.static import FlextInfraConfigModelsStatic
    from flext_infra._models._config.templates import FlextInfraConfigModelsTemplates
    from flext_infra._models._config.workspace import FlextInfraConfigModelsWorkspace
    from flext_infra._models._git.identity import FlextInfraModelsGitIdentity
    from flext_infra._models._git.worktree_facts import FlextInfraModelsGitWorktreeFacts
    from flext_infra._models._git.worktree_state import FlextInfraModelsGitWorktreeState
    from flext_infra._models.base import FlextInfraModelsBase
    from flext_infra._models.census import FlextInfraModelsCensus
    from flext_infra._models.check import FlextInfraModelsCheck
    from flext_infra._models.codegen_render import FlextInfraModelsCodegenRender
    from flext_infra._models.codegen_toolchain import FlextInfraModelsCodegenToolchain
    from flext_infra._models.codemod import FlextInfraModelsCodemod
    from flext_infra._models.deps import FlextInfraModelsDeps
    from flext_infra._models.deps_toml import FlextInfraModelsDepsToml
    from flext_infra._models.deps_tool_config import FlextInfraModelsDepsToolConfig
    from flext_infra._models.deps_tool_config_linters import (
        FlextInfraModelsDepsToolConfigLinters,
    )
    from flext_infra._models.deps_tool_config_project import (
        FlextInfraModelsDepsToolConfigProject,
    )
    from flext_infra._models.deps_tool_config_project_artifacts import (
        FlextInfraModelsDepsToolConfigProjectArtifacts,
    )
    from flext_infra._models.deps_tool_config_project_gitignore import (
        FlextInfraModelsDepsToolConfigProjectGitignore,
    )
    from flext_infra._models.deps_tool_config_project_mise import (
        FlextInfraModelsDepsToolConfigProjectMise,
    )
    from flext_infra._models.deps_tool_config_type_checkers import (
        FlextInfraModelsDepsToolConfigTypeCheckers,
    )
    from flext_infra._models.docs import FlextInfraModelsDocs
    from flext_infra._models.docs_collection import FlextInfraModelsDocsCollection
    from flext_infra._models.docs_generation import FlextInfraModelsDocsGeneration
    from flext_infra._models.duplication import FlextInfraModelsDuplication
    from flext_infra._models.gates import FlextInfraModelsGates
    from flext_infra._models.git import FlextInfraModelsGit
    from flext_infra._models.layout import FlextInfraModelsLayout
    from flext_infra._models.mise_toolchain import FlextInfraModelsMiseToolchain
    from flext_infra._models.mise_toolchain_base import (
        FlextInfraModelsMiseToolchainBase,
    )
    from flext_infra._models.mixins import FlextInfraModelsMixins
    from flext_infra._models.promoted import FlextInfraModelsPromoted
    from flext_infra._models.refactor import FlextInfraModelsRefactor
    from flext_infra._models.refactor_ast_grep import FlextInfraModelsRefactorGrep
    from flext_infra._models.refactor_namespace_enforcer import (
        FlextInfraModelsNamespaceEnforcer,
    )
    from flext_infra._models.release import FlextInfraModelsRelease
    from flext_infra._models.rope import FlextInfraModelsRope
    from flext_infra._models.rope_move import FlextInfraModelsRopeMove
    from flext_infra._models.scan import FlextInfraModelsScan
    from flext_infra._models.settings import FlextInfraSettingsModels
    from flext_infra._models.sonarcloud import FlextInfraModelsSonarcloud
    from flext_infra._models.testmon import FlextInfraModelsTestmon
    from flext_infra._models.transformers import FlextInfraModelsTransformers
    from flext_infra._models.validate import FlextInfraModelsCore
    from flext_infra._models.workspace import FlextInfraModelsWorkspace
    from flext_infra._models.worktree import FlextInfraModelsWorktree


__all__: tuple[str, ...] = (
    "FlextInfraCodegen",
    "FlextInfraConfigModels",
    "FlextInfraConfigModelsArtifact",
    "FlextInfraConfigModelsBeads",
    "FlextInfraConfigModelsContexts",
    "FlextInfraConfigModelsContract",
    "FlextInfraConfigModelsMake",
    "FlextInfraConfigModelsProvider",
    "FlextInfraConfigModelsRelease",
    "FlextInfraConfigModelsRender",
    "FlextInfraConfigModelsRoot",
    "FlextInfraConfigModelsScaffold",
    "FlextInfraConfigModelsStatic",
    "FlextInfraConfigModelsTemplates",
    "FlextInfraConfigModelsWorkspace",
    "FlextInfraExternalCacheDirectorySpec",
    "FlextInfraModelsBase",
    "FlextInfraModelsCensus",
    "FlextInfraModelsCheck",
    "FlextInfraModelsCodegenFixModels",
    "FlextInfraModelsCodegenJournalModels",
    "FlextInfraModelsCodegenLazyInitModels",
    "FlextInfraModelsCodegenPipelineModels",
    "FlextInfraModelsCodegenRender",
    "FlextInfraModelsCodegenScaffoldModels",
    "FlextInfraModelsCodegenToolchain",
    "FlextInfraModelsCodegenTransactionModels",
    "FlextInfraModelsCodemod",
    "FlextInfraModelsCore",
    "FlextInfraModelsDeps",
    "FlextInfraModelsDepsToml",
    "FlextInfraModelsDepsToolConfig",
    "FlextInfraModelsDepsToolConfigLinters",
    "FlextInfraModelsDepsToolConfigProject",
    "FlextInfraModelsDepsToolConfigProjectArtifacts",
    "FlextInfraModelsDepsToolConfigProjectGitignore",
    "FlextInfraModelsDepsToolConfigProjectMise",
    "FlextInfraModelsDepsToolConfigTypeCheckers",
    "FlextInfraModelsDocs",
    "FlextInfraModelsDocsCollection",
    "FlextInfraModelsDocsGeneration",
    "FlextInfraModelsDuplication",
    "FlextInfraModelsGates",
    "FlextInfraModelsGit",
    "FlextInfraModelsGitIdentity",
    "FlextInfraModelsGitWorktreeFacts",
    "FlextInfraModelsGitWorktreeState",
    "FlextInfraModelsLayout",
    "FlextInfraModelsMiseToolchain",
    "FlextInfraModelsMiseToolchainBase",
    "FlextInfraModelsMixins",
    "FlextInfraModelsNamespaceEnforcer",
    "FlextInfraModelsPromoted",
    "FlextInfraModelsRefactor",
    "FlextInfraModelsRefactorGrep",
    "FlextInfraModelsRelease",
    "FlextInfraModelsRope",
    "FlextInfraModelsRopeMove",
    "FlextInfraModelsScan",
    "FlextInfraModelsSonarcloud",
    "FlextInfraModelsTestmon",
    "FlextInfraModelsTransformers",
    "FlextInfraModelsWorkspace",
    "FlextInfraModelsWorktree",
    "FlextInfraSettingsModels",
    "_codegen",
    "_config",
    "_git",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraCodegen": "._codegen.base",
        "FlextInfraConfigModels": "._config.base",
        "FlextInfraConfigModelsArtifact": "._config.artifact",
        "FlextInfraConfigModelsBeads": "._config.beads",
        "FlextInfraConfigModelsContexts": "._config.contexts",
        "FlextInfraConfigModelsContract": "._config.contract",
        "FlextInfraConfigModelsMake": "._config.make",
        "FlextInfraConfigModelsProvider": "._config.provider",
        "FlextInfraConfigModelsRelease": "._config.release",
        "FlextInfraConfigModelsRender": "._config.render",
        "FlextInfraConfigModelsRoot": "._config.root",
        "FlextInfraConfigModelsScaffold": "._config.scaffold",
        "FlextInfraConfigModelsStatic": "._config.static",
        "FlextInfraConfigModelsTemplates": "._config.templates",
        "FlextInfraConfigModelsWorkspace": "._config.workspace",
        "FlextInfraExternalCacheDirectorySpec": "._config.external_cache",
        "FlextInfraModelsBase": ".base",
        "FlextInfraModelsCensus": ".census",
        "FlextInfraModelsCheck": ".check",
        "FlextInfraModelsCodegenFixModels": "._codegen.fix",
        "FlextInfraModelsCodegenJournalModels": "._codegen.journal",
        "FlextInfraModelsCodegenLazyInitModels": "._codegen.lazy_init",
        "FlextInfraModelsCodegenPipelineModels": "._codegen.pipeline",
        "FlextInfraModelsCodegenRender": ".codegen_render",
        "FlextInfraModelsCodegenScaffoldModels": "._codegen.scaffold",
        "FlextInfraModelsCodegenToolchain": ".codegen_toolchain",
        "FlextInfraModelsCodegenTransactionModels": "._codegen.transaction",
        "FlextInfraModelsCodemod": ".codemod",
        "FlextInfraModelsCore": ".validate",
        "FlextInfraModelsDeps": ".deps",
        "FlextInfraModelsDepsToml": ".deps_toml",
        "FlextInfraModelsDepsToolConfig": ".deps_tool_config",
        "FlextInfraModelsDepsToolConfigLinters": ".deps_tool_config_linters",
        "FlextInfraModelsDepsToolConfigProject": ".deps_tool_config_project",
        "FlextInfraModelsDepsToolConfigProjectArtifacts": (
            ".deps_tool_config_project_artifacts"
        ),
        "FlextInfraModelsDepsToolConfigProjectGitignore": (
            ".deps_tool_config_project_gitignore"
        ),
        "FlextInfraModelsDepsToolConfigProjectMise": ".deps_tool_config_project_mise",
        "FlextInfraModelsDepsToolConfigTypeCheckers": ".deps_tool_config_type_checkers",
        "FlextInfraModelsDocs": ".docs",
        "FlextInfraModelsDocsCollection": ".docs_collection",
        "FlextInfraModelsDocsGeneration": ".docs_generation",
        "FlextInfraModelsDuplication": ".duplication",
        "FlextInfraModelsGates": ".gates",
        "FlextInfraModelsGit": ".git",
        "FlextInfraModelsGitIdentity": "._git.identity",
        "FlextInfraModelsGitWorktreeFacts": "._git.worktree_facts",
        "FlextInfraModelsGitWorktreeState": "._git.worktree_state",
        "FlextInfraModelsLayout": ".layout",
        "FlextInfraModelsMiseToolchain": ".mise_toolchain",
        "FlextInfraModelsMiseToolchainBase": ".mise_toolchain_base",
        "FlextInfraModelsMixins": ".mixins",
        "FlextInfraModelsNamespaceEnforcer": ".refactor_namespace_enforcer",
        "FlextInfraModelsPromoted": ".promoted",
        "FlextInfraModelsRefactor": ".refactor",
        "FlextInfraModelsRefactorGrep": ".refactor_ast_grep",
        "FlextInfraModelsRelease": ".release",
        "FlextInfraModelsRope": ".rope",
        "FlextInfraModelsRopeMove": ".rope_move",
        "FlextInfraModelsScan": ".scan",
        "FlextInfraModelsSonarcloud": ".sonarcloud",
        "FlextInfraModelsTestmon": ".testmon",
        "FlextInfraModelsTransformers": ".transformers",
        "FlextInfraModelsWorkspace": ".workspace",
        "FlextInfraModelsWorktree": ".worktree",
        "FlextInfraSettingsModels": ".settings",
        "_codegen": "._codegen",
        "_config": "._config",
        "_git": "._git",
    }),
    public_exports=__all__,
)
