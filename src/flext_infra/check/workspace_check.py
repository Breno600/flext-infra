"""FLEXT infrastructure workspace checker.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import ClassVar, override

from flext_infra import c, config, m, p, r, t, u
from flext_infra.base import FlextInfraServiceBase
from flext_infra.check._workspace_check_reports import (
    FlextInfraWorkspaceCheckReportsMixin,
)
from flext_infra.check.gate_registry import FlextInfraGateRegistry
from flext_infra.check.workspace_check_gates import FlextInfraWorkspaceCheckGatesMixin


class FlextInfraWorkspaceChecker(
    FlextInfraServiceBase[bool],
    FlextInfraWorkspaceCheckGatesMixin,
    FlextInfraWorkspaceCheckReportsMixin,
):
    """Run workspace quality gates and generate reports."""

    _repository_root: Path
    _registry: FlextInfraGateRegistry
    _default_reports_dir: Path
    model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        arbitrary_types_allowed=True,
    )

    @override
    def model_post_init(self, __context: t.ScalarMapping | None, /) -> None:
        """Initialize private gate state from validated service fields."""
        super().model_post_init(__context)
        self._repository_root = self.repository_root
        self._registry = FlextInfraGateRegistry()
        self._default_reports_dir = u.Cli.resolve_report_dir(
            self._repository_root,
            c.Infra.PROJECT,
            c.Infra.VERB_CHECK,
        )

    @staticmethod
    def parse_tool_args(raw: str | None) -> t.StrSequence:
        """Parse extra gate arguments passed as a shell-style string.

        Returns:
            The resulting ``t.StrSequence``.

        """
        if raw is None:
            return list[str]()
        return [item for item in shlex.split(raw) if item]

    @staticmethod
    def resolve_gates(gates: t.StrSequence) -> p.Result[list[str]]:
        """Validate exact, unique requested gate names without normalization.

        Returns:
            The resulting ``p.Result[list[str]]``.

        """
        if not gates:
            return r[list[str]].fail("ERROR: at least one quality gate is required")
        resolved: list[str] = []
        for gate in gates:
            if not gate or gate != gate.strip():
                return r[list[str]].fail(f"ERROR: invalid gate name {gate!r}")
            if gate not in c.Infra.ALLOWED_GATES:
                return r[list[str]].fail(f"ERROR: unknown gate '{gate}'")
            if gate in resolved:
                return r[list[str]].fail(f"ERROR: duplicate gate '{gate}'")
            resolved.append(gate)
        return r[list[str]].ok(list(resolved))

    @override
    def execute(self) -> p.Result[bool]:
        """Execute.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return r[bool].fail("Use execute_command() directly")

    def execute_payload(self, params: m.Infra.RunCommand) -> p.Result[bool]:
        """Execute quality gates from the canonical check command payload.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        project_targets_result = self._resolve_project_targets(params)
        if project_targets_result.failure:
            return r[bool].from_failure(project_targets_result)
        project_targets = project_targets_result.value
        # An omitted gate selection is the typed SSOT default: every default
        # check gate (the set an unset CI token runs), never an empty run.
        gates = list(params.gates or config.Infra.codegen.make.check_gates_default)
        gate_ctx = m.Infra.GateContext(
            repository_root=params.repository_root,
            reports_dir=params.reports_dir_path,
            apply_fixes=params.apply,
            check_only=params.check_only,
            fail_fast=params.fail_fast,
            ruff_args=tuple(self.parse_tool_args(params.ruff_args)),
            pyright_args=tuple(self.parse_tool_args(params.pyright_args)),
        )
        run_result = self.run_projects(
            projects=project_targets,
            gates=gates,
            reports_dir=params.reports_dir_path,
            fail_fast=params.fail_fast,
            ctx=gate_ctx,
        )
        if run_result.failure:
            return r[bool].from_failure(run_result)
        if len(run_result.value) != len(project_targets):
            return r[bool].fail(
                "quality checks did not execute every requested project: "
                f"{len(run_result.value)}/{len(project_targets)}",
            )
        failed_projects = [
            project for project in run_result.value if not project.passed
        ]
        if failed_projects:
            failed_names = ", ".join(project.project for project in failed_projects)
            total_findings = sum(
                len(execution.issues)
                for project in failed_projects
                for execution in project.gates.values()
            )
            return r[bool].fail(
                f"quality checks failed for: {failed_names} "
                f"({total_findings} findings; see the check summary and reports)",
            )
        return r[bool].ok(value=True)

    @staticmethod
    def _resolve_project_targets(
        params: m.Infra.RunCommand,
    ) -> p.Result[t.SequenceOf[m.Infra.CheckProjectTarget]]:
        """Resolve the selected projects; an omitted selection is this repository.

        Every repository evaluates only itself: an
        omitted ``--projects`` never widens to the declared members, and a root
        that is not a project fails loud through the topology owner.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.CheckProjectTarget]]``.

        """
        requested = params.project_names
        if requested:
            return r[t.SequenceOf[m.Infra.CheckProjectTarget]].ok(
                tuple(
                    m.Infra.CheckProjectTarget(
                        name=project_name,
                        path=params.repository_root / project_name,
                    )
                    for project_name in requested
                ),
            )
        resolved = u.Infra.resolve_projects(params.repository_root, (".",))
        if resolved.failure:
            return r[t.SequenceOf[m.Infra.CheckProjectTarget]].from_failure(resolved)
        return r[t.SequenceOf[m.Infra.CheckProjectTarget]].ok(
            tuple(
                m.Infra.CheckProjectTarget(name=project.name, path=project.path)
                for project in resolved.value
            ),
        )

    def format(self, project_dir: Path) -> p.Result[m.Infra.GateResult]:
        """Run format checks for one project.

        Returns:
            The resulting ``p.Result[m.Infra.GateResult]``.

        """
        return r[m.Infra.GateResult].ok(
            self._run_gate(c.Infra.FORMAT, project_dir).result,
        )

    def lint(self, project_dir: Path) -> p.Result[m.Infra.GateResult]:
        """Run lint checks for one project.

        Returns:
            The resulting ``p.Result[m.Infra.GateResult]``.

        """
        return r[m.Infra.GateResult].ok(
            self._run_gate(c.Infra.LINT, project_dir).result,
        )

    def run_project(
        self,
        project: str,
        gates: t.StrSequence,
    ) -> p.Result[t.SequenceOf[m.Infra.ProjectResult]]:
        """Run selected gates for one project.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.ProjectResult]]``.

        """
        return self.run_projects([project], list(gates))

    def run_projects(
        self,
        projects: t.StrSequence | t.SequenceOf[m.Infra.CheckProjectTarget],
        gates: t.StrSequence,
        *,
        reports_dir: Path | None = None,
        fail_fast: bool = c.Infra.CHECK_FAIL_FAST_DEFAULT,
        ctx: m.Infra.GateContext | None = None,
    ) -> p.Result[t.SequenceOf[m.Infra.ProjectResult]]:
        """Run selected gates in one exclusively owned invocation report directory.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.ProjectResult]]``.

        """
        resolved_gates_result = self.resolve_gates(gates)
        if resolved_gates_result.failure:
            return r[t.SequenceOf[m.Infra.ProjectResult]].from_failure(
                resolved_gates_result,
            )
        resolved_gates = resolved_gates_result.value
        targets = self._project_targets(projects)
        if not targets:
            return r[t.SequenceOf[m.Infra.ProjectResult]].fail(
                "quality check selected no projects",
            )
        unrunnable = [
            str(target.path / c.PYPROJECT_FILENAME)
            for target in targets
            if not (target.path / c.PYPROJECT_FILENAME).is_file()
        ]
        if unrunnable:
            return r[t.SequenceOf[m.Infra.ProjectResult]].fail(
                "quality check selected projects without a pyproject: "
                + ", ".join(unrunnable),
            )
        reports_root = reports_dir or self._default_reports_dir
        dir_ensure = u.Cli.ensure_dir(reports_root)
        if dir_ensure.failure:
            return r[t.SequenceOf[m.Infra.ProjectResult]].from_failure(dir_ensure)
        report_base = reports_root / u.generate_id()
        report_base.mkdir(exist_ok=False)
        effective_ctx = ctx or m.Infra.GateContext(
            repository_root=self._repository_root,
            reports_dir=report_base,
            fail_fast=fail_fast,
        )
        if effective_ctx.fail_fast != fail_fast:
            return r[t.SequenceOf[m.Infra.ProjectResult]].fail(
                "gate context fail_fast disagrees with the requested project policy",
            )
        effective_ctx = effective_ctx.model_copy(update={"reports_dir": report_base})
        outcome = self._run_project_loop(
            targets,
            resolved_gates,
            effective_ctx,
            fail_fast=fail_fast,
        )
        return self._write_reports_and_summary(
            resolved_gates,
            report_base,
            outcome,
            m.Infra.CheckReportSummary(
                targets=tuple(
                    m.Infra.CheckProjectTarget(
                        name=target.path.name,
                        path=target.path.resolve(),
                    )
                    for target in targets
                ),
                results=tuple(outcome.results),
                selected_files=effective_ctx.selected_files,
            ),
        )

    def _project_targets(
        self,
        projects: t.StrSequence | t.SequenceOf[m.Infra.CheckProjectTarget],
    ) -> t.SequenceOf[m.Infra.CheckProjectTarget]:
        """Return typed project targets from public names or internal selections.

        Returns:
            Typed project targets from public names or internal selections.

        """
        targets: list[m.Infra.CheckProjectTarget] = []
        for project in projects:
            if isinstance(project, m.Infra.CheckProjectTarget):
                targets.append(project)
                continue
            targets.append(
                m.Infra.CheckProjectTarget(
                    name=project,
                    path=self._repository_root / project,
                ),
            )
        return tuple(targets)


__all__: list[str] = ["FlextInfraWorkspaceChecker"]
