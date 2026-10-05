# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.deps. Modernizer package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.deps._modernizer.base import FlextInfraPyprojectModernizerBase
    from flext_infra.deps._modernizer.document import (
        FlextInfraPyprojectModernizerDocument,
    )
    from flext_infra.deps._modernizer.run import FlextInfraPyprojectModernizerRun
    from flext_infra.deps._modernizer.tooling import (
        FlextInfraPyprojectModernizerTooling,
    )


__all__: tuple[str, ...] = (
    "FlextInfraPyprojectModernizerBase",
    "FlextInfraPyprojectModernizerDocument",
    "FlextInfraPyprojectModernizerRun",
    "FlextInfraPyprojectModernizerTooling",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraPyprojectModernizerBase": ".base",
        "FlextInfraPyprojectModernizerDocument": ".document",
        "FlextInfraPyprojectModernizerRun": ".run",
        "FlextInfraPyprojectModernizerTooling": ".tooling",
    }),
    public_exports=__all__,
)
