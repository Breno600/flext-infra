"""Automated namespace enforcement orchestration.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_cli import cli

from flext_infra import c, m, r, u
from flext_infra.refactor._namespace_enforcer_project import (
    FlextInfraNamespaceEnforcerProjectMixin,
)

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraNamespaceEnforcer(FlextInfraNamespaceEnforcerProjectMixin):
    """Orchestrate namespace enforcement across a workspace."""

    def __init__(self, *, repository_root: Path) -> None:
        """Initialize with the repository root path."""
        super().__init__()
        self._repository_root = repository_root.resolve()
        self._rope_project: t.Infra.RopeProject = u.Infra.init_rope_project(
            self._repository_root,
        )

    def enforce(
        self,
        *,
        apply: bool = False,
        project_names: t.StrSequence | None = None,
        gates: t.StrSequence | None = None,
    ) -> m.Infra.WorkspaceEnforcementReport:
        """Run namespace enforcement across projects in the workspace.

        Args:
            apply: If True, auto-fix detected violations.
            project_names: If provided, only enforce these projects.
            gates: If provided, only run these enforcement gates.

        Returns:
            The resulting ``m.Infra.WorkspaceEnforcementReport``.

        """
        project_roots = self._resolve_project_roots(project_names=project_names)
        project_reports: list[m.Infra.ProjectEnforcementReport] = []
        for project_root in project_roots:
            report = self._enforce_project(
                project_root=project_root,
                project_name=project_root.name,
                apply=apply,
                gates=gates,
            )
            project_reports.append(report)
        return m.Infra.WorkspaceEnforcementReport(
            workspace=str(self._repository_root),
            projects=project_reports,
        )

    def _resolve_project_roots(
        self,
        *,
        project_names: t.StrSequence | None = None,
    ) -> t.SequenceOf[Path]:
        """Resolve the selected namespace-enabled roots through the topology owner.

        ``.`` names this repository itself; an unknown name is a caller error
        and escapes loud instead of silently enforcing nothing.

        Returns:
            The resulting ``t.SequenceOf[Path]``.

        Raises:
            ValueError: If ``resolved.failure``.

        """
        resolved = u.Infra.resolve_projects(self._repository_root, project_names or ())
        if resolved.failure:
            raise ValueError(resolved.error or "project resolution failed")
        return [
            project.path
            for project in resolved.value
            if u.Infra.namespace_enabled(project.path)
        ]

    @staticmethod
    def render_text(report: m.Infra.WorkspaceEnforcementReport) -> str:
        """Render a workspace enforcement report as plain text.

        Returns:
            The resulting ``str``.

        """
        projects = report.projects
        lines = [
            "Namespace Enforcement Report",
            f"Workspace: {report.workspace}",
            f"Projects: {len(report.projects)}",
            f"Violations: {'YES' if report.has_violations else 'NO'}",
            (
                f"Relocation findings: "
                f"{sum(project.relocation_findings for project in projects)}"
            ),
            f"Files scanned: {sum(project.files_scanned for project in projects)}",
        ]
        return "\n".join(lines)

    @classmethod
    def execute_command(
        cls,
        params: m.Infra.RefactorNamespaceEnforceInput,
    ) -> p.Result[m.Infra.WorkspaceEnforcementReport]:
        """Execute namespace enforcement directly from the canonical payload.

        Returns:
            The resulting ``p.Result[m.Infra.WorkspaceEnforcementReport]``.

        """
        enforcer = cls(repository_root=params.repository_root)
        report = enforcer.enforce(
            apply=params.apply,
            project_names=params.project_names,
            gates=params.gates,
        )
        cli.display_text(cls.render_text(report))
        published = u.Infra.publish_refactor_report_evidence(
            params.repository_root,
            report,
            relative_path=c.Infra.NAMESPACE_ENFORCE_REPORT_RELATIVE_PATH,
        )
        if published.failure:
            return r[m.Infra.WorkspaceEnforcementReport].from_failure(published)
        has_violations: bool = report.has_violations
        if has_violations:
            return r[m.Infra.WorkspaceEnforcementReport].fail(
                "Namespace violations found",
            )
        return r[m.Infra.WorkspaceEnforcementReport].ok(report)


__all__: list[str] = ["FlextInfraNamespaceEnforcer"]
