"""Automated namespace enforcement orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_cli import cli

from flext_core import r
from flext_infra import m, u

from ._namespace_enforcer_project import FlextInfraNamespaceEnforcerProjectMixin
from .namespace_enforcer_phases import FlextInfraNamespaceEnforcerPhasesMixin

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraNamespaceEnforcer(
    FlextInfraNamespaceEnforcerPhasesMixin, FlextInfraNamespaceEnforcerProjectMixin
):
    """Orchestrate namespace enforcement across a workspace."""

    def __init__(self, *, repository_root: Path) -> None:
        """Initialize with the repository root path."""
        super().__init__()
        self._repository_root = repository_root.resolve()
        self._rope_project: t.Infra.RopeProject = u.Infra.init_rope_project(
            self._repository_root
        )

    @override
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
            workspace=str(self._repository_root), projects=project_reports
        )

    @override
    def _resolve_project_roots(
        self, *, project_names: t.StrSequence | None = None
    ) -> t.SequenceOf[Path]:
        """Discover and optionally filter project roots."""
        project_roots = u.Infra.discover_project_roots(
            repository_root=self._repository_root
        )
        project_roots = [
            project_root
            for project_root in project_roots
            if u.Infra.namespace_enabled(project_root)
        ]
        if project_names:
            name_set = set(project_names)
            project_roots = [r for r in project_roots if r.name in name_set]
        return project_roots

    @override
    def _detect_and_apply[V](
        self,
        *,
        py_files: t.SequenceOf[Path],
        detect_fn: Callable[[Path], t.SequenceOf[V]],
        rewrite_fn: Callable[[t.MutableSequenceOf[V]], None] | None,
        apply: bool,
    ) -> t.MutableSequenceOf[V]:
        """Run detect -> optional apply -> re-detect cycle for a violation type.

        Re-detection only runs when apply=True AND a real rewrite_fn is provided.
        """
        violations: t.MutableSequenceOf[V] = []
        for py_file in py_files:
            violations.extend(detect_fn(py_file))
        if not (apply and violations and rewrite_fn is not None):
            return violations
        rewrite_fn(violations)
        self._rope_project.validate(self._rope_project.root)
        post_violations: t.MutableSequenceOf[V] = []
        for py_file in py_files:
            post_violations.extend(detect_fn(py_file))
        return post_violations

    @staticmethod
    def render_text(report: m.Infra.WorkspaceEnforcementReport) -> str:
        """Render a workspace enforcement report as plain text."""
        projects = report.projects
        lines = [
            "Namespace Enforcement Report",
            f"Workspace: {report.workspace}",
            f"Projects: {len(report.projects)}",
            f"Violations: {'YES' if report.has_violations else 'NO'}",
            f"Missing facades: {sum(1 for project in projects for facade in project.facade_statuses if not facade.exists)}",
            f"Loose objects: {sum(len(project.loose_objects) for project in projects)}",
            f"Import violations: {sum(len(project.import_violations) for project in projects)}",
            f"Namespace source violations: {sum(len(project.namespace_source_violations) for project in projects)}",
            f"Internal import violations: {sum(len(project.internal_import_violations) for project in projects)}",
            f"Private import bypass violations: {sum(len(project.private_import_bypass_violations) for project in projects)}",
            f"Manual protocol violations: {sum(len(project.manual_protocol_violations) for project in projects)}",
            f"Cyclic imports: {sum(len(project.cyclic_imports) for project in projects)}",
            f"Runtime alias violations: {sum(len(project.runtime_alias_violations) for project in projects)}",
            f"Future violations: {sum(len(project.future_violations) for project in projects)}",
            f"Manual typing violations: {sum(len(project.manual_typing_violations) for project in projects)}",
            f"Compatibility alias violations: {sum(len(project.compatibility_alias_violations) for project in projects)}",
            f"Foreign canonical alias violations: {sum(len(project.foreign_canonical_alias_violations) for project in projects)}",
            f"Class placement violations: {sum(len(project.class_placement_violations) for project in projects)}",
            f"Bare except violations: {sum(len(project.bare_except_violations) for project in projects)}",
            f"Print violations: {sum(len(project.print_violations) for project in projects)}",
            f"Breakpoint violations: {sum(len(project.breakpoint_violations) for project in projects)}",
            f"Open-encoding violations: {sum(len(project.open_encoding_violations) for project in projects)}",
            f"Dict annotation violations: {sum(len(project.dict_annotation_violations) for project in projects)}",
            f"typing.Dict attr violations: {sum(len(project.typing_dict_attr_violations) for project in projects)}",
            f"typing.Dict import violations: {sum(len(project.typing_dict_import_violations) for project in projects)}",
            f"Hardcoded-version violations: {sum(len(project.hardcoded_version_violations) for project in projects)}",
            f"Parse failures: {sum(len(project.parse_failures) for project in projects)}",
            f"Files scanned: {sum(project.files_scanned for project in projects)}",
        ]
        return "\n".join(lines)

    @classmethod
    def execute_command(
        cls, params: m.Infra.RefactorNamespaceEnforceInput
    ) -> p.Result[m.Infra.WorkspaceEnforcementReport]:
        """Execute namespace enforcement directly from the canonical payload."""
        enforcer = cls(repository_root=params.repository_root)
        report = enforcer.enforce(
            apply=params.apply, project_names=params.project_names, gates=params.gates
        )
        cli.display_text(cls.render_text(report))
        has_violations: bool = report.has_violations
        if has_violations:
            return r[m.Infra.WorkspaceEnforcementReport].fail(
                "Namespace violations found"
            )
        return r[m.Infra.WorkspaceEnforcementReport].ok(report)


__all__: list[str] = ["FlextInfraNamespaceEnforcer"]
