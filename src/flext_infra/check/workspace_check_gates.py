"""Gate execution methods for workspace checker.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from flext_cli import cli

from flext_core import r
from flext_infra import c, config, m, p, t, u

if TYPE_CHECKING:
    from flext_infra.check.gate_registry import FlextInfraGateRegistry
    from flext_infra.gates.base_gate import FlextInfraGate


class FlextInfraWorkspaceCheckGatesMixin:
    """Gate execution, project loop, and individual gate runner methods."""

    _repository_root: Path
    _registry: FlextInfraGateRegistry
    _default_reports_dir: Path
    _gate_logger: ClassVar[p.Logger] = u.fetch_logger(__name__)

    @staticmethod
    def _isolate_context(
        ctx: m.Infra.GateContext,
        target: m.Infra.CheckProjectTarget,
    ) -> m.Infra.GateContext:
        """Create a fresh GateContext scoped to a single project.

        Returns:
            The resulting ``m.Infra.GateContext``.

        """
        return m.Infra.GateContext(
            repository_root=ctx.repository_root,
            reports_dir=ctx.reports_dir / target.name,
            apply_fixes=ctx.apply_fixes,
            check_only=ctx.check_only,
            fail_fast=ctx.fail_fast,
            ruff_args=ctx.ruff_args,
            pyright_args=ctx.pyright_args,
        )

    def _run_single_project(
        self,
        target: m.Infra.CheckProjectTarget,
        resolved_gates: t.StrSequence,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.ProjectResult:
        """Check one project after the loop has validated its target.

        Returns:
            The resulting ``m.Infra.ProjectResult``.

        """
        project_dir = target.path
        project_ctx = self._isolate_context(ctx, target)
        _ = u.Cli.ensure_dir(project_ctx.reports_dir)
        start = time.monotonic()
        project_result = self._check_project_with_ctx(
            project_dir,
            resolved_gates,
            project_ctx,
        )
        elapsed = time.monotonic() - start
        u.Cli.status(
            c.Infra.VERB_CHECK,
            target.name,
            result=project_result.passed,
            elapsed=elapsed,
        )
        return project_result

    def _run_project_loop(
        self,
        projects: t.SequenceOf[m.Infra.CheckProjectTarget],
        resolved_gates: t.StrSequence,
        ctx: m.Infra.GateContext,
        *,
        fail_fast: bool,
    ) -> m.Infra.LoopOutcome:
        """Execute gate checks across projects, collecting results and timing.

        Returns:
            The resulting ``m.Infra.LoopOutcome``.

        """
        results: t.MutableSequenceOf[m.Infra.ProjectResult] = []
        total = len(projects)
        failed = 0
        loop_start = time.monotonic()
        for index, target in enumerate(projects, 1):
            u.Cli.progress(index, total, target.name, c.Infra.VERB_CHECK)
            project_result = self._run_single_project(target, resolved_gates, ctx)
            results.append(project_result)
            project_passed: bool = project_result.passed
            if not project_passed:
                failed += 1
                if fail_fast:
                    break
        return m.Infra.LoopOutcome(
            results=tuple(results),
            failed=failed,
            total_elapsed=time.monotonic() - loop_start,
        )

    def _gate_ctx(self, reports_dir: Path | None = None) -> m.Infra.GateContext:
        """Gate ctx.

        Returns:
            The resulting ``m.Infra.GateContext``.

        """
        return m.Infra.GateContext(
            repository_root=self._repository_root,
            reports_dir=reports_dir or self._default_reports_dir,
        )

    def _run_gate(
        self,
        gate_id: str,
        project_dir: Path,
        reports_dir: Path | None = None,
        *,
        ctx: m.Infra.GateContext | None = None,
    ) -> m.Infra.GateExecution:
        """Run gate.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        """
        gate = self._registry.create(gate_id, self._repository_root)
        if gate is None:
            return m.Infra.GateExecution(
                result=m.Infra.GateResult(
                    gate=gate_id,
                    project=project_dir.name,
                    passed=False,
                    errors=[f"{gate_id} gate not registered"],
                    duration=0.0,
                ),
                issues=(),
                raw_output=f"{gate_id} gate not registered",
            )
        return gate.check(project_dir, ctx or self._gate_ctx(reports_dir))

    def _check_project_with_ctx(
        self,
        project_dir: Path,
        gates: t.StrSequence,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.ProjectResult:
        """Run gates for one project and retain every executed gate in order.

        Fixers mutate shared files, so an ``--apply`` run chains every gate on
        the previous one. Read-only gates share no mutable state and run as one
        parallel wave; reporting retains the complete wave, including failures
        after the first one. Serialized fail-fast runs stop at their failed gate.

        Returns:
            The resulting ``m.Infra.ProjectResult``.

        Raises:
            ValueError: If ``gate_instance is None``.

        """
        project_name = project_dir.name
        result = m.Infra.ProjectResult(
            project=project_name,
            informational_gates=config.Infra.codegen.make.informational_check_gates,
        )
        mutating = ctx.apply_fixes and not ctx.check_only
        executions: MutableMapping[str, m.Infra.GateExecution] = {}

        stages: t.MutableSequenceOf[m.Cli.PipelineStageSpec] = []
        previous_gate_id: str | None = None
        for gate_id in gates:
            gate_instance = self._registry.create(gate_id, self._repository_root)
            if gate_instance is None:
                msg = f"{gate_id} gate not registered"
                raise ValueError(msg)
            if not gate_instance.selected_for(project_dir):
                continue
            stages.append(
                m.Cli.PipelineStageSpec(
                    stage_id=gate_id,
                    depends_on=(
                        frozenset({previous_gate_id})
                        if (ctx.fail_fast or mutating) and previous_gate_id is not None
                        else frozenset()
                    ),
                    handler=self._make_gate_handler(
                        gate_instance,
                        project_dir,
                        ctx,
                        executions,
                    ),
                ),
            )
            previous_gate_id = gate_id

        cli.pipeline(
            stages,
            context=m.Cli.PipelineStageContext(repository_root=project_dir),
            logger=self._gate_logger,
        )
        for stage in stages:
            execution = executions[stage.stage_id]
            result.gates[stage.stage_id] = execution
            u.Cli.gate_result(
                stage.stage_id,
                execution.finding_count,
                passed=execution.result.passed,
                elapsed=execution.result.duration,
            )
            if not execution.result.passed:
                for finding in execution.result.errors:
                    u.Cli.info(finding)
                # Missing or malformed findings must retain the producer's failure.
                if execution.raw_output.strip() and (
                    not execution.result.errors
                    or any(
                        issue.code == c.Infra.ToolOutcome.ERROR
                        for issue in execution.issues
                    )
                ):
                    u.Cli.info(execution.raw_output)
                if ctx.fail_fast or mutating:
                    break
        return result

    # ------------------------------------------------------------------
    # Pipeline stage helpers
    # ------------------------------------------------------------------

    def _make_gate_handler(
        self,
        gate_instance: FlextInfraGate,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        gates_sink: MutableMapping[str, m.Infra.GateExecution],
    ) -> p.Cli.PipelineStage:
        """Build a pipeline stage handler that executes a single gate.

        The handler only records the GateExecution into *gates_sink*; reporting
        happens after the wave, in declared gate order.

        Returns:
            The resulting ``p.Cli.PipelineStage``.

        """
        gate_id = gate_instance.gate_id
        project_name = project_dir.name

        def _handler(
            _pipeline_ctx: p.Cli.PipelineStageContext,
            /,
        ) -> p.Result[m.Cli.PipelineStageResult]:
            """Run the gate and record its execution in the sink.

            Returns:
                The resulting ``p.Result[m.Cli.PipelineStageResult]``.

            """
            gate_ctx = m.Infra.GateContext(
                repository_root=ctx.repository_root,
                reports_dir=ctx.reports_dir,
                apply_fixes=ctx.apply_fixes,
                check_only=ctx.check_only,
                fail_fast=ctx.fail_fast,
                ruff_args=ctx.ruff_args,
                pyright_args=ctx.pyright_args,
            )
            execution = self._execute_gate(gate_instance, project_dir, gate_ctx)
            gates_sink[gate_id] = execution
            self._gate_logger.info(
                "gate_executed",
                project=project_name,
                gate=gate_id,
                passed=execution.result.passed,
                elapsed=execution.result.duration,
            )
            if not execution.result.passed:
                return r[m.Cli.PipelineStageResult].fail(
                    f"{gate_id} failed for {project_name} "
                    f"with {len(execution.issues)} findings",
                )
            return r[m.Cli.PipelineStageResult].ok(
                m.Cli.PipelineStageResult(
                    stage_id=gate_id,
                    status=c.Cli.PipelineStageStatus.OK,
                    output={"findings": execution.finding_count},
                ),
            )

        return _handler

    @staticmethod
    def _execute_gate(
        gate_instance: FlextInfraGate,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.GateExecution:
        """Run fix-only under ``--apply``; check-only otherwise.

        Single-pass verb law: the mutating verb runs exactly one operation per
        gate — never a check pass before or after the fix. The fix execution
        already reports what its tool could not repair (the fix execution
        takes the fixer's exit status as its verdict); enforcing that residue belongs to
        the read-only ``make check``. Gates without a fix contract fall
        through to their read-only check, so an ``--apply`` selection over a
        read-only gate still executes it instead of silently skipping.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        """
        if ctx.apply_fixes and (not ctx.check_only) and gate_instance.can_fix:
            return gate_instance.fix(project_dir, ctx)
        return gate_instance.check(project_dir, ctx)


__all__: list[str] = ["FlextInfraWorkspaceCheckGatesMixin"]
