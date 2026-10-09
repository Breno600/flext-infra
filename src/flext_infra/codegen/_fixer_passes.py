"""Pipeline pass helpers for the codegen fixer service.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from flext_infra import m, u
from flext_infra.codegen import (
    FlextInfraCodegenFixerResultsMixin,
    FlextInfraCodegenLazyInit,
)


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
        FlextInfraCodegenFixerPassesMixin._fixer_log.warning(
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
    def _run_import_cycle_proof(ctx: m.Infra.FixContext, project_path: Path) -> None:
        """Prove the post-fix tree is free of runtime import cycles.

        The existing cyclic-import detector (the codemod project facts engine:
        runtime import graph over Rope's module import table, then strongly
        connected components) reads the tree as the fix left it. Every module
        taking part in a cycle is recorded as an unfixable violation, so an
        auto-fix run that introduced a cycle fails loud instead of
        publishing it.

        """
        graph = u.Infra.project_import_graph(project_path)[0]
        cycles = u.Infra.project_import_cycles(graph)
        if not cycles:
            return
        FlextInfraCodegenFixerPassesMixin._fixer_log.error(
            "import_cycle_detected",
            project=project_path.name,
            modules=",".join(sorted(cycles)),
        )
        ctx.violations_skipped.extend(
            m.Infra.CensusViolation(
                module=module,
                rule="IMPORT-CYCLE",
                line=0,
                message="module takes part in a runtime import cycle",
                fixable=False,
            )
            for module in sorted(cycles)
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
