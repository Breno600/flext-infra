"""Pyproject modernizer base joining its responsibility classes via MRO."""

from __future__ import annotations

from typing import Annotated, override

from flext_core import r
from flext_infra import config, m, p, t
from flext_infra.base_selection import FlextInfraProjectSelectionServiceBase

from .document import FlextInfraPyprojectModernizerDocument
from .run import FlextInfraPyprojectModernizerRun
from .tooling import FlextInfraPyprojectModernizerTooling


class FlextInfraPyprojectModernizerBase(
    FlextInfraProjectSelectionServiceBase[bool],
    FlextInfraPyprojectModernizerDocument,
    FlextInfraPyprojectModernizerTooling,
    FlextInfraPyprojectModernizerRun,
):
    """Modernize workspace pyproject.toml files to the canonical format."""

    @staticmethod
    def _config_sort_first() -> t.StrSequence:
        """Read the config-owned top-level TOML section order once."""
        return config.Infra.tooling.tools.tomlsort.sort_first

    audit: Annotated[
        bool, m.Field(False, description="Audit pyproject changes without writing")
    ] = False
    skip_check: Annotated[
        bool, m.Field(alias="skip-check", description="Skip post-write validation")
    ] = False
    skip_comments: Annotated[
        bool, m.Field(alias="skip-comments", description="Skip managed comment updates")
    ] = False
    rewrite_constraints: Annotated[
        bool,
        m.Field(
            alias="rewrite-constraints",
            description="Rewrite dependency constraints from the provisioned runtime",
        ),
    ] = False
    managed_artifacts: Annotated[
        m.Infra.ProjectManagedArtifactsResolution | None,
        m.Field(
            default=None,
            exclude=True,
            description="Caller-owned project ManagedArtifacts resolution",
        ),
    ] = None
    tomlsort_sort_first: t.StrSequence = m.Field(
        default_factory=_config_sort_first,
        exclude=True,
        description="Config-owned top-level TOML section order",
    )

    @override
    def execute(self) -> p.Result[bool]:
        """Execute pyproject modernization for the configured workspace."""
        if self.run() != 0:
            return r[bool].fail("pyproject modernization failed")
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraPyprojectModernizerBase"]
