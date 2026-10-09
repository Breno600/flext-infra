"""Workspace-wide Rope-only census orchestration.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, override

from flext_cli import cli

from flext_infra import c, m, p, r, t, u
from flext_infra.base_selection import FlextInfraProjectSelectionServiceBase
from flext_infra.refactor._census_collect import FlextInfraRefactorCensusCollectMixin
from flext_infra.refactor._census_collect_helpers import (
    FlextInfraRefactorCensusCollectHelpersMixin,
)
from flext_infra.refactor._census_filters import FlextInfraRefactorCensusFiltersMixin
from flext_infra.refactor._census_objects import FlextInfraRefactorCensusObjectsMixin
from flext_infra.refactor._census_project import FlextInfraRefactorCensusProjectMixin
from flext_infra.refactor._census_removal import FlextInfraRefactorCensusRemovalMixin
from flext_infra.refactor._census_render import FlextInfraRefactorCensusRenderMixin
from flext_infra.workspace.rope import FlextInfraRopeWorkspace


class FlextInfraRefactorCensus(
    FlextInfraProjectSelectionServiceBase[m.Infra.WorkspaceReport],
    FlextInfraRefactorCensusCollectMixin,
    FlextInfraRefactorCensusCollectHelpersMixin,
    FlextInfraRefactorCensusFiltersMixin,
    FlextInfraRefactorCensusObjectsMixin,
    FlextInfraRefactorCensusProjectMixin,
    FlextInfraRefactorCensusRemovalMixin,
    FlextInfraRefactorCensusRenderMixin,
):
    """Rope object census across the workspace: inventory and its analyses.

    Code-shape rules are rule data run by the one engine (``make mod`` and the
    codemod gate); the census reports what only a workspace object inventory
    can see — duplicate definitions, unreferenced objects and tier placement —
    and, when applying, removes the unreferenced objects it proved removable.
    """

    json_output: Annotated[
        str | None,
        m.Field(description="Path to write JSON report"),
    ] = None
    impact_map_output: Annotated[
        str | None,
        m.Field(description="Path to write dry-run impact map JSON"),
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
            description="Optional namespace-family filters; repeat --families NAME",
        ),
    ] = None
    include_local_scopes: Annotated[
        bool,
        m.Field(description="Include locals, parameters, and nested scopes"),
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

    @property
    @override
    def dry_run_gate_names(self) -> t.StrSequence:
        """Per-candidate gate set (``lint`` + ``pyrefly``).

        Mypy and pyright analyse modules transitively and flag ``__init__.py``
        lazy-import references to just-removed symbols before the lazy
        initializers are regenerated, which would reject every safe candidate.
        The per-candidate gate therefore runs the two tools that validate the
        modified file itself; normalization of every touched file follows.
        """
        return (c.Infra.LINT, c.Infra.PYREFLY)

    def _rope_root_for_selection(self) -> Path | None:
        """Return a project-scoped Rope root when exactly one project is selected.

        Workspace-wide scans (zero or many projects) keep the canonical workspace
        root so cross-project rules such as duplicate detection remain accurate.

        Returns:
            A project-scoped Rope root when exactly one project is selected.

        """
        names: t.StrSequence | None = self.project_names
        if names is None or len(names) != 1:
            return None
        project_name: str = names[0]
        project_path: Path = self.root / project_name
        if project_path.is_dir():
            return project_path
        return None

    def _execution_reports(
        self,
    ) -> t.Pair[m.Infra.WorkspaceReport, m.Infra.WorkspaceReport]:
        """Return the final report and the pre-apply report the impact map reads.

        Returns:
            The final report and the pre-apply report the impact map reads.

        """
        started = time.monotonic()
        with FlextInfraRopeWorkspace.open_workspace(
            self.root,
            rope_repository_root=self._rope_root_for_selection(),
        ) as rope:
            impact_report = self._collect_report(rope)
            report = impact_report
            if (
                self.apply_changes
                and not self.effective_dry_run
                and self._apply_removal_candidates(rope, impact_report)
            ):
                report = self._collect_report(rope)
        finalized = report.model_copy(
            update={"scan_duration_seconds": time.monotonic() - started},
        )
        return finalized, impact_report

    def build_report(self) -> m.Infra.WorkspaceReport:
        """Build the canonical workspace census report without CLI side effects.

        Returns:
            The resulting ``m.Infra.WorkspaceReport``.

        """
        report, _ = self._execution_reports()
        return report

    @override
    def execute(self) -> p.Result[m.Infra.WorkspaceReport]:
        """Execute the census with one shared Rope session.

        Returns:
            The resulting ``p.Result[m.Infra.WorkspaceReport]``.

        """
        report, impact_report = self._execution_reports()
        cli.display_text(self.render_text(report))
        if self.json_output_path is not None:
            u.Infra.export_pydantic_json(report, self.json_output_path)
            u.Cli.info(f"JSON report exported to: {self.json_output_path}")
        if self.impact_map_output_path is not None:
            impact_result = u.Infra.write_impact_map(
                self._impact_map_results(impact_report),
                self.impact_map_output_path,
            )
            if impact_result.failure:
                return r[m.Infra.WorkspaceReport].from_failure(impact_result)
            u.Cli.info(f"Impact map exported to: {self.impact_map_output_path}")
        return r[m.Infra.WorkspaceReport].ok(report)


__all__: list[str] = ["FlextInfraRefactorCensus"]
