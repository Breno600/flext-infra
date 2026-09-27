# AUTO-GENERATED FILE — Regenerate with: make gen
"""Tests package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_cli import cli
    from flext_infra import docs_main, infra, main
    from flext_tests import (
        api,
        config,
        core,
        d,
        e,
        h,
        install_local_packages,
        lazy_attribute,
        load_infra_report,
        r,
        services,
        settings,
        td,
        tf,
        tk,
        tm,
        tv,
        x,
    )

    from . import integration, refactor, unit
    from .base import TestsFlextInfraServiceBase, TestsFlextInfraServiceBase as s
    from .constants import TestsFlextInfraConstants, c
    from .constants_scan import TestsFlextInfraConstantsScanMixin
    from .models import TestsFlextInfraModels, m
    from .protocols import TestsFlextInfraProtocols, p
    from .typings import TestsFlextInfraTypes, t
    from .utilities import TestsFlextInfraUtilities, u
    from .utilities_codegen import TestsFlextInfraUtilitiesCodegenMixin
    from .utilities_deps import TestsFlextInfraUtilitiesDepsMixin
    from .utilities_fixture_docs import TestsFlextInfraUtilitiesDocsFixtureMixin
    from .utilities_fixture_project import TestsFlextInfraUtilitiesProjectFixtureMixin
    from .utilities_fixture_tooling import TestsFlextInfraUtilitiesToolingFixtureMixin
    from .utilities_fixture_workspace import (
        TestsFlextInfraUtilitiesWorkspaceFixtureMixin,
    )
    from .utilities_gates import TestsFlextInfraUtilitiesGatesMixin
    from .utilities_git import TestsFlextInfraUtilitiesGitMixin
    from .utilities_promoted import TestsFlextInfraUtilitiesPromotedMixin
    from .utilities_release import TestsFlextInfraUtilitiesReleaseMixin
    from .utilities_replay import TestsFlextInfraUtilitiesReplayRunnerMixin
    from .utilities_replay_sequence import TestsFlextInfraUtilitiesReplaySequenceMixin
    from .utilities_toml import TestsFlextInfraUtilitiesTomlMixin
    from .utilities_workspace_env import TestsFlextInfraUtilitiesWorkspaceEnvMixin


__all__: tuple[str, ...] = (
    "TestsFlextInfraConstants",
    "TestsFlextInfraConstantsScanMixin",
    "TestsFlextInfraModels",
    "TestsFlextInfraProtocols",
    "TestsFlextInfraServiceBase",
    "TestsFlextInfraTypes",
    "TestsFlextInfraUtilities",
    "TestsFlextInfraUtilitiesCodegenMixin",
    "TestsFlextInfraUtilitiesDepsMixin",
    "TestsFlextInfraUtilitiesDocsFixtureMixin",
    "TestsFlextInfraUtilitiesGatesMixin",
    "TestsFlextInfraUtilitiesGitMixin",
    "TestsFlextInfraUtilitiesProjectFixtureMixin",
    "TestsFlextInfraUtilitiesPromotedMixin",
    "TestsFlextInfraUtilitiesReleaseMixin",
    "TestsFlextInfraUtilitiesReplayRunnerMixin",
    "TestsFlextInfraUtilitiesReplaySequenceMixin",
    "TestsFlextInfraUtilitiesTomlMixin",
    "TestsFlextInfraUtilitiesToolingFixtureMixin",
    "TestsFlextInfraUtilitiesWorkspaceEnvMixin",
    "TestsFlextInfraUtilitiesWorkspaceFixtureMixin",
    "api",
    "c",
    "cli",
    "config",
    "core",
    "d",
    "docs_main",
    "e",
    "h",
    "infra",
    "install_local_packages",
    "integration",
    "lazy_attribute",
    "load_infra_report",
    "m",
    "main",
    "p",
    "r",
    "refactor",
    "s",
    "services",
    "settings",
    "t",
    "td",
    "tf",
    "tk",
    "tm",
    "tv",
    "u",
    "unit",
    "x",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".base": ("TestsFlextInfraServiceBase", "s"),
            ".constants": ("TestsFlextInfraConstants", "c"),
            ".constants_scan": ("TestsFlextInfraConstantsScanMixin",),
            ".integration": ("integration",),
            ".models": ("TestsFlextInfraModels", "m"),
            ".protocols": ("TestsFlextInfraProtocols", "p"),
            ".refactor": ("refactor",),
            ".typings": ("TestsFlextInfraTypes", "t"),
            ".unit": ("unit",),
            ".utilities": ("TestsFlextInfraUtilities", "u"),
            ".utilities_codegen": ("TestsFlextInfraUtilitiesCodegenMixin",),
            ".utilities_deps": ("TestsFlextInfraUtilitiesDepsMixin",),
            ".utilities_fixture_docs": ("TestsFlextInfraUtilitiesDocsFixtureMixin",),
            ".utilities_fixture_project": (
                "TestsFlextInfraUtilitiesProjectFixtureMixin",
            ),
            ".utilities_fixture_tooling": (
                "TestsFlextInfraUtilitiesToolingFixtureMixin",
            ),
            ".utilities_fixture_workspace": (
                "TestsFlextInfraUtilitiesWorkspaceFixtureMixin",
            ),
            ".utilities_gates": ("TestsFlextInfraUtilitiesGatesMixin",),
            ".utilities_git": ("TestsFlextInfraUtilitiesGitMixin",),
            ".utilities_promoted": ("TestsFlextInfraUtilitiesPromotedMixin",),
            ".utilities_release": ("TestsFlextInfraUtilitiesReleaseMixin",),
            ".utilities_replay": ("TestsFlextInfraUtilitiesReplayRunnerMixin",),
            ".utilities_replay_sequence": (
                "TestsFlextInfraUtilitiesReplaySequenceMixin",
            ),
            ".utilities_toml": ("TestsFlextInfraUtilitiesTomlMixin",),
            ".utilities_workspace_env": ("TestsFlextInfraUtilitiesWorkspaceEnvMixin",),
            "flext_cli": ("cli",),
            "flext_infra": ("docs_main", "infra", "main"),
            "flext_tests": (
                "api",
                "config",
                "core",
                "d",
                "e",
                "h",
                "install_local_packages",
                "lazy_attribute",
                "load_infra_report",
                "r",
                "services",
                "settings",
                "td",
                "tf",
                "tk",
                "tm",
                "tv",
                "x",
            ),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
