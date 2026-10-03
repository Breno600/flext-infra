# AUTO-GENERATED FILE — Regenerate with: make gen
"""Tests package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_tests import api, d, e, h, r, td, tf, tk, tm, x

    from tests import fixtures, integration, refactor, unit
    from tests.base import TestsFlextInfraServiceBase, s
    from tests.constants import TestsFlextInfraConstants, c
    from tests.constants_scan import TestsFlextInfraConstantsScanMixin
    from tests.models import TestsFlextInfraModels, m
    from tests.protocols import TestsFlextInfraProtocols, p
    from tests.typings import TestsFlextInfraTypes, t
    from tests.utilities import TestsFlextInfraUtilities, u
    from tests.utilities_codegen import TestsFlextInfraUtilitiesCodegenMixin
    from tests.utilities_deps import TestsFlextInfraUtilitiesDepsMixin
    from tests.utilities_fixture_docs import TestsFlextInfraUtilitiesDocsFixtureMixin
    from tests.utilities_fixture_project import (
        TestsFlextInfraUtilitiesProjectFixtureMixin,
    )
    from tests.utilities_fixture_tooling import (
        TestsFlextInfraUtilitiesToolingFixtureMixin,
    )
    from tests.utilities_fixture_workspace import (
        TestsFlextInfraUtilitiesWorkspaceFixtureMixin,
    )
    from tests.utilities_gates import TestsFlextInfraUtilitiesGatesMixin
    from tests.utilities_git import TestsFlextInfraUtilitiesGitMixin
    from tests.utilities_promoted import TestsFlextInfraUtilitiesPromotedMixin
    from tests.utilities_release import TestsFlextInfraUtilitiesReleaseMixin
    from tests.utilities_toml import TestsFlextInfraUtilitiesTomlMixin
    from tests.utilities_workspace_env import TestsFlextInfraUtilitiesWorkspaceEnvMixin

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
    "TestsFlextInfraUtilitiesTomlMixin",
    "TestsFlextInfraUtilitiesToolingFixtureMixin",
    "TestsFlextInfraUtilitiesWorkspaceEnvMixin",
    "TestsFlextInfraUtilitiesWorkspaceFixtureMixin",
    "api",
    "c",
    "d",
    "e",
    "fixtures",
    "h",
    "integration",
    "m",
    "p",
    "r",
    "refactor",
    "s",
    "t",
    "td",
    "tf",
    "tk",
    "tm",
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
            ".fixtures": ("fixtures",),
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
            ".utilities_toml": ("TestsFlextInfraUtilitiesTomlMixin",),
            ".utilities_workspace_env": ("TestsFlextInfraUtilitiesWorkspaceEnvMixin",),
            "flext_tests": ("api", "d", "e", "h", "r", "td", "tf", "tk", "tm", "x"),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
