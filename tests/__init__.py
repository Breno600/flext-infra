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
        "TestsFlextInfraConstants": ".constants",
        "TestsFlextInfraConstantsScanMixin": ".constants_scan",
        "TestsFlextInfraModels": ".models",
        "TestsFlextInfraProtocols": ".protocols",
        "TestsFlextInfraServiceBase": ".base",
        "TestsFlextInfraTypes": ".typings",
        "TestsFlextInfraUtilities": ".utilities",
        "TestsFlextInfraUtilitiesCodegenMixin": ".utilities_codegen",
        "TestsFlextInfraUtilitiesDepsMixin": ".utilities_deps",
        "TestsFlextInfraUtilitiesDocsFixtureMixin": ".utilities_fixture_docs",
        "TestsFlextInfraUtilitiesGatesMixin": ".utilities_gates",
        "TestsFlextInfraUtilitiesGitMixin": ".utilities_git",
        "TestsFlextInfraUtilitiesProjectFixtureMixin": ".utilities_fixture_project",
        "TestsFlextInfraUtilitiesPromotedMixin": ".utilities_promoted",
        "TestsFlextInfraUtilitiesReleaseMixin": ".utilities_release",
        "TestsFlextInfraUtilitiesTomlMixin": ".utilities_toml",
        "TestsFlextInfraUtilitiesToolingFixtureMixin": ".utilities_fixture_tooling",
        "TestsFlextInfraUtilitiesWorkspaceEnvMixin": ".utilities_workspace_env",
        "TestsFlextInfraUtilitiesWorkspaceFixtureMixin": ".utilities_fixture_workspace",
        "api": "flext_tests",
        "c": ".constants",
        "d": "flext_tests",
        "e": "flext_tests",
        "fixtures": ".fixtures",
        "h": "flext_tests",
        "integration": ".integration",
        "m": ".models",
        "p": ".protocols",
        "r": "flext_tests",
        "refactor": ".refactor",
        "s": ".base",
        "t": ".typings",
        "td": "flext_tests",
        "tf": "flext_tests",
        "tk": "flext_tests",
        "tm": "flext_tests",
        "u": ".utilities",
        "unit": ".unit",
        "x": "flext_tests",
    }),
    public_exports=__all__,
)
