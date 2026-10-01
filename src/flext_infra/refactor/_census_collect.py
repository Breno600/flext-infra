"""Census per-module scan + workspace-report assembly — extracted concern."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from flext_infra import m, u

from ._census_rules_dispatch import FlextInfraRefactorCensusRulesDispatchMixin
from ._census_validate import FlextInfraRefactorCensusValidateMixin

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraRefactorCensusCollectMixin(
    FlextInfraRefactorCensusRulesDispatchMixin, FlextInfraRefactorCensusValidateMixin
):
    """Scan one module (inventory + rules) and assemble the WorkspaceReport."""

    _rope_safe_exceptions: ClassVar[t.VariadicTuple[type[BaseException]]] = (
        *u.Infra.rope_runtime_errors(),
        *u.Infra.rope_error_types(),
        RecursionError,
        SyntaxError,
        ValueError,
        RuntimeError,
    )

    if TYPE_CHECKING:

        @property
        def effective_dry_run(self) -> bool: ...

        @staticmethod
        def _project_name_for_module(
            module: m.Infra.RopeModuleIndexEntry,
            convention: m.Infra.RopeModuleConvention,
        ) -> str: ...
        @classmethod
        def _lightweight_symbol_index(
            cls, rope: p.Infra.RopeWorkspaceDsl, file_path: Path
        ) -> MutableMapping[str, t.Pair[str, int]]: ...
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
            findings: m.Infra.ScanFindings,
            duplicate_keys: frozenset[str],
            scan_config: m.Infra.ScanConfig,
        ) -> m.Infra.ProjectReport: ...

    def _scan_module(
        self,
        rope: p.Infra.RopeWorkspaceDsl,
        module: m.Infra.RopeModuleIndexEntry,
        scan_config: m.Infra.ScanConfig,
        *,
        findings: m.Infra.ScanFindings,
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
            except self._rope_safe_exceptions as exc:
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
                    findings.project_objects.setdefault(project, []).extend(objects)
        if objects:
            findings.report_projects.add(project)
        if inventory_failed:
            return
        try:
            violations, fixes = self._module_rules(
                m.Infra.ModuleScan(
                    rope=rope,
                    file_path=module.file_path,
                    project=project,
                    convention=convention,
                    objects=module_objects,
                    symbol_index=self._lightweight_symbol_index(rope, module.file_path),
                    scan_config=scan_config,
                )
            )
        except self._rope_safe_exceptions as exc:
            self._handle_rope_stage_failure(
                file_path=module.file_path, stage="rules", exc=exc
            )
        else:
            findings.report_projects.add(project)
            if not objects and not violations and not fixes:
                return
            findings.project_violations.setdefault(project, []).extend(violations)
            findings.project_fixes.setdefault(project, []).extend(fixes)

    def _assemble_report(
        self,
        rope: p.Infra.RopeWorkspaceDsl,
        *,
        findings: m.Infra.ScanFindings,
        scan_config: m.Infra.ScanConfig,
    ) -> m.Infra.WorkspaceReport:
        """Aggregate per-project scans into the final workspace census report."""
        duplicates = self._duplicate_groups(tuple(findings.project_objects.values()))
        duplicate_keys = frozenset(
            self._object_key(item)
            for group in duplicates
            for item in group.definitions[1:]
        )
        report_project_names = tuple(
            sorted(
                findings.report_projects
                | set(findings.project_objects)
                | set(findings.project_violations)
                | set(findings.project_fixes)
            )
        )
        project_reports = tuple(
            self._project_report(
                project,
                findings=findings,
                duplicate_keys=duplicate_keys,
                scan_config=scan_config,
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
