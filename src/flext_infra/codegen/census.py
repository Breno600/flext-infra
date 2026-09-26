"""Census service for namespace violation counting and reporting.

Read-only service that counts and classifies namespace violations
across all workspace projects using FlextInfraNamespaceValidator.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_core import r
from flext_infra import c, m, p, t, u
from flext_infra.validate.namespace_validator import FlextInfraNamespaceValidator

from ..base import s

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraCodegenCensus(s[str]):
    """Read-only census service for namespace violation counting."""

    rope: t.Port[p.Infra.RopeWorkspaceDsl] = m.Field(
        exclude=True, description="Shared Rope cycle injected by the composition root"
    )

    @override
    def execute(self) -> p.Result[str]:
        """Execute the census directly from the validated CLI service model."""
        if self.apply_changes:
            return r[str].fail(
                "census is read-only; use flext-infra codegen auto-fix --apply"
            )
        reports_result = self.run()
        if reports_result.failure:
            return r[str].from_failure(reports_result)
        reports = reports_result.value
        total_violations = sum(report.total for report in reports)
        total_fixable = sum(report.fixable for report in reports)
        if self.output_format == c.Cli.OutputFormats.JSON:
            payload: t.Infra.MutableInfraMapping = {
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
            f" across {len(reports)} projects"
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
            repository_root: Override repository root (defaults to self.repository_root).
            output_format: Unused, kept for API compat.
            projects: Pre-discovered projects to skip redundant discovery.

        Returns:
            List of CensusReport models, one per scanned project.

        """
        _ = output_format
        workspace = repository_root or self.repository_root
        return self._run_project_census(workspace, projects=projects)

    def _run_project_census(
        self,
        workspace: Path,
        *,
        projects: t.SequenceOf[p.Infra.ProjectInfo] | None = None,
    ) -> p.Result[t.VariadicTuple[m.Infra.CensusReport]]:
        """Census all projects in workspace using the standard path."""
        if projects is not None:
            selected_projects = tuple(projects)
        else:
            projects_result = u.Infra.projects(workspace)
            if projects_result.failure:
                return r[t.VariadicTuple[m.Infra.CensusReport]].from_failure(
                    projects_result
                )
            selected_projects = tuple(projects_result.value)
        bindings = tuple(
            FlextInfraNamespaceValidator(
                repository_root=project.path, rope=self.rope
            ).callback_binding()
            for project in selected_projects
        )
        cycle_result = self.rope.cycle(
            bindings,
            project_names=tuple(project.path.resolve().name for project in selected_projects),
        )
        if cycle_result.failure:
            return r[t.VariadicTuple[m.Infra.CensusReport]].from_failure(cycle_result)
        reports: t.MutableSequenceOf[m.Infra.CensusReport] = []
        for project in selected_projects:
            project_root = project.path.resolve()
            raw_violations = tuple(
                violation
                for outcome in cycle_result.value.outcomes
                if outcome.callback_id == "namespace"
                and outcome.project_root.resolve() == project_root
                and outcome.applicable
                for violation in outcome.violations
            )
            validation = r[m.Infra.ValidationReport].ok(
                m.Infra.ValidationReport(
                    passed=not raw_violations,
                    violations=raw_violations,
                    summary=f"{len(raw_violations)} namespace violation(s)",
                )
            )
            parsed = u.Infra.parse_namespace_validation(validation)
            if parsed.failure:
                return r[t.VariadicTuple[m.Infra.CensusReport]].from_failure(parsed)
            violations = parsed.value
            reports.append(
                m.Infra.CensusReport(
                    project=project.name,
                    violations=violations,
                    total=len(violations),
                    fixable=u.count(violations, lambda violation: violation.fixable),
                )
            )
        return r[t.VariadicTuple[m.Infra.CensusReport]].ok(tuple(reports))


__all__: list[str] = ["FlextInfraCodegenCensus"]
