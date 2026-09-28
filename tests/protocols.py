"""Protocol definitions for FLEXT infra tests.

Provides TestsFlextInfraProtocols, extending TestsFlextProtocols with
infra-specific protocol definitions for infrastructure testing.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import FlextTestsProtocols

from flext_infra import FlextInfraProtocols


class TestsFlextInfraProtocols(FlextTestsProtocols, FlextInfraProtocols):
    """Protocol definitions for FLEXT infra tests."""

    class Tests(FlextTestsProtocols.Tests):
        """Tests use inherited flext-tests and production protocols."""


p = TestsFlextInfraProtocols

__all__: list[str] = ["TestsFlextInfraProtocols", "p"]
