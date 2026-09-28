"""Promoted-command utilities facet for ``u.Infra``.

Private responsibility classes live under ``_utilities/_promoted/``; consumers
use ``from flext_infra import u`` only.
"""

from __future__ import annotations

from ._promoted.commands import FlextInfraUtilitiesPromotedCommands
from ._promoted.execution import FlextInfraUtilitiesPromotedExecution
from ._promoted.rendering import FlextInfraUtilitiesPromotedRendering


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
