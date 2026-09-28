"""Public make work lane lifecycle saga service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, override

from flext_core import r
from flext_infra import c, m
from flext_infra._utilities.work_saga_finish import FlextInfraWorkSagaFinish
from flext_infra._utilities.work_saga_publish import FlextInfraWorkSagaPublish
from flext_infra._utilities.work_saga_start import FlextInfraWorkSagaStart
from flext_infra._utilities.work_saga_status import FlextInfraWorkSagaStatus
from flext_infra.base import s

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkService(
    FlextInfraWorkSagaStart,
    FlextInfraWorkSagaStatus,
    FlextInfraWorkSagaPublish,
    FlextInfraWorkSagaFinish,
    s[str],
):
    """Automate bead + GitFlow branch + worktree + GitHub PR as one saga."""

    operation: Annotated[
        c.Infra.WorkOperation, m.Field(description="Public work saga operation")
    ]
    bead: Annotated[str | None, m.Field(description="Lane-root Beads issue id")] = None
    kind: Annotated[
        c.Infra.WorkKind | None, m.Field(description="GitFlow lane kind")
    ] = None
    name: Annotated[
        str | None, m.Field(description="Lane slug without kind prefix")
    ] = None
    branch: Annotated[
        str | None, m.Field(description="Explicit kind/slug branch override")
    ] = None
    epic: Annotated[
        str | None,
        m.Field(description="Registered epic Beads issue owning this child lane"),
    ] = None
    base: Annotated[
        str | None, m.Field(description="Integration base; config or HEAD when omitted")
    ] = None

    @override
    def execute(self) -> p.Result[str]:
        """Execute the selected public work saga operation."""
        primary = self._primary_root()
        if primary.failure:
            return r.fail(primary.error or "failed to resolve primary worktree")
        if self.operation == c.Infra.WorkOperation.START:
            return self._start(primary.value)
        if self.operation == c.Infra.WorkOperation.STATUS:
            return self._status(primary.value)
        if self.operation == c.Infra.WorkOperation.LAND:
            return self._land(primary.value)
        return self._finish(primary.value)


__all__: list[str] = ["FlextInfraWorkService"]
