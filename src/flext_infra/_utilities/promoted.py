"""Promoted-command utilities facet for ``u.Infra``.

Private responsibility classes live under ``_utilities/_promoted/``; consumers
use ``from flext_infra import u`` only.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities._promoted.commands import FlextInfraUtilitiesPromotedCommands
from flext_infra._utilities._promoted.execution import FlextInfraUtilitiesPromotedExecution
from flext_infra._utilities._promoted.rendering import FlextInfraUtilitiesPromotedRendering


class FlextInfraUtilitiesPromoted(
    FlextInfraUtilitiesPromotedExecution,
    FlextInfraUtilitiesPromotedCommands,
    FlextInfraUtilitiesPromotedRendering,
):
    """Stateless promoted-command primitives.

    Execution composes invocation validation and the workspace boundary;
    header ingress and help rendering are independent leaves.
    """


__all__: list[str] = ["FlextInfraUtilitiesPromoted"]
