"""Workspace-wide Rope-only census orchestration."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, override

from flext_cli import cli

from flext_core import r
from flext_infra import m, p, t, u
from flext_infra.base_selection import FlextInfraProjectSelectionServiceBase
from flext_infra.workspace.rope import FlextInfraRopeWorkspace

from ._census_collect import FlextInfraRefactorCensusCollectMixin
from ._census_collect_helpers import FlextInfraRefactorCensusCollectHelpersMixin
from ._census_filters import FlextInfraRefactorCensusFiltersMixin
from ._census_objects import FlextInfraRefactorCensusObjectsMixin
from ._census_project import FlextInfraRefactorCensusProjectMixin
from ._census_render import FlextInfraRefactorCensusRenderMixin


class FlextInfraRefactorCensus(
    FlextInfraProjectSelectionServiceBase[m.Infra.WorkspaceReport],
    FlextInfraRefactorCensusCollectMixin,
    FlextInfraRefactorCensusCollectHelpersMixin,
    FlextInfraRefactorCensusFiltersMixin,
    FlextInfraRefactorCensusObjectsMixin,
    FlextInfraRefactorCensusProjectMixin,
    FlextInfraRefactorCensusRenderMixin,
):
    """Rope object census across the workspace: inventory and its analyses.

    Code-shape rules are rule data run by the one engine (``make mod`` and the
    codemod gate); the census reports what only a workspace object inventory
    can see — duplicate definitions, unreferenced objects and tier placement.
    """

    json_output: Annotated[
        str | None, m.Field(description="Path to write JSON report")
    ] = None
    impact_map_output: Annotated[
        str | None, m.Field(description="Path to write dry-run impact map JSON")
    ] = None
    kinds: Annotated[
        t.StrSequence | None,
        m.Field(description="Optional symbol-kind filters; repeat --kinds NAME"),
    ] = None
    rules: Annotated[
        t.StrSequence | None,
        m.Field(description="Optional violation-rule filters; repeat --rules NAME"),
    ] = None
    families: Annotated[
        t.StrSequence | None,
        m.Field(
            description="Optional namespace-family filters; repeat --families NAME"
        ),
    ] = None
    include_local_scopes: Annotated[
        bool, m.Field(description="Include locals, parameters, and nested scopes")
    ] = True

    @property
    def json_output_path(self) -> Path | None:
        """Resolved JSON export path when provided."""
        path: Path | None = u.Infra.normalize_optional_path(self.json_output)
        return path

    @property
    def impact_map_output_path(self) -> Path | None:
        """Resolved impact-map export path when provided."""
        path: Path | None = u.Infra.normalize_optional_path(self.impact_map_output)
        return path

    @property
    @override
    def kind_names(self) -> t.StrSequence | None:
        """Normalized symbol-kind filters."""
        return u.Infra.normalize_sequence_values(self.kinds)

    @property
    @override
    def rule_names(self) -> t.StrSequence | None:
        """Normalized violation-rule filters."""
        return u.Infra.normalize_sequence_values(self.rules)

    @property
    @override
    def family_names(self) -> t.StrSequence | None:
        """Normalized family filters."""
        return u.Infra.normalize_sequence_values(self.families)

    def _rope_root_for_selection(self) -> Path | None:
        """Return a project-scoped Rope root when exactly one project is selected.

        Workspace-wide scans (zero or many projects) keep the canonical workspace
        root so cross-project rules such as duplicate detection remain accurate.
        """
        names: t.StrSequence | None = self.project_names
        if names is None or len(names) != 1:
            return None
        project_name: str = names[0]
        project_path: Path = self.root / project_name
        if project_path.is_dir():
            return project_path
        return None

    def build_report(self) -> m.Infra.WorkspaceReport:
        """Build the canonical workspace census report without CLI side effects."""
        started = time.monotonic()
        with FlextInfraRopeWorkspace.open_workspace(
            self.root, rope_repository_root=self._rope_root_for_selection()
        ) as rope:
            report = self._collect_report(rope)
        return report.model_copy(
            update={"scan_duration_seconds": time.monotonic() - started}
        )

    @override
    def execute(self) -> p.Result[m.Infra.WorkspaceReport]:
        """Execute the census with one shared Rope session."""
        report = self.build_report()
        cli.display_text(self.render_text(report))
        if self.json_output_path is not None:
            u.Infra.export_pydantic_json(report, self.json_output_path)
            u.Cli.info(f"JSON report exported to: {self.json_output_path}")
        if self.impact_map_output_path is not None:
            impact_result = u.Infra.write_impact_map(
                self._impact_map_results(report), self.impact_map_output_path
            )
            if impact_result.failure:
                return r[m.Infra.WorkspaceReport].from_failure(impact_result)
            u.Cli.info(f"Impact map exported to: {self.impact_map_output_path}")
        return r[m.Infra.WorkspaceReport].ok(report)


__all__: list[str] = ["FlextInfraRefactorCensus"]
