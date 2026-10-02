"""Modernize workspace pyproject.toml files to standardized format.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra.deps._modernizer.base import FlextInfraPyprojectModernizerBase


class FlextInfraPyprojectModernizer(FlextInfraPyprojectModernizerBase):
    """Modernize all workspace pyproject.toml files."""


__all__: list[str] = ["FlextInfraPyprojectModernizer"]
