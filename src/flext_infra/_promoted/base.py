"""Promoted-command framework base: joins every responsibility via MRO."""

from __future__ import annotations

from .dispatch import FlextInfraPromotedDispatch


class FlextInfraPromotedBase(FlextInfraPromotedDispatch):
    """Registry state, discovery, and dispatch composed for the public facade.

    Stateless header, validation, rendering, and execution primitives are the
    ``u.Infra.promoted_*`` utilities; this chain owns only registry state.
    """


__all__: list[str] = ["FlextInfraPromotedBase"]
