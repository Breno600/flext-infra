"""Constants for the unified census pipeline — accessed via c.Infra.*.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import ClassVar


class FlextInfraConstantsCensus:
    """Census pipeline constants for object detection and classification."""

    CENSUS_UNSUPPORTED_SIMPLE_REMOVAL_CODE: ClassVar[str] = (
        "CENSUS_UNSUPPORTED_SIMPLE_REMOVAL"
    )
    "Error code marking a candidate outside the simple-removal contract."


__all__: list[str] = ["FlextInfraConstantsCensus"]
