"""Census per-module scan + workspace-report assembly — extracted concern."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import m, u

from ._census_rules_dispatch import FlextInfraRefactorCensusRulesDispatchMixin
from ._census_validate import FlextInfraRefactorCensusValidateMixin

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t

_ROPE_SAFE_EXCEPTIONS: t.VariadicTuple[type[BaseException]] = (
    *u.Infra.rope_runtime_errors(),
    *u.Infra.rope_error_types(),
    RecursionError,
    SyntaxError,
    ValueError,
    RuntimeError,
)


class FlextInfraRefactorCensusCollectMixin(
    FlextInfraRefactorCensusRulesDispatchMixin, FlextInfraRefactorCensusValidateMixin
):
    """Scan one module (inventory + rules) and assemble the WorkspaceReport."""

    if TYPE_CHECKING:

        @property
        def effective_dry_run(self) -> bool: ...

        @staticmethod
        def _project_name_for_module(
            module: m.Infra.RopeModuleIndexEntry,
            convention: m.Infra.RopeModuleConvention,
        ) -> str: ...
        def _handle_rope_stage_failure(
            self, *, file_path: Path, stage: str, exc: BaseException
        ) -> None: ...
        @staticmethod
        def _include_object(
            item: m.Infra.Object,
            *,
            kind_names: t.StrSequence | None,
            selected_families: frozenset[str],
            selected_kinds: frozenset[str] | None = None,
        ) -> bool: ...
        @staticmethod
        def _duplicate_groups(
            project_objects: t.VariadicTuple[t.SequenceOf[m.Infra.Object]],
        ) -> t.VariadicTuple[m.Infra.DuplicateGroup]: ...
        @staticmethod
        def _object_key(item: m.Infra.Object) -> str: ...
        def _project_report(
            self,
            project: str,
            *,
            objects: t.VariadicTuple[m.Infra.Object],
            seed_violations: t.VariadicTuple[m.Infra.Violation],
            fixes: t.VariadicTuple[m.Infra.Fix],
            duplicate_keys: frozenset[str],
            rule_names: t.StrSequence | None,
            selected_rules: frozenset[str] | None = None,
        ) -> m.Infra.ProjectReport: ...

    def _scan_module(
        self,
        rope: p.Infra.RopeWorkspaceDsl,
        module: m.Infra.RopeModuleIndexEntry,
        scan_config: m.Infra.ScanConfig,
        *,
        project_objects: t.MappingKV[str, t.MutableSequenceOf[m.Infra.Object]],
        project_violations: t.MappingKV[str, t.MutableSequenceOf[m.Infra.Violation]],
        project_fixes: t.MappingKV[str, t.MutableSequenceOf[m.Infra.Fix]],
        report_projects: set[str],
    ) -> None:
        """Scan one module, accumulating objects/violations/fixes per project."""
        convention = rope.convention(module.file_path)
        project = self._project_name_for_module(module, convention)
        if not project:
            return
        module_objects: t.VariadicTuple[m.Infra.Object] | None = None
        objects: t.VariadicTuple[m.Infra.Object] = ()
        inventory_failed = False
        if scan_config.collect_object_inventory:
            try:
                module_objects = tuple(
                    rope.objects(
                        module.file_path,
                        include_local_scopes=scan_config.include_local_scopes,
                        include_references=scan_config.include_object_references,
                    )
                )
            except _ROPE_SAFE_EXCEPTIONS as exc:
                self._handle_rope_stage_failure(
                    file_path=module.file_path, stage="inventory", exc=exc
                )
                inventory_failed = True
            else:
                inventory_objects = module_objects or ()
                objects = tuple(
                    item
                    for item in inventory_objects
                    if self._include_object(
                        item,
                        kind_names=scan_config.kind_names,
                        selected_families=scan_config.selected_families,
                        selected_kinds=scan_config.selected_kinds,
                    )
                )
                if objects:
                    project_objects[project].extend(objects)
        if objects:
            report_projects.add(project)
        if inventory_failed:
            return
        try:
            violations, fixes = self._module_rules(
                rope,
                module.file_path,
                objects=module_objects,
                project_name=project,
                scan_config=scan_config,
            )
        except _ROPE_SAFE_EXCEPTIONS as exc:
            self._handle_rope_stage_failure(
                file_path=module.file_path, stage="rules", exc=exc
            )
        else:
            report_projects.add(project)
            if not objects and not violations and not fixes:
                return
            project_violations[project].extend(violations)
            project_fixes[project].extend(fixes)

    def _assemble_report(
        self,
        rope: p.Infra.RopeWorkspaceDsl,
        *,
        project_objects: t.MappingKV[str, t.SequenceOf[m.Infra.Object]],
        project_violations: t.MappingKV[str, t.SequenceOf[m.Infra.Violation]],
        project_fixes: t.MappingKV[str, t.SequenceOf[m.Infra.Fix]],
        report_projects: set[str],
        rule_names: t.StrSequence | None,
        selected_rules: frozenset[str] | None,
    ) -> m.Infra.WorkspaceReport:
        """Aggregate per-project scans into the final workspace census report."""
        duplicates = self._duplicate_groups(tuple(project_objects.values()))
        duplicate_keys = frozenset(
            self._object_key(item)
            for group in duplicates
            for item in group.definitions[1:]
        )
        report_project_names = tuple(
            sorted(
                report_projects
                | set(project_objects)
                | set(project_violations)
                | set(project_fixes)
            )
        )
        project_reports = tuple(
            self._project_report(
                project,
                objects=tuple(project_objects[project]),
                seed_violations=tuple(project_violations[project]),
                fixes=tuple(project_fixes[project]),
                duplicate_keys=duplicate_keys,
                rule_names=rule_names,
                selected_rules=selected_rules,
            )
            for project in report_project_names
        )
        if self.effective_dry_run:
            project_reports = self._validated_project_reports(rope, project_reports)
        return m.Infra.WorkspaceReport(
            projects=project_reports,
            total_objects=sum(report.objects_total for report in project_reports),
            total_violations=sum(report.violations_total for report in project_reports),
            total_fixable=sum(
                1
                for report in project_reports
                for violation in report.violations
                if violation.fixable
            ),
            fixes_total=sum(len(report.fixes) for report in project_reports),
            duplicates=duplicates,
            unused_count=sum(report.unused_count for report in project_reports),
            removal_candidate_count=sum(
                report.removal_candidate_count for report in project_reports
            ),
            removal_candidates=tuple(
                candidate
                for report in project_reports
                for candidate in report.removal_candidates
            ),
        )


__all__: list[str] = ["FlextInfraRefactorCensusCollectMixin"]
