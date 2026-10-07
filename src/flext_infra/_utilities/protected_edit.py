"""Protected file edit helpers facade.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities import FlextInfraUtilitiesProtectedEditWrites


class FlextInfraUtilitiesProtectedEdit(FlextInfraUtilitiesProtectedEditWrites):
    """Shared safety helpers for protected file edits in refactor workflows."""


__all__: list[str] = ["FlextInfraUtilitiesProtectedEdit"]
