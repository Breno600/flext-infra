"""Codegen pipeline stage handlers — extracted concern of FlextInfraCodegenPipeline.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, m, t, u
from flext_infra.codegen import FlextInfraCodegenCensus
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_infra.codegen.fixer import FlextInfraCodegenFixer
from flext_infra.codegen.lazy_init import FlextInfraCodegenLazyInit
from flext_infra.codegen.py_typed import FlextInfraCodegenPyTyped
from flext_infra.codegen.scaffolder import FlextInfraCodegenScaffolder
from flext_infra.deps.detector import FlextInfraRuntimeDevDependencyDetector

if TYPE_CHECKING:
    from collections.abc import Callable

    from flext_infra import p


class FlextInfraCodegenPipelineStagesMixin:
    """Canonical codegen stage handlers, each a single fail-fast boundary.

    Composed into FlextInfraCodegenPipeline via FLEXT; every handler runs through
    the facade's ``_run_stage`` harness and caches its output in ``self._state``.
    """

    if TYPE_CHECKING:
        # Provided by the composed facade (FlextInfraCodegenPipeline); declared
        # here so the handlers type-resolve against the facade state + harness.
        _state: m.Infra.CodegenPipelineState
        conform_collaborators: m.Infra.CodegenConformPorts

        def _run_stage[V](
            self,
            stage_id: str,
            action: Callable[[], V],
            emit: Callable[[V], t.JsonMapping],
        ) -> p.Result[m.Cli.PipelineStageResult]: ...

    def _stage_discover(
        self,
        ctx: p.Cli.PipelineStageContext,
        /,
    ) -> p.Result[m.Cli.PipelineStageResult]:
        """Discover workspace projects once for reuse across all stages.

        Failure to enumerate projects propagates as a stage failure — no
        silent empty-tuple fallback, since downstream stages depend on the
        actual workspace inventory.

        Returns:
            The resulting ``p.Result[m.Cli.PipelineStageResult]``.

        """

        def _action() -> t.VariadicTuple[m.Infra.ProjectInfo]:
            projects_result = u.Infra.projects(ctx.repository_root)
            if projects_result.failure:
                msg = projects_result.error or "project discovery failed"
                raise RuntimeError(msg)
            return tuple(projects_result.unwrap())

        def _emit(discovered: t.VariadicTuple[m.Infra.ProjectInfo]) -> t.JsonMapping:
            self._state.discovered_projects = discovered
            return {"projects_discovered": len(discovered)}

        return self._run_stage(c.Infra.PipelineStage.DISCOVER, _action, _emit)

    def _stage_toolchain(
        self,
        ctx: p.Cli.PipelineStageContext,
        /,
    ) -> p.Result[m.Cli.PipelineStageResult]:
        """Conform workspace toolchains through the canonical codegen planner.

        Returns:
            The resulting ``p.Result[m.Cli.PipelineStageResult]``.

        """

        def _action() -> m.Infra.CodegenResult:
            dry_run = bool(ctx.settings.get(c.Infra.PIPELINE_KEY_DRY_RUN, False))
            result = FlextInfraCodegenConform.execute_request(
                m.Infra.CodegenConformRequest(
                    root=ctx.repository_root,
                    what=c.Infra.CodegenConformSurface.ALL,
                    scope=c.Infra.CodegenConformScope.ALL,
                    mode=(
                        c.Infra.CodegenConformMode.CHECK
                        if dry_run
                        else c.Infra.CodegenConformMode.APPLY
                    ),
                ),
                ports=self.conform_collaborators,
            )
            if result.failure:
                msg = result.error or "toolchain conform failed"
                raise RuntimeError(msg)
            conformed: m.Infra.CodegenResult = result.unwrap()
            return conformed

        return self._run_stage(
            c.Infra.PipelineStage.TOOLCHAIN,
            _action,
            lambda result: {
                "repositories_conformed": len(result.plan.repositories),
                "files_written": len(result.written_files),
            },
        )

    def _stage_deps(
        self,
        ctx: p.Cli.PipelineStageContext,
        /,
    ) -> p.Result[m.Cli.PipelineStageResult]:
        """Conform dependencies to reality via deptry + typing-stub detection.

        Reuses ``FlextInfraRuntimeDevDependencyDetector`` (deptry DEP001-004 +
        ``types-*`` stub hints). Apply declares missing requirements in CUSTOM
        ``project.optional-dependencies.typings`` and installs them through UV;
        dry-run reports only. Mutation failures remain stage failures.

        Returns:
            The resulting ``p.Result[m.Cli.PipelineStageResult]``.

        """

        def _action() -> bool:
            dry_run = bool(ctx.settings.get(c.Infra.PIPELINE_KEY_DRY_RUN, False))
            projects = self._state.discovered_projects
            selected = tuple(project.path.name for project in projects)
            detector = FlextInfraRuntimeDevDependencyDetector(
                repository_root=ctx.repository_root,
                apply_changes=not dry_run,
                apply_typings=not dry_run,
                selected_projects=selected,
            )
            result = detector.execute()
            if result.failure:
                msg = result.error or "dependency conform failed"
                raise RuntimeError(msg)
            applied: bool = t.Infra.BOOL_ADAPTER.validate_python(result.unwrap())
            return applied

        return self._run_stage(
            c.Infra.PipelineStage.DEPS,
            _action,
            lambda applied: {"deps_conformed": applied},
        )

    def _stage_py_typed(
        self,
        ctx: p.Cli.PipelineStageContext,
        /,
    ) -> p.Result[m.Cli.PipelineStageResult]:
        """Run PEP 561 py.typed marker generation.

        Returns:
            The resulting ``p.Result[m.Cli.PipelineStageResult]``.

        """

        def _action() -> int:
            py_typed = FlextInfraCodegenPyTyped(repository_root=ctx.repository_root)
            return py_typed.run()

        return self._run_stage(
            c.Infra.PipelineStage.PY_TYPED,
            _action,
            lambda count: {"markers_updated": count},
        )

    def _stage_census_before(
        self,
        ctx: p.Cli.PipelineStageContext,
        /,
    ) -> p.Result[m.Cli.PipelineStageResult]:
        """Run census (before fixes) and cache reports in typed state.

        Returns:
            The resulting ``p.Result[m.Cli.PipelineStageResult]``.

        """

        def _action() -> t.Pair[
            FlextInfraCodegenCensus,
            t.SequenceOf[m.Infra.CensusReport],
        ]:
            census = FlextInfraCodegenCensus(repository_root=ctx.repository_root)
            projects = self._state.discovered_projects
            reports_result = census.run(projects=projects)
            if reports_result.failure:
                raise RuntimeError(reports_result.error or "census failed")
            return census, reports_result.value

        def _emit(
            payload: t.Pair[
                FlextInfraCodegenCensus,
                t.SequenceOf[m.Infra.CensusReport],
            ],
        ) -> t.JsonMapping:
            census, reports = payload
            self._state.census_service = census
            self._state.reports_before = reports
            return {
                "total_violations": sum(report.total for report in reports),
                "total_fixable": sum(report.fixable for report in reports),
            }

        return self._run_stage(c.Infra.PipelineStage.CENSUS_BEFORE, _action, _emit)

    def _stage_scaffold(
        self,
        ctx: p.Cli.PipelineStageContext,
        /,
    ) -> p.Result[m.Cli.PipelineStageResult]:
        """Run scaffold stage and cache results.

        Returns:
            The resulting ``p.Result[m.Cli.PipelineStageResult]``.

        """

        def _action() -> t.SequenceOf[m.Infra.ScaffoldResult]:
            dry_run = bool(ctx.settings.get(c.Infra.PIPELINE_KEY_DRY_RUN, False))
            projects = self._state.discovered_projects
            return FlextInfraCodegenScaffolder(repository_root=ctx.repository_root).run(
                dry_run=dry_run,
                projects=projects,
            )

        def _emit(results: t.SequenceOf[m.Infra.ScaffoldResult]) -> t.JsonMapping:
            self._state.scaffold_results = results
            return {
                "total_created": sum(len(rsl.files_created) for rsl in results),
                "total_skipped": sum(len(rsl.files_skipped) for rsl in results),
            }

        return self._run_stage(c.Infra.PipelineStage.SCAFFOLD, _action, _emit)

    def _stage_auto_fix(
        self,
        ctx: p.Cli.PipelineStageContext,
        /,
    ) -> p.Result[m.Cli.PipelineStageResult]:
        """Run auto-fix stage and cache results.

        Returns:
            The resulting ``p.Result[m.Cli.PipelineStageResult]``.

        """

        def _action() -> t.SequenceOf[m.Infra.AutoFixResult]:
            dry_run = bool(ctx.settings.get(c.Infra.PIPELINE_KEY_DRY_RUN, False))
            projects = self._state.discovered_projects
            return FlextInfraCodegenFixer(
                repository_root=ctx.repository_root,
                dry_run=dry_run,
            ).fix_workspace(projects=projects)

        def _emit(results: t.SequenceOf[m.Infra.AutoFixResult]) -> t.JsonMapping:
            self._state.fix_results = results
            return {
                "total_fixed": sum(len(rsl.violations_fixed) for rsl in results),
                "total_skipped": sum(len(rsl.violations_skipped) for rsl in results),
            }

        return self._run_stage(c.Infra.PipelineStage.AUTO_FIX, _action, _emit)

    def _stage_lazy_init(
        self,
        ctx: p.Cli.PipelineStageContext,
        /,
    ) -> p.Result[m.Cli.PipelineStageResult]:
        """Measure lazy-init drift without publishing outside conform.

        Returns:
            The resulting ``p.Result[m.Cli.PipelineStageResult]``.

        """

        def _action() -> int:
            analysis = (
                FlextInfraCodegenLazyInit(repository_root=ctx.repository_root)
                .plan_files()
                .unwrap()
            )
            return sum(
                u.Infra.codegen_file_requires_effect(plan) for plan in analysis.files
            )

        return self._run_stage(
            c.Infra.PipelineStage.LAZY_INIT,
            _action,
            lambda count: {"unmapped_count": count},
        )

    def _stage_census_after(
        self,
        ctx: p.Cli.PipelineStageContext,
        /,
    ) -> p.Result[m.Cli.PipelineStageResult]:
        """Run census (after fixes) and cache reports.

        Returns:
            The resulting ``p.Result[m.Cli.PipelineStageResult]``.

        """

        def _action() -> t.SequenceOf[m.Infra.CensusReport]:
            census = self._state.census_service
            if census is None:
                census = FlextInfraCodegenCensus(repository_root=ctx.repository_root)
            projects = self._state.discovered_projects
            reports_result = census.run(projects=projects)
            if reports_result.failure:
                raise RuntimeError(reports_result.error or "census failed")
            return reports_result.value

        def _emit(reports: t.SequenceOf[m.Infra.CensusReport]) -> t.JsonMapping:
            self._state.reports_after = reports
            return {
                "total_violations": sum(report.total for report in reports),
                "total_fixable": sum(report.fixable for report in reports),
            }

        return self._run_stage(c.Infra.PipelineStage.CENSUS_AFTER, _action, _emit)


__all__: list[str] = ["FlextInfraCodegenPipelineStagesMixin"]
