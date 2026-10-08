"""Semantic ``make mod`` cutover planning, composed from private domain partials.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities._semantic_cutover.base import FlextInfraUtilitiesSemanticCutoverBase


class FlextInfraUtilitiesSemanticCutover(FlextInfraUtilitiesSemanticCutoverBase):
    """Plan class-nesting, compatibility-alias, and private-import cutovers."""


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutover"]
