"""Generation helpers for docs services.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities import (
    FlextInfraUtilitiesDocsCollection,
    FlextInfraUtilitiesDocsGenerateRootMixin,
    FlextInfraUtilitiesDocsGuidesMixin,
)

# Why: restored lost composition — FlextInfraUtilitiesDocsGuidesMixin was
# never wired into any composed Docs* facade, leaving consumers unresolved.


class FlextInfraUtilitiesDocsGenerate(
    FlextInfraUtilitiesDocsGenerateRootMixin,
    FlextInfraUtilitiesDocsGuidesMixin,
    FlextInfraUtilitiesDocsCollection,
):
    """Reusable generation helpers exposed through ``u.Infra``."""


__all__: list[str] = ["FlextInfraUtilitiesDocsGenerate"]
