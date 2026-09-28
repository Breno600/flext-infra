"""Models for FLEXT infra tests.

Provides TestsFlextInfraModels, extending TestsFlextModels with infra-specific
model definitions for infrastructure testing and validation.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import FlextTestsModels

from flext_infra import FlextInfraModels


class TestsFlextInfraModels(FlextTestsModels, FlextInfraModels):
    """Infra test models extending flext-tests and production models."""

    class Tests(FlextTestsModels.Tests):
        """Tests use inherited flext-tests and production infra models."""


m = TestsFlextInfraModels

__all__: list[str] = ["TestsFlextInfraModels", "m"]
