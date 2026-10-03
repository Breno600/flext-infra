"""Protocol definitions for flext-infra utilities and services.

Defines structural contracts (runtime-checkable Protocols) for orchestration,
command execution, validation, and reporting services used across the
infrastructure layer.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import FlextCliProtocols

from flext_infra._protocols.base import FlextInfraProtocolsBase
from flext_infra._protocols.check import FlextInfraProtocolsCheck
from flext_infra._protocols.deps import FlextInfraProtocolsDeps
from flext_infra._protocols.docs import FlextInfraProtocolsDocs
from flext_infra._protocols.promoted import FlextInfraProtocolsPromoted
from flext_infra._protocols.rope import FlextInfraProtocolsRope
from flext_infra._protocols.rope_runtime import FlextInfraProtocolsRopeRuntime


class FlextInfraProtocols(FlextCliProtocols):
    """Structural contracts for flext-infra utilities and services.

    All parent protocols (Result, Config, DI, Service, etc.) are inherited
    transparently from ``FlextProtocols`` via FLEXT. Infra-specific utility
    protocols live as nested classes below.
    """

    class Infra(
        FlextInfraProtocolsCheck,
        FlextInfraProtocolsDeps,
        FlextInfraProtocolsDocs,
        FlextInfraProtocolsPromoted,
        FlextInfraProtocolsRopeRuntime,
        FlextInfraProtocolsRope,
        FlextInfraProtocolsBase,
    ):
        """Infra-specific structural protocol definitions."""


p = FlextInfraProtocols
__all__: list[str] = ["FlextInfraProtocols", "FlextInfraProtocolsBase", "p"]
