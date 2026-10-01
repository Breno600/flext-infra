"""Census collection-gate + module-selection helpers — extracted concern.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import config, m

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraRefactorCensusCollectHelpersMixin:
    """Select the modules to inventory and drive the census collection.

    Composed into FlextInfraRefactorCensus via inheritance; owns the
    collection-gate helpers and the top-level ``_collect_report`` orchestrator
    (scan selected modules → assemble).
    """

    if TYPE_CHECKING:
        include_local_scopes: bool

        @property
        def project_names(self) -> t.StrSequence | None:
            """Selected projects of the composed census service."""
            ...

        @property
        def kind_names(self) -> t.StrSequence | None:
            """Normalized symbol-kind filters of the census service."""
            ...

        @property
        def rule_names(self) -> t.StrSequence | None:
            """Normalized analysis filters of the census service."""
            ...

        @property
        def family_names(self) -> t.StrSequence | None:
            """Normalized family filters of the census service."""
            ...

        @staticmethod
        def _selected_families(family_names: t.StrSequence | None) -> frozenset[str]:
            """Resolve selected families through the composed object mixin."""
            ...

        def _scan_module(
            self,
            rope: p.Infra.RopeWorkspaceDsl,
            module: m.Infra.RopeModuleIndexEntry,
            scan_config: m.Infra.ScanConfig,
            *,
            findings: m.Infra.ScanFindings,
        ) -> None:
            """Scan through the composed census collection mixin."""
            ...

        def _assemble_report(
            self,
            rope: p.Infra.RopeWorkspaceDsl,
            *,
            findings: m.Infra.ScanFindings,
            scan_config: m.Infra.ScanConfig,
        ) -> m.Infra.WorkspaceReport:
            """Assemble through the composed census collection mixin."""
            ...

    @staticmethod
    def _should_collect_object_references(rule_names: t.StrSequence | None) -> bool:
        """Decide whether to collect object references."""
        if rule_names is None:
            return True
        return "unused" in rule_names

    @staticmethod
    def _project_name_for_module(
        module: m.Infra.RopeModuleIndexEntry,
        convention: m.Infra.RopeModuleConvention,
    ) -> str:
        """Project name for a module entry."""
        layout = convention.project_layout
        if layout is not None:
            return layout.project_name
        if module.project_root is not None:
            return module.project_root.name
        return ""

    @staticmethod
    def _is_production_module(module: m.Infra.RopeModuleIndexEntry) -> bool:
        """Return whether a module belongs to one configured production root."""
        project_root = module.project_root
        if project_root is None:
            return False
        resolved_file = module.file_path.resolve()
        resolved_root = project_root.resolve()
        if not resolved_file.is_relative_to(resolved_root):
            return False
        parts = resolved_file.relative_to(resolved_root).parts
        return bool(parts) and (parts[0] in config.Infra.source_scan.roots)

    def _collect_report(
        self,
        rope: p.Infra.RopeWorkspaceDsl,
    ) -> m.Infra.WorkspaceReport:
        """Inventory the selected modules then assemble the census report."""
        kind_names = self.kind_names
        rule_names = self.rule_names
        scan_config = m.Infra.ScanConfig(
            kind_names=kind_names,
            rule_names=rule_names,
            selected_families=self._selected_families(self.family_names),
            selected_kinds=frozenset(kind_names) if kind_names else None,
            selected_rules=frozenset(rule_names) if rule_names else None,
            include_object_references=self._should_collect_object_references(
                rule_names,
            ),
            include_local_scopes=self.include_local_scopes,
        )
        findings = m.Infra.ScanFindings(project_objects={}, report_projects=set())
        for module in rope.modules(project_names=self.project_names):
            if self._is_production_module(module):
                self._scan_module(rope, module, scan_config, findings=findings)
        return self._assemble_report(rope, findings=findings, scan_config=scan_config)


__all__: list[str] = ["FlextInfraRefactorCensusCollectHelpersMixin"]
