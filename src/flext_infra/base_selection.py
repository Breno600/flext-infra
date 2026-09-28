"""Project-selection service base for flext-infra command services."""

from __future__ import annotations

from flext_infra import m, t

from ._base_projects import FlextInfraProjectSelectionMixin
from .base import FlextInfraServiceBase


class FlextInfraProjectSelectionServiceBase[TDomainResult: t.Cli.ResultValue](
    FlextInfraServiceBase[TDomainResult], FlextInfraProjectSelectionMixin
):
    """Shared service foundation for commands that target workspace projects."""

    selected_projects: t.StrSequence | None = m.Field(
        default=None, alias="projects", description="Projects to process"
    )


__all__: list[str] = ["FlextInfraProjectSelectionServiceBase"]
