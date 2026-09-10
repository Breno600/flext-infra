"""FLEXT infrastructure workspace checker."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import override

from flext_infra import c, m, p, r, t, u
from flext_infra.base import FlextInfraServiceBase

from ._workspace_check_reports import FlextInfraWorkspaceCheckReportsMixin
from .workspace_check_gates import (
    FlextInfraGateRegistry,
    FlextInfraWorkspaceCheckGatesMixin,
)


class FlextInfraWorkspaceChecker(
    FlextInfraServiceBase[bool],
    FlextInfraWorkspaceCheckGatesMixin,
    FlextInfraWorkspaceCheckReportsMixin,
):
    """Run workspace quality gates and generate reports."""

    _repository_root: Path
    _registry: FlextInfraGateRegistry
    _default_reports_dir: Path

    def __init__(
        self,
        repository_root: Path | None = None,
        *,
        gate_runners: t.MappingKV[str, p.Cli.CommandRunner] | None = None,
    ) -> None:
        """Initialize workspace checker services and paths."""
        resolved_root = u.Infra.resolve_repository_root_or_cwd(repository_root)
        super().__init__(repository_root=resolved_root)
        self._repository_root = self.repository_root
        self._registry = FlextInfraGateRegistry(runners=gate_runners)
        report_dir = u.Cli.resolve_report_dir(
            self._repository_root, c.Infra.PROJECT, c.Infra.VERB_CHECK
        )
        dir_result = u.Cli.ensure_dir(report_dir)
        if dir_result.failure:
            self._default_reports_dir = (
                self._repository_root / c.Infra.REPORTS_DIR_NAME / c.Infra.VERB_CHECK
            )
        else:
            self._default_reports_dir = report_dir

    @staticmethod
    def parse_tool_args(raw: str | None) -> t.StrSequence:
        """Parse extra gate arguments passed as a shell-style string."""
        if raw is None:
            return list[str]()
        return [item for item in shlex.split(raw) if item]

    @staticmethod
    def resolve_gates(gates: t.StrSequence) -> p.Result[list[str]]:
        """Validate exact, unique requested gate names without normalization."""
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
        """Execute."""
        return r[bool].fail("Use execute_command() directly")

    @classmethod
    def execute_payload(cls, params: m.Infra.RunCommand) -> p.Result[bool]:
        """Execute quality gates from the canonical check command payload."""
        checker = cls(repository_root=params.repository_root)
        project_targets_result = cls._resolve_project_targets(params)
        if project_targets_result.failure:
            return r[bool].from_failure(project_targets_result)
        project_targets = project_targets_result.value
        gates = list(params.gates)
        if not gates:
            return r[bool].fail("check requires at least one registered gate")
        gate_ctx = m.Infra.GateContext(
            repository_root=params.repository_root,
            reports_dir=params.reports_dir_path,
            apply_fixes=params.fix,
            check_only=params.check_only,
            ruff_args=tuple(cls.parse_tool_args(params.ruff_args)),
            pyright_args=tuple(cls.parse_tool_args(params.pyright_args)),
        )
        run_result = checker.run_projects(
            projects=project_targets,
            gates=gates,
            reports_dir=params.reports_dir_path,
            fail_fast=params.fail_fast,
            ctx=gate_ctx,
        )
        if run_result.failure:
            return r[bool].from_failure(run_result)
        failed_projects = [
            project for project in run_result.value if not project.passed
        ]
        if failed_projects:
            failed_names = ", ".join(project.project for project in failed_projects)
            return r[bool].fail(f"quality gates failed for: {failed_names}")
        return r[bool].ok(True)

    @staticmethod
    def _resolve_project_targets(
        params: m.Infra.RunCommand,
    ) -> p.Result[t.SequenceOf[m.Infra.CheckProjectTarget]]:
        """Resolve explicit projects or discover the workspace project set."""
        requested = params.project_names
        if requested:
            return r[t.SequenceOf[m.Infra.CheckProjectTarget]].ok(
                tuple(
                    m.Infra.CheckProjectTarget.from_workspace_name(
                        params.repository_root, project_name
                    )
                    for project_name in requested
                )
            )
        discovered = u.Infra.resolve_projects(params.repository_root, ())
        if discovered.failure:
            return r[t.SequenceOf[m.Infra.CheckProjectTarget]].from_failure(discovered)
        project_targets = tuple(
            m.Infra.CheckProjectTarget(name=project.name, path=project.path)
            for project in discovered.value
        )
        if not project_targets:
            return r[t.SequenceOf[m.Infra.CheckProjectTarget]].fail(
                "no projects discovered"
            )
        return r[t.SequenceOf[m.Infra.CheckProjectTarget]].ok(project_targets)

    def format(self, project_dir: Path) -> p.Result[m.Infra.GateResult]:
        """Run format checks for one project."""
        return r[m.Infra.GateResult].ok(
            self._run_gate(c.Infra.FORMAT, project_dir).result
        )

    def lint(self, project_dir: Path) -> p.Result[m.Infra.GateResult]:
        """Run lint checks for one project."""
        return r[m.Infra.GateResult].ok(
            self._run_gate(c.Infra.LINT, project_dir).result
        )

    def run_project(
        self, project: str, gates: t.StrSequence
    ) -> p.Result[t.SequenceOf[m.Infra.ProjectResult]]:
        """Run selected gates for one project."""
        return self.run_projects([project], list(gates))

    def run_projects(
        self,
        projects: t.StrSequence | t.SequenceOf[m.Infra.CheckProjectTarget],
        gates: t.StrSequence,
        *,
        reports_dir: Path | None = None,
        fail_fast: bool = False,
        ctx: m.Infra.GateContext | None = None,
    ) -> p.Result[t.SequenceOf[m.Infra.ProjectResult]]:
        """Run selected gates for multiple projects."""
        resolved_gates_result = self.resolve_gates(gates)
        if resolved_gates_result.failure:
            return r[t.SequenceOf[m.Infra.ProjectResult]].from_failure(
                resolved_gates_result
            )
        resolved_gates = resolved_gates_result.value
        report_base = reports_dir or self._default_reports_dir
        dir_ensure = u.Cli.ensure_dir(report_base)
        if dir_ensure.failure:
            return r[t.SequenceOf[m.Infra.ProjectResult]].from_failure(dir_ensure)
        effective_ctx = ctx or m.Infra.GateContext(
            repository_root=self._repository_root, reports_dir=report_base
        )
        outcome = self._run_project_loop(
            self._project_targets(projects),
            resolved_gates,
            effective_ctx,
            fail_fast=fail_fast,
        )
        return self._write_reports_and_summary(resolved_gates, report_base, outcome)

    def _project_targets(
        self, projects: t.StrSequence | t.SequenceOf[m.Infra.CheckProjectTarget]
    ) -> t.SequenceOf[m.Infra.CheckProjectTarget]:
        """Return typed project targets from public names or internal selections."""
        targets: list[m.Infra.CheckProjectTarget] = []
        for project in projects:
            if isinstance(project, m.Infra.CheckProjectTarget):
                targets.append(project)
                continue
            targets.append(
                m.Infra.CheckProjectTarget.from_workspace_name(
                    self._repository_root, project
                )
            )
        return tuple(targets)


__all__: list[str] = ["FlextInfraWorkspaceChecker"]
