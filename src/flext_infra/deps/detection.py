"""Dependency detection and analysis service for deptry, pip-check, and typing stubs.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path

from flext_core import c as core_c, r
from flext_infra import c, m, p, t, u
from flext_infra.deps.detection_analysis import FlextInfraDependencyDetectionAnalysis


class FlextInfraDependencyDetectionService(FlextInfraDependencyDetectionAnalysis):
    """Runtime vs dev dependency detector using deptry, pip-check, and mypy stub analysis."""

    _log = u.fetch_logger(__name__)

    @staticmethod
    def classify_issues(
        issues: t.SequenceOf[t.JsonMapping],
    ) -> m.Infra.DeptryIssueGroups:
        """Classify deptry issues by error code (DEP001-DEP004)."""
        groups = m.Infra.DeptryIssueGroups(dep001=[], dep002=[], dep003=[], dep004=[])
        for item in issues:
            normalized_item: MutableMapping[str, t.Primitives | None] = {}
            for key, raw_value in item.items():
                if raw_value is None:
                    normalized_item[key] = ""
                    continue
                if isinstance(raw_value, core_c.PRIMITIVES_TYPES):
                    normalized_item[key] = raw_value
            error_obj = item.get(c.Infra.ERROR)
            if not isinstance(error_obj, Mapping):
                continue
            error_data = u.Cli.json_as_mapping(error_obj)
            if not error_data:
                continue
            code = error_data.get(c.Infra.CODE)
            bucket = {
                "DEP001": groups.dep001,
                "DEP002": groups.dep002,
                "DEP003": groups.dep003,
                "DEP004": groups.dep004,
            }.get(str(code) if code is not None else "")
            if bucket is not None:
                bucket.append(normalized_item)
        return groups

    def build_project_report(
        self,
        project_name: str,
        deptry_issues: t.SequenceOf[t.JsonMapping],
    ) -> m.Infra.ProjectDependencyReport:
        """Build a project dependency report from classified deptry issues."""
        classified = self.classify_issues(deptry_issues)

        def _module_names(
            items: t.SequenceOf[t.MappingKV[str, t.JsonValue | None]],
        ) -> t.MutableSequenceOf[str]:
            """Extract module names from classified issue items."""
            return [
                str(val)
                for item in items
                if (val := item.get(c.Infra.MODULE)) is not None
            ]

        return m.Infra.ProjectDependencyReport(
            project=project_name,
            deptry=m.Infra.DeptryReport(
                missing=_module_names(classified.dep001),
                unused=_module_names(classified.dep002),
                transitive=_module_names(classified.dep003),
                dev_in_runtime=_module_names(classified.dep004),
                raw_count=len(deptry_issues),
            ),
        )

    def discover_project_paths(
        self,
        repository_root: Path,
        projects_filter: t.StrSequence | None = None,
    ) -> p.Result[t.SequenceOf[Path]]:
        """Discover project paths with pyproject.toml in workspace.

        Returns only the Path objects, filtered to those with pyproject.toml.
        For full ProjectInfo metadata, use u.Infra.discover_projects().
        """
        names = projects_filter or []
        result = u.Infra.resolve_projects(repository_root, names)
        if result.failure:
            return r[t.SequenceOf[Path]].from_failure(result)
        projects_info: t.SequenceOf[m.Infra.ProjectInfo] = result.value
        projects = [
            project.path
            for project in projects_info
            if (project.path / c.PYPROJECT_FILENAME).exists()
        ]
        return r[t.SequenceOf[Path]].ok(sorted(projects))


__all__: list[str] = ["FlextInfraDependencyDetectionService"]
