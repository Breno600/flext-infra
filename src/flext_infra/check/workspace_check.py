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

    _repository_root: Path = u.PrivateAttr()
    _registry: FlextInfraGateRegistry = u.PrivateAttr()
    _default_reports_dir: Path = u.PrivateAttr()
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
        selected_files_result = self._resolve_selected_files(params)
        if selected_files_result.failure:
            return r[bool].from_failure(selected_files_result)
        selected_files = selected_files_result.value
        project_targets_result = self._resolve_project_targets(params, selected_files)
        if project_targets_result.failure:
            return r[bool].from_failure(project_targets_result)
        project_targets = project_targets_result.value
        # An omitted gate selection is the typed SSOT default: every default
        # check gate (the set an unset CI token runs), never an empty run.
        gates = list(params.gates or config.Infra.codegen.make.check_gates_default)
        if selected_files:
            u.Cli.info(
                f"file-gate: source={selected_files[0]} gates={gates} "
                "selection=CLI:check run --gates"
            )
        gate_ctx = m.Infra.GateContext(
            repository_root=params.repository_root,
            reports_dir=params.reports_dir_path,
            apply_fixes=params.apply,
            check_only=params.check_only,
            fail_fast=params.fail_fast,
            ruff_args=tuple(self.parse_tool_args(params.ruff_args)),
            pyright_args=tuple(self.parse_tool_args(params.pyright_args)),
            selected_files=selected_files,
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
        return self._summarize_project_results(run_result.value, project_targets)

    @classmethod
    def _resolve_selected_files(
        cls,
        params: m.Infra.RunCommand,
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Resolve the optional ``--file`` selection into one repository file.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        """
        if params.file is None:
            return r[t.VariadicTuple[Path]].ok(())
        if not params.gates:
            return r[t.VariadicTuple[Path]].fail(
                "--file requires explicit canonical --gates selection"
            )
        if (
            params.apply
            or params.ruff_args is not None
            or params.pyright_args is not None
            or (params.project_names and tuple(params.project_names) != (".",))
        ):
            return r[t.VariadicTuple[Path]].fail(
                "file-gate requires read-only local selection without tool overrides",
            )
        return cls._resolve_repository_file(params.repository_root, params.file)

    @staticmethod
    def _resolve_repository_file(
        repository_root: Path,
        raw: str,
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Resolve a literal repository-relative source file without symlinks.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        """
        relative = Path(raw)
        if (
            not raw
            or raw != raw.strip()
            or relative.is_absolute()
            or any(part in {"", ".", ".."} for part in raw.split("/"))
        ):
            return r[t.VariadicTuple[Path]].fail(
                f"invalid literal repository-relative FILE: {raw!r}"
            )
        root = repository_root.resolve(strict=True)
        selected = root / relative
        current = root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                return r[t.VariadicTuple[Path]].fail(
                    f"FILE has a symlink component: {current}"
                )
        if (
            not selected.is_file()
            or not selected.resolve(strict=True).is_relative_to(root)
            or selected.suffix not in {".py", ".pyi"}
        ):
            return r[t.VariadicTuple[Path]].fail(
                f"FILE is not an existing repository file: {selected}"
            )
        return r[t.VariadicTuple[Path]].ok((selected,))

    @staticmethod
    def _summarize_project_results(
        results: t.SequenceOf[m.Infra.ProjectResult],
        project_targets: t.SequenceOf[m.Infra.CheckProjectTarget],
    ) -> p.Result[bool]:
        """Fail unless every requested project executed and passed.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if len(results) != len(project_targets):
            return r[bool].fail(
                "quality checks did not execute every requested project: "
                f"{len(results)}/{len(project_targets)}",
            )
        failed_projects = [project for project in results if not project.passed]
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
        selected_files: t.VariadicTuple[Path],
    ) -> p.Result[t.SequenceOf[m.Infra.CheckProjectTarget]]:
        """Resolve the selected projects; an omitted selection is this repository.

        Every repository evaluates only itself: an
        omitted ``--projects`` never widens to the declared members, and a root
        that is not a project fails loud through the topology owner.
        A literal file selects only its deepest declared project owner.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.CheckProjectTarget]]``.

        """
        if selected_files:
            discovered = u.Infra.resolve_projects(params.repository_root, ())
            if discovered.failure:
                return r[t.SequenceOf[m.Infra.CheckProjectTarget]].from_failure(
                    discovered,
                )
            owners = [
                project
                for project in discovered.value
                if selected_files[0].is_relative_to(project.path)
            ]
            if not owners:
                return r[t.SequenceOf[m.Infra.CheckProjectTarget]].fail(
                    f"FILE has no declared project owner: {selected_files[0]}",
                )
            owner = max(owners, key=lambda project: len(project.path.parts))
            return r[t.SequenceOf[m.Infra.CheckProjectTarget]].ok((
                m.Infra.CheckProjectTarget(name=owner.name, path=owner.path),
            ))
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
        """Run selected gates for multiple projects.

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
        report_base = reports_dir or self._default_reports_dir
        dir_ensure = u.Cli.ensure_dir(report_base)
        if dir_ensure.failure:
            return r[t.SequenceOf[m.Infra.ProjectResult]].from_failure(dir_ensure)
        effective_ctx = ctx or m.Infra.GateContext(
            repository_root=self._repository_root,
            reports_dir=report_base,
            fail_fast=fail_fast,
        )
        if effective_ctx.fail_fast != fail_fast:
            return r[t.SequenceOf[m.Infra.ProjectResult]].fail(
                "gate context fail_fast disagrees with the requested project policy",
            )
        outcome = self._run_project_loop(
            targets,
            resolved_gates,
            effective_ctx,
            fail_fast=fail_fast,
        )
        return self._write_reports_and_summary(resolved_gates, report_base, outcome)

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
