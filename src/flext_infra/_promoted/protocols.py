"""Promoted-family protocols anchor.

Federates the Infra protocol contracts consumed by discovery and dispatch:
the family binds the composed Infra protocols facade under ``p`` so family
modules keep one canonical TYPE_CHECKING import
(``from flext_infra.protocols import p``).

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra.protocols import FlextInfraProtocols

p = FlextInfraProtocols

__all__: tuple[str, ...] = ("FlextInfraProtocols", "p")
