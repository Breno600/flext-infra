# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Models package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from . import _git
    from ._git.identity import FlextInfraModelsGitIdentity
    from .base import FlextInfraModelsBase
    from .census import FlextInfraModelsCensus
    from .check import FlextInfraModelsCheck
    from .codegen import FlextInfraModelsCodegen
    from .codegen_render import FlextInfraModelsCodegenRender
    from .codemod import FlextInfraModelsCodemod
    from .config import FlextInfraConfigModels
    from .deps import FlextInfraModelsDeps
    from .deps_toml import FlextInfraModelsDepsToml
    from .deps_tool_config import FlextInfraModelsDepsToolSettings
    from .deps_tool_config_linters import FlextInfraModelsDepsToolConfigLinters
    from .deps_tool_config_project import (
        FlextInfraModelsDepsToolConfigProject,
        FlextInfraModelsDepsToolConfigProjectArtifacts,
        FlextInfraModelsDepsToolConfigProjectMise,
        FlextInfraModelsDepsToolConfigProjectRuff,
    )
    from .deps_tool_config_type_checkers import (
        FlextInfraModelsDepsToolConfigTypeCheckers,
    )
    from .docs import FlextInfraModelsDocs
    from .docs_generation import FlextInfraModelsDocsGeneration
    from .duplication import FlextInfraModelsDuplication
    from .enforcement import FlextInfraModelsEnforcement
    from .gates import FlextInfraModelsGates
    from .git import FlextInfraModelsGit
    from .layout import FlextInfraModelsLayout
    from .mixins import FlextInfraModelsMixins
    from .promoted import FlextInfraModelsPromoted
    from .refactor import FlextInfraModelsRefactor
    from .refactor_ast_grep import FlextInfraModelsRefactorGrep
    from .refactor_census import FlextInfraModelsRefactorCensus
    from .refactor_namespace_enforcer import FlextInfraModelsNamespaceEnforcer
    from .refactor_violations import FlextInfraModelsRefactorViolations
    from .release import FlextInfraModelsRelease
    from .rope import FlextInfraModelsRope
    from .rope_move import FlextInfraModelsRopeMove
    from .rope_rules import FlextInfraModelsRopeRules
    from .scan import FlextInfraModelsScan
    from .settings import FlextInfraSettingsModels
    from .testmon import FlextInfraModelsTestmon
    from .transformers import FlextInfraModelsTransformers
    from .validate import FlextInfraModelsCore
    from .workspace import FlextInfraModelsWorkspace
    from .worktree import FlextInfraModelsWorktree
__all__: tuple[str, ...] = (
    "FlextInfraConfigModels",
    "FlextInfraModelsBase",
    "FlextInfraModelsCensus",
    "FlextInfraModelsCheck",
    "FlextInfraModelsCodegen",
    "FlextInfraModelsCodegenRender",
    "FlextInfraModelsCodemod",
    "FlextInfraModelsCore",
    "FlextInfraModelsDeps",
    "FlextInfraModelsDepsToml",
    "FlextInfraModelsDepsToolConfigLinters",
    "FlextInfraModelsDepsToolConfigProject",
    "FlextInfraModelsDepsToolConfigProjectArtifacts",
    "FlextInfraModelsDepsToolConfigProjectMise",
    "FlextInfraModelsDepsToolConfigProjectRuff",
    "FlextInfraModelsDepsToolConfigTypeCheckers",
    "FlextInfraModelsDepsToolSettings",
    "FlextInfraModelsDocs",
    "FlextInfraModelsDocsGeneration",
    "FlextInfraModelsDuplication",
    "FlextInfraModelsEnforcement",
    "FlextInfraModelsGates",
    "FlextInfraModelsGit",
    "FlextInfraModelsGitIdentity",
    "FlextInfraModelsLayout",
    "FlextInfraModelsMixins",
    "FlextInfraModelsNamespaceEnforcer",
    "FlextInfraModelsPromoted",
    "FlextInfraModelsRefactor",
    "FlextInfraModelsRefactorCensus",
    "FlextInfraModelsRefactorGrep",
    "FlextInfraModelsRefactorViolations",
    "FlextInfraModelsRelease",
    "FlextInfraModelsRope",
    "FlextInfraModelsRopeMove",
    "FlextInfraModelsRopeRules",
    "FlextInfraModelsScan",
    "FlextInfraModelsTestmon",
    "FlextInfraModelsTransformers",
    "FlextInfraModelsWorkspace",
    "FlextInfraModelsWorktree",
    "FlextInfraSettingsModels",
    "_git",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._git": ("_git",),
            "._git.identity": ("FlextInfraModelsGitIdentity",),
            ".base": ("FlextInfraModelsBase",),
            ".census": ("FlextInfraModelsCensus",),
            ".check": ("FlextInfraModelsCheck",),
            ".codegen": ("FlextInfraModelsCodegen",),
            ".codegen_render": ("FlextInfraModelsCodegenRender",),
            ".codemod": ("FlextInfraModelsCodemod",),
            ".config": ("FlextInfraConfigModels",),
            ".deps": ("FlextInfraModelsDeps",),
            ".deps_toml": ("FlextInfraModelsDepsToml",),
            ".deps_tool_config": ("FlextInfraModelsDepsToolSettings",),
            ".deps_tool_config_linters": ("FlextInfraModelsDepsToolConfigLinters",),
            ".deps_tool_config_project": (
                "FlextInfraModelsDepsToolConfigProject",
                "FlextInfraModelsDepsToolConfigProjectArtifacts",
                "FlextInfraModelsDepsToolConfigProjectMise",
                "FlextInfraModelsDepsToolConfigProjectRuff",
            ),
            ".deps_tool_config_type_checkers": (
                "FlextInfraModelsDepsToolConfigTypeCheckers",
            ),
            ".docs": ("FlextInfraModelsDocs",),
            ".docs_generation": ("FlextInfraModelsDocsGeneration",),
            ".duplication": ("FlextInfraModelsDuplication",),
            ".enforcement": ("FlextInfraModelsEnforcement",),
            ".gates": ("FlextInfraModelsGates",),
            ".git": ("FlextInfraModelsGit",),
            ".layout": ("FlextInfraModelsLayout",),
            ".mixins": ("FlextInfraModelsMixins",),
            ".promoted": ("FlextInfraModelsPromoted",),
            ".refactor": ("FlextInfraModelsRefactor",),
            ".refactor_ast_grep": ("FlextInfraModelsRefactorGrep",),
            ".refactor_census": ("FlextInfraModelsRefactorCensus",),
            ".refactor_namespace_enforcer": ("FlextInfraModelsNamespaceEnforcer",),
            ".refactor_violations": ("FlextInfraModelsRefactorViolations",),
            ".release": ("FlextInfraModelsRelease",),
            ".rope": ("FlextInfraModelsRope",),
            ".rope_move": ("FlextInfraModelsRopeMove",),
            ".rope_rules": ("FlextInfraModelsRopeRules",),
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
