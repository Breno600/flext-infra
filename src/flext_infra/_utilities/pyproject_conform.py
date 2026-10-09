"""Autonomous library pyproject conformance through the flext-cli TOML facade.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities._pyproject.base import (
    FlextInfraUtilitiesPyprojectConformBase,
)


class FlextInfraUtilitiesPyprojectConform(FlextInfraUtilitiesPyprojectConformBase):
    """Render root workspace and autonomous library metadata deterministically.

    Every responsibility lives in its ``_pyproject`` owner and composes here
    through the MRO; this class declares nothing of its own.
    """


__all__: list[str] = ["FlextInfraUtilitiesPyprojectConform"]
