"""Write and restore flows facade for protected edit workflows.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities import FlextInfraUtilitiesProtectedEditApply


class FlextInfraUtilitiesProtectedEditWrites(FlextInfraUtilitiesProtectedEditApply):
    """Shared write, rollback, and backup helpers for protected edits."""


__all__: list[str] = ["FlextInfraUtilitiesProtectedEditWrites"]
