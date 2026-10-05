"""Census service for namespace violation counting and reporting.

Read-only service that counts and classifies namespace violations
across all workspace projects from the rule engine's findings.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_core import r
from flext_infra import c, m, p, t, u
from flext_infra.base import s
from flext_infra.validate.namespace_validator import FlextInfraNamespaceValidator

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraCodegenCensus(s[str]):
    """Read-only census service for namespace violation counting."""

    @override
    def execute(self) -> p.Result[str]:
        """Execute the census directly from the validated CLI service model.

        Returns:
            The resulting ``p.Result[str]``.

        """
        if self.apply_changes:
            return r[str].fail(
                "census is read-only; use flext-infra codegen auto-fix --apply",
            )
        reports_result = self.run()
        if reports_result.failure:
            return r[str].from_failure(reports_result)
        reports = reports_result.value
        total_violations = sum(report.total for report in reports)
        total_fixable = sum(report.fixable for report in reports)
        if self.output_format == c.Cli.OutputFormats.JSON:
            payload: t.MutableJsonMapping = {
                c.Infra.RK_PROJECTS: [report.model_dump() for report in reports],
                "total_violations": total_violations,
                "total_fixable": total_fixable,
            }
            return r[str].ok(t.Infra.INFRA_MAPPING_ADAPTER.dump_json(payload).decode())
        lines: t.MutableSequenceOf[str] = [
            (
                f"  {report.project}: {report.total} violations"
                f" ({report.fixable} fixable)"
            )
            for report in reports
            if report.total > 0
        ]
        lines.append(
            f"Total: {total_violations} violations ({total_fixable} fixable)"
            f" across {len(reports)} projects",
        )
        return r[str].ok("\n".join(lines))

    def run(
        self,
        repository_root: Path | None = None,
        *,
        output_format: str = c.Cli.OutputFormats.JSON,
        projects: t.SequenceOf[p.Infra.ProjectInfo] | None = None,
    ) -> p.Result[t.VariadicTuple[m.Infra.CensusReport]]:
        """Run census on all projects in workspace.

        Args:
            repository_root: Override root (defaults to self.repository_root).
            output_format: Unused, kept for API compat.
            projects: Pre-discovered projects to skip redundant discovery.

        Returns:
            List of CensusReport models, one per scanned project.

        """
        _ = output_format
        workspace = repository_root or self.repository_root
        return self._run_project_census(workspace, projects=projects)

    @staticmethod
    def _run_project_census(
        workspace: Path,
        *,
        projects: t.SequenceOf[p.Infra.ProjectInfo] | None = None,
    ) -> p.Result[t.VariadicTuple[m.Infra.CensusReport]]:
        """Census all projects in workspace using the standard path.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.CensusReport]]``.

        """
        if projects is not None:
            selected_projects = tuple(projects)
        else:
            projects_result = u.Infra.projects(workspace)
            if projects_result.failure:
                return r[t.VariadicTuple[m.Infra.CensusReport]].from_failure(
                    projects_result,
                )
            selected_projects = tuple(projects_result.value)
        reports: t.MutableSequenceOf[m.Infra.CensusReport] = []
        for project in selected_projects:
            project_root = project.path.resolve()
            validation = FlextInfraNamespaceValidator(
                repository_root=project_root,
            ).build_report()
            parsed = u.Infra.parse_namespace_validation(validation, project_root)
            if parsed.failure:
                return r[t.VariadicTuple[m.Infra.CensusReport]].from_failure(parsed)
            violations = parsed.value
            reports.append(
                m.Infra.CensusReport(
                    project=project.name,
                    violations=violations,
                    total=len(violations),
                    fixable=u.count(violations, lambda violation: violation.fixable),
                ),
            )
        return r[t.VariadicTuple[m.Infra.CensusReport]].ok(tuple(reports))


__all__: list[str] = ["FlextInfraCodegenCensus"]
