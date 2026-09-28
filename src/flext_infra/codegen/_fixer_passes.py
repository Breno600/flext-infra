"""Pipeline pass helpers for the codegen fixer service."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from flext_infra import m, u

from ._fixer_results import FlextInfraCodegenFixerResultsMixin
from .lazy_init import FlextInfraCodegenLazyInit

_log = u.fetch_logger(__name__)


class FlextInfraCodegenFixerPassesMixin(FlextInfraCodegenFixerResultsMixin):
    """Private pipeline passes for codegen fixer composition."""

    @staticmethod
    def _run_namespace_enforcement(
        ctx: m.Infra.FixContext,
        project_path: Path,
        enforce: Callable[[str], m.Infra.WorkspaceEnforcementReport],
    ) -> None:
        """Run namespace enforcement and record any unresolved violations."""
        enforcement = enforce(project_path.name)
        violating_projects = tuple(
            project_report
            for project_report in enforcement.projects
            if project_report.has_violations
        )
        if not violating_projects:
            return
        _log.warning(
            "namespace_enforcement_failed",
            project=project_path.name,
            error="violations remain after namespace enforcement",
        )
        ctx.violations_skipped.extend(
            m.Infra.CensusViolation(
                module=project_report.project,
                rule="NAMESPACE",
                line=0,
                message="violations remain after namespace enforcement",
                fixable=False,
            )
            for project_report in violating_projects
        )

    @staticmethod
    def _run_lazy_init_preflight(ctx: m.Infra.FixContext, project_path: Path) -> None:
        """Preflight lazy-init plans and leave publication to conform."""
        plans = (
            FlextInfraCodegenLazyInit(repository_root=project_path)
            .plan_files()
            .unwrap()
        )
        pending = tuple(
            plan for plan in plans.files if u.Infra.codegen_file_requires_effect(plan)
        )
        if pending:
            ctx.skip(
                module=project_path.name,
                rule="LAZY-INIT",
                line=0,
                message=(
                    f"{len(pending)} lazy-init artifacts require the "
                    "codegen conform transaction"
                ),
            )


__all__: list[str] = ["FlextInfraCodegenFixerPassesMixin"]
