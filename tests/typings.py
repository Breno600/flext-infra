"""Type system for FLEXT infra tests.

Provides TestsFlextInfraTypes, extending TestsFlextTypes with infra-specific
type definitions for infrastructure testing.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import FlextTestsTypes

from flext_infra import FlextInfraTypes


class TestsFlextInfraTypes(FlextTestsTypes, FlextInfraTypes):
    """Type system for FLEXT infra tests."""

    class Tests(FlextTestsTypes.Tests):
        """Tests use inherited flext-tests and production typing contracts."""


t = TestsFlextInfraTypes

__all__: list[str] = ["TestsFlextInfraTypes", "t"]
