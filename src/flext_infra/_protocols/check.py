"""Protocol for workspace check outcomes.

Defines the structural contract for workspace gate loop outcome
objects with results, failure counts, and timing information.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import m, p


@runtime_checkable
class FlextInfraProtocolsCheck(Protocol):
    """Check-domain protocol definitions."""

    @runtime_checkable
    class WorkspaceLoopOutcome(Protocol):
        """Public structural view of the workspace gate loop outcome."""

        results: tuple[m.Infra.ProjectResult, ...]
        failed: int
        skipped: int
        total_elapsed: float

    @runtime_checkable
    class RopeCheckGate(Protocol):
        """Gate that consumes the composition root's shared Rope cycle."""

        def rope_callback_binding(
            self, project_dir: Path, rope: p.Infra.RopeWorkspaceDsl
        ) -> m.Infra.RopeCallbackBinding: ...

        def check_rope_outcomes(
            self,
            project_dir: Path,
            ctx: m.Infra.GateContext,
            outcomes: tuple[m.Infra.RopeCallbackOutcome, ...],
        ) -> m.Infra.GateExecution: ...


__all__: list[str] = ["FlextInfraProtocolsCheck"]
