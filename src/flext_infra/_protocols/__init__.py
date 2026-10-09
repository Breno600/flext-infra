# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Protocols package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._protocols.base import FlextInfraProtocolsBase
    from flext_infra._protocols.check import FlextInfraProtocolsCheck
    from flext_infra._protocols.deps import FlextInfraProtocolsDeps
    from flext_infra._protocols.docs import FlextInfraProtocolsDocs
    from flext_infra._protocols.promoted import FlextInfraProtocolsPromoted
    from flext_infra._protocols.rope import FlextInfraProtocolsRope
    from flext_infra._protocols.rope_runtime import FlextInfraProtocolsRopeRuntime


__all__: tuple[str, ...] = (
    "FlextInfraProtocolsBase",
    "FlextInfraProtocolsCheck",
    "FlextInfraProtocolsDeps",
    "FlextInfraProtocolsDocs",
    "FlextInfraProtocolsPromoted",
    "FlextInfraProtocolsRope",
    "FlextInfraProtocolsRopeRuntime",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraProtocolsBase": ".base",
        "FlextInfraProtocolsCheck": ".check",
        "FlextInfraProtocolsDeps": ".deps",
        "FlextInfraProtocolsDocs": ".docs",
        "FlextInfraProtocolsPromoted": ".promoted",
        "FlextInfraProtocolsRope": ".rope",
        "FlextInfraProtocolsRopeRuntime": ".rope_runtime",
    }),
    public_exports=__all__,
)
