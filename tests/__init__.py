# AUTO-GENERATED FILE — Regenerate with: make gen
"""Tests package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

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

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "TestsFlextInfraConstants": (".constants", "TestsFlextInfraConstants"),
        "TestsFlextInfraConstantsScanMixin": (
            ".constants_scan",
            "TestsFlextInfraConstantsScanMixin",
        ),
        "TestsFlextInfraModels": (".models", "TestsFlextInfraModels"),
        "TestsFlextInfraProtocols": (".protocols", "TestsFlextInfraProtocols"),
        "TestsFlextInfraServiceBase": (".base", "TestsFlextInfraServiceBase"),
        "TestsFlextInfraTypes": (".typings", "TestsFlextInfraTypes"),
        "TestsFlextInfraUtilities": (".utilities", "TestsFlextInfraUtilities"),
        "TestsFlextInfraUtilitiesCodegenMixin": (
            ".utilities_codegen",
            "TestsFlextInfraUtilitiesCodegenMixin",
        ),
        "TestsFlextInfraUtilitiesDepsMixin": (
            ".utilities_deps",
            "TestsFlextInfraUtilitiesDepsMixin",
        ),
        "TestsFlextInfraUtilitiesDocsFixtureMixin": (
            ".utilities_fixture_docs",
            "TestsFlextInfraUtilitiesDocsFixtureMixin",
        ),
        "TestsFlextInfraUtilitiesGatesMixin": (
            ".utilities_gates",
            "TestsFlextInfraUtilitiesGatesMixin",
        ),
        "TestsFlextInfraUtilitiesGitMixin": (
            ".utilities_git",
            "TestsFlextInfraUtilitiesGitMixin",
        ),
        "TestsFlextInfraUtilitiesProjectFixtureMixin": (
            ".utilities_fixture_project",
            "TestsFlextInfraUtilitiesProjectFixtureMixin",
        ),
        "TestsFlextInfraUtilitiesPromotedMixin": (
            ".utilities_promoted",
            "TestsFlextInfraUtilitiesPromotedMixin",
        ),
        "TestsFlextInfraUtilitiesReleaseMixin": (
            ".utilities_release",
            "TestsFlextInfraUtilitiesReleaseMixin",
        ),
        "TestsFlextInfraUtilitiesTomlMixin": (
            ".utilities_toml",
            "TestsFlextInfraUtilitiesTomlMixin",
        ),
        "TestsFlextInfraUtilitiesToolingFixtureMixin": (
            ".utilities_fixture_tooling",
            "TestsFlextInfraUtilitiesToolingFixtureMixin",
        ),
        "TestsFlextInfraUtilitiesWorkspaceEnvMixin": (
            ".utilities_workspace_env",
            "TestsFlextInfraUtilitiesWorkspaceEnvMixin",
        ),
        "TestsFlextInfraUtilitiesWorkspaceFixtureMixin": (
            ".utilities_fixture_workspace",
            "TestsFlextInfraUtilitiesWorkspaceFixtureMixin",
        ),
        "api": ("flext_tests", "api"),
        "c": (".constants", "c"),
        "d": ("flext_tests", "d"),
        "e": ("flext_tests", "e"),
        "fixtures": (".fixtures", ""),
        "h": ("flext_tests", "h"),
        "integration": (".integration", ""),
        "m": (".models", "m"),
        "p": (".protocols", "p"),
        "r": ("flext_tests", "r"),
        "refactor": (".refactor", ""),
        "s": (".base", "s"),
        "t": (".typings", "t"),
        "td": ("flext_tests", "td"),
        "tf": ("flext_tests", "tf"),
        "tk": ("flext_tests", "tk"),
        "tm": ("flext_tests", "tm"),
        "u": (".utilities", "u"),
        "unit": (".unit", ""),
        "x": ("flext_tests", "x"),
    }),
    public_exports=__all__,
)
