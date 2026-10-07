"""Qualified runtime-base discovery over captured, unpublished source.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities._rope_source_bases_aliases import (
    FlextInfraUtilitiesRopeSourceBasesAliases,
)
from flext_infra._utilities._rope_source_bases_inventory import (
    FlextInfraUtilitiesRopeSourceBasesInventory,
)
from flext_infra._utilities._rope_source_bases_runtime import (
    FlextInfraUtilitiesRopeSourceBasesRuntime,
)


class FlextInfraUtilitiesRopeSourceBases(
    FlextInfraUtilitiesRopeSourceBasesAliases,
    FlextInfraUtilitiesRopeSourceBasesInventory,
    FlextInfraUtilitiesRopeSourceBasesRuntime,
):
    """Keep source declaration identities separate from Ruff's qualified bases."""


__all__: list[str] = ["FlextInfraUtilitiesRopeSourceBases"]
