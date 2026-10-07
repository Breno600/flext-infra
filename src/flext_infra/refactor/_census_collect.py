"""Census per-module inventory + workspace-report assembly — extracted concern.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra.models

if TYPE_CHECKING:
    from flext_infra.protocols
    from flext_infra.typings


class FlextInfraRefactorCensusCollectMixin:
    """Inventory one module and assemble the WorkspaceReport."""

    if TYPE_CHECKING:

        @property
        def effective_dry_run(self) -> bool: ...

        def _validated_project_reports(
            self,
            rope: p.Infra.RopeWorkspaceDsl,
            project_reports: t.VariadicTuple[m.Infra.ProjectReport],
        ) -> t.VariadicTuple[m.Infra.ProjectReport]: ...

        @staticmethod
        def _project_name_for_module(
            module: m.Infra.RopeModuleIndexEntry,
            convention: m.Infra.RopeModuleConvention,
        ) -> str: ...
        @staticmethod
        def _include_object(
            item: m.Infra.Object,
            *,
            selected_families: frozenset[str],
            selected_kinds: frozenset[str] | None,
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
        """Inventory one module, accumulating its selected objects per project.

        A Rope failure on a module escapes with its cause: a census that skips
        the modules it could not read reports a partial workspace as whole.
        """
        convention = rope.convention(module.file_path)
        project = self._project_name_for_module(module, convention)
        if not project:
            return
        findings.report_projects.add(project)
        objects = tuple(
            item
            for item in rope.objects(
                module.file_path,
                include_local_scopes=scan_config.include_local_scopes,
                include_references=scan_config.include_object_references,
            )
            if self._include_object(
                item,
                selected_families=scan_config.selected_families,
                selected_kinds=scan_config.selected_kinds,
            )
        )
        if objects:
            findings.project_objects.setdefault(project, []).extend(objects)

    def _assemble_report(
        self,
        rope: p.Infra.RopeWorkspaceDsl,
        *,
        findings: m.Infra.ScanFindings,
        scan_config: m.Infra.ScanConfig,
    ) -> m.Infra.WorkspaceReport:
        """Aggregate per-project inventories into the workspace census report.

        In dry-run the removal candidates are previewed through the gates and
        only the ones that pass stay candidates.

        Returns:
            The resulting ``m.Infra.WorkspaceReport``.

        """
        duplicates = self._duplicate_groups(tuple(findings.project_objects.values()))
        duplicate_keys = frozenset(
            self._object_key(item)
            for group in duplicates
            for item in group.definitions[1:]
        )
        project_reports = tuple(
            self._project_report(
                project,
                findings=findings,
                duplicate_keys=duplicate_keys,
                scan_config=scan_config,
            )
            for project in sorted(
                findings.report_projects | set(findings.project_objects),
            )
        )
        if self.effective_dry_run:
            project_reports = self._validated_project_reports(rope, project_reports)
        return m.Infra.WorkspaceReport(
            projects=project_reports,
            total_objects=sum(report.objects_total for report in project_reports),
            total_violations=sum(report.violations_total for report in project_reports),
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
