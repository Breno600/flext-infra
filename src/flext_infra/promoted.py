"""Promoted-command framework facade for ``scripts/<verb>/<WHAT>`` commands.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from ._promoted.base import FlextInfraPromotedBase


class FlextInfraPromoted(FlextInfraPromotedBase):
    """Discover, validate, render, and dispatch repository promoted commands."""


__all__: list[str] = ["FlextInfraPromoted"]
