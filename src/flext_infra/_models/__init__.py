# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Models package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from . import _codegen, _config, _git
    from ._codegen.fix import FlextInfraModelsCodegenFixModels
    from ._codegen.journal import FlextInfraModelsCodegenJournalModels
    from ._codegen.lazy_init import FlextInfraModelsCodegenLazyInitModels
    from ._codegen.pipeline import FlextInfraModelsCodegenPipelineModels
    from ._codegen.scaffold import FlextInfraModelsCodegenScaffoldModels
    from ._codegen.transaction import FlextInfraModelsCodegenTransactionModels
    from ._config.artifact import FlextInfraConfigModelsArtifact
    from ._config.beads import FlextInfraConfigModelsBeads
    from ._config.contexts import FlextInfraConfigModelsContexts
    from ._config.contract import FlextInfraConfigModelsContract
    from ._config.make import FlextInfraConfigModelsMake
    from ._config.provider import FlextInfraConfigModelsProvider
    from ._config.release import FlextInfraConfigModelsRelease
    from ._config.render import FlextInfraConfigModelsRender
    from ._config.scaffold import FlextInfraConfigModelsScaffold
    from ._config.static import FlextInfraConfigModelsStatic
    from ._config.templates import FlextInfraConfigModelsTemplates
    from ._config.workspace import FlextInfraConfigModelsWorkspace
    from ._defaults import FlextInfraModelsDefaults
    from ._git.identity import FlextInfraModelsGitIdentity
    from .base import FlextInfraModelsBase
    from .census import FlextInfraModelsCensus
    from .check import FlextInfraModelsCheck
    from ._codegen import FlextInfraModelsCodegen
    from ._codegen.journal import FlextInfraModelsCodegenJournal
    from .codegen_render import FlextInfraModelsCodegenRender
    from .codegen_toolchain import FlextInfraModelsCodegenToolchain
    from .codemod import FlextInfraModelsCodemod
    from ._config import FlextInfraConfigModels
    from .deps import FlextInfraModelsDeps
    from .deps_toml import FlextInfraModelsDepsToml
    from .deps_tool_config import FlextInfraModelsDepsToolSettings
    from .deps_tool_config_linters import FlextInfraModelsDepsToolConfigLinters
    from .deps_tool_config_project import FlextInfraModelsDepsToolConfigProject
    from .deps_tool_config_type_checkers import (
        FlextInfraModelsDepsToolConfigTypeCheckers,
    )
    from .docs import FlextInfraModelsDocs
    from .docs_collection import FlextInfraModelsDocsCollection
    from .docs_generation import FlextInfraModelsDocsGeneration
    from .duplication import FlextInfraModelsDuplication
    from .enforcement import FlextInfraModelsEnforcement
    from .gates import FlextInfraModelsGates
    from .git import FlextInfraModelsGit
    from .layout import FlextInfraModelsLayout
    from .mise_toolchain import FlextInfraModelsMiseToolchain
    from .mixins import FlextInfraModelsMixins
    from .promoted import FlextInfraModelsPromoted
    from .refactor import FlextInfraModelsRefactor
    from .refactor_ast_grep import FlextInfraModelsRefactorGrep
    from .refactor_namespace_enforcer import FlextInfraModelsNamespaceEnforcer
    from .release import FlextInfraModelsRelease
    from .rope import FlextInfraModelsRope
    from .rope_move import FlextInfraModelsRopeMove
    from .scan import FlextInfraModelsScan
    from .settings import FlextInfraSettingsModels
    from .testmon import FlextInfraModelsTestmon
    from .transformers import FlextInfraModelsTransformers
    from .validate import FlextInfraModelsCore
    from .workspace import FlextInfraModelsWorkspace
    from .worktree import FlextInfraModelsWorktree
__all__: t.VariadicTuple[str] = (
    "FlextInfraConfigModels",
    "FlextInfraConfigModelsArtifact",
    "FlextInfraConfigModelsBeads",
    "FlextInfraConfigModelsContexts",
    "FlextInfraConfigModelsContract",
    "FlextInfraConfigModelsMake",
    "FlextInfraConfigModelsProvider",
    "FlextInfraConfigModelsRelease",
    "FlextInfraConfigModelsRender",
    "FlextInfraConfigModelsScaffold",
    "FlextInfraConfigModelsStatic",
    "FlextInfraConfigModelsTemplates",
    "FlextInfraConfigModelsWorkspace",
    "FlextInfraModelsBase",
    "FlextInfraModelsCensus",
    "FlextInfraModelsCheck",
    "FlextInfraModelsCodegen",
    "FlextInfraModelsCodegenFixModels",
    "FlextInfraModelsCodegenJournal",
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
    "FlextInfraModelsDepsToolConfigLinters",
    "FlextInfraModelsDepsToolConfigProject",
    "FlextInfraModelsDepsToolConfigTypeCheckers",
    "FlextInfraModelsDepsToolSettings",
    "FlextInfraModelsDocs",
    "FlextInfraModelsDocsCollection",
    "FlextInfraModelsDocsGeneration",
    "FlextInfraModelsDuplication",
    "FlextInfraModelsEnforcement",
    "FlextInfraModelsGates",
    "FlextInfraModelsGit",
    "FlextInfraModelsGitIdentity",
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
    "FlextInfraModelsTestmon",
    "FlextInfraModelsTransformers",
    "FlextInfraModelsWorkspace",
    "FlextInfraModelsWorktree",
    "FlextInfraSettingsModels",
    "ImmutableEmptyMapping",
    "_codegen",
    "_config",
    "_git",
    "immutable_empty_mapping",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._codegen": ("_codegen",),
            "._codegen.fix": ("FlextInfraModelsCodegenFixModels",),
            "._codegen.journal": ("FlextInfraModelsCodegenJournalModels",),
            "._codegen.lazy_init": ("FlextInfraModelsCodegenLazyInitModels",),
            "._codegen.pipeline": ("FlextInfraModelsCodegenPipelineModels",),
            "._codegen.scaffold": ("FlextInfraModelsCodegenScaffoldModels",),
            "._codegen.transaction": ("FlextInfraModelsCodegenTransactionModels",),
            "._config": ("_config",),
            "._config.artifact": ("FlextInfraConfigModelsArtifact",),
            "._config.beads": ("FlextInfraConfigModelsBeads",),
            "._config.contexts": ("FlextInfraConfigModelsContexts",),
            "._config.contract": ("FlextInfraConfigModelsContract",),
            "._config.make": ("FlextInfraConfigModelsMake",),
            "._config.provider": ("FlextInfraConfigModelsProvider",),
            "._config.release": ("FlextInfraConfigModelsRelease",),
            "._config.render": ("FlextInfraConfigModelsRender",),
            "._config.scaffold": ("FlextInfraConfigModelsScaffold",),
            "._config.static": ("FlextInfraConfigModelsStatic",),
            "._config.templates": ("FlextInfraConfigModelsTemplates",),
            "._config.workspace": ("FlextInfraConfigModelsWorkspace",),
            "._defaults": ("FlextInfraModelsDefaults",),
            "._git": ("_git",),
            "._git.identity": ("FlextInfraModelsGitIdentity",),
            ".base": ("FlextInfraModelsBase",),
            ".census": ("FlextInfraModelsCensus",),
            ".check": ("FlextInfraModelsCheck",),
            "._codegen": ("FlextInfraModelsCodegen",),
            "._codegen.journal": ("FlextInfraModelsCodegenJournal",),
            ".codegen_render": ("FlextInfraModelsCodegenRender",),
            ".codegen_toolchain": ("FlextInfraModelsCodegenToolchain",),
            ".codemod": ("FlextInfraModelsCodemod",),
            "._config": ("FlextInfraConfigModels",),
            ".deps": ("FlextInfraModelsDeps",),
            ".deps_toml": ("FlextInfraModelsDepsToml",),
            ".deps_tool_config": ("FlextInfraModelsDepsToolSettings",),
            ".deps_tool_config_linters": ("FlextInfraModelsDepsToolConfigLinters",),
            ".deps_tool_config_project": ("FlextInfraModelsDepsToolConfigProject",),
            ".deps_tool_config_type_checkers": (
                "FlextInfraModelsDepsToolConfigTypeCheckers",
            ),
            ".docs": ("FlextInfraModelsDocs",),
            ".docs_collection": ("FlextInfraModelsDocsCollection",),
            ".docs_generation": ("FlextInfraModelsDocsGeneration",),
            ".duplication": ("FlextInfraModelsDuplication",),
            ".enforcement": ("FlextInfraModelsEnforcement",),
            ".gates": ("FlextInfraModelsGates",),
            ".git": ("FlextInfraModelsGit",),
            ".layout": ("FlextInfraModelsLayout",),
            ".mise_toolchain": ("FlextInfraModelsMiseToolchain",),
            ".mixins": ("FlextInfraModelsMixins",),
            ".promoted": ("FlextInfraModelsPromoted",),
            ".refactor": ("FlextInfraModelsRefactor",),
            "._codegen.journal": ("FlextInfraModelsCodegenJournal",),
            ".refactor_ast_grep": ("FlextInfraModelsRefactorGrep",),
            ".refactor_namespace_enforcer": ("FlextInfraModelsNamespaceEnforcer",),
            ".release": ("FlextInfraModelsRelease",),
            ".rope": ("FlextInfraModelsRope",),
            ".rope_move": ("FlextInfraModelsRopeMove",),
            ".scan": ("FlextInfraModelsScan",),
            ".settings": ("FlextInfraSettingsModels",),
            ".testmon": ("FlextInfraModelsTestmon",),
            ".transformers": ("FlextInfraModelsTransformers",),
            ".validate": ("FlextInfraModelsCore",),
            ".workspace": ("FlextInfraModelsWorkspace",),
            ".worktree": ("FlextInfraModelsWorktree",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
