"""Catalog-driven enforcement fix orchestrator.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Annotated, ClassVar, override

from flext_core import r
from flext_infra import m, p, t, u
from flext_infra.base_selection import FlextInfraProjectSelectionServiceBase

from .._enforcement.engine import FlextInfraEnforcementEngine
from .gate_fixer import FlextInfraGateFixerAdapter
from .manual_fixer import FlextInfraManualFixerAdapter
from .rope_fixer import FlextInfraRopeFixerAdapter
from .transformer_fixer import FlextInfraTransformerFixerAdapter

if TYPE_CHECKING:
    from pathlib import Path

    from .base import FlextInfraFixerAdapter


class FlextInfraEnforcementFixerOrchestrator(
    FlextInfraProjectSelectionServiceBase[str]
):
    """Apply automatic fixes for enforcement-catalog rules across workspace projects.

    The orchestrator reads the canonical enforcement catalog from flext-core,
    keeps only rules that declare a ``fix_action``, collects violations for
    those rules using the same validators/detectors that the pytest dispatcher
    uses, and routes each violation to the appropriate adapter.
    """

    _ADAPTER_CLASSES: ClassVar[t.VariadicTuple[type[FlextInfraFixerAdapter]]] = (
        FlextInfraGateFixerAdapter,
        FlextInfraManualFixerAdapter,
        FlextInfraRopeFixerAdapter,
        FlextInfraTransformerFixerAdapter,
    )

    apply: Annotated[
        bool, m.Field(description="Apply fixes instead of dry-run preview")
    ] = False
    rules: Annotated[
        t.VariadicTuple[str], m.Field(description="Enforcement rule IDs to fix")
    ] = ()
    safe_only: Annotated[
        bool, m.Field(description="Only apply fixes marked safe in the catalog")
    ] = True
    check_after: Annotated[
        bool, m.Field(description="Re-run the corresponding check after fixing")
    ] = True

    @classmethod
    def execute_payload(cls, params: m.Infra.FixEnforcementCommand) -> p.Result[str]:
        """Execute enforcement fixes from the canonical CLI payload."""
        instance = cls(
            repository_root=params.repository_root,
            selected_projects=params.projects,
            apply=params.apply,
            rules=tuple(params.rules),
            safe_only=params.safe_only,
            check_after=params.check_after,
            fail_fast=params.fail_fast,
        )
        return instance.execute()

    @override
    def execute(self) -> p.Result[str]:
        """Run the enforcement fix pipeline and return a human-readable report."""
        try:
            selected_rules = self._selected_rules()
        except ValueError as exc:
            return r[str].fail(str(exc), exception=exc)
        if not selected_rules:
            return r[str].ok("No fixable enforcement rules selected.")
        projects = self._resolve_projects()
        if projects.failure:
            return r[str].from_failure(projects)
        all_results: list[m.Infra.ProjectFixResult] = []
        for project in projects.value:
            project_result = self._fix_project(project, selected_rules)
            all_results.extend(project_result)
        report = self._render_report(all_results)
        if any(result.failed for result in all_results):
            return r[str].fail(report)
        return r[str].ok(report)

    def _selected_rules(
        self, catalog: m.EnforcementCatalog | None = None
    ) -> t.VariadicTuple[m.EnforcementRuleSpec]:
        """Return enabled rules with fix actions matching the CLI filter.

        Preflight: every enabled rule that declares a fix action must resolve
        to exactly one registered adapter. A catalog contract the runtime
        cannot honour is a defect of the catalog or the adapter registry, so it
        fails here, before any project is touched, naming rule and action —
        never a per-project failed fix discovered mid-run.
        """
        resolved: m.EnforcementCatalog = (
            catalog
            if catalog is not None
            else FlextInfraEnforcementEngine.canonical_catalog()
        )
        adapterless = tuple(
            f"{rule.id} {rule.fix_action.kind}:{rule.fix_action.target}"
            for rule in resolved.enabled_rules()
            if rule.fix_action is not None and not self._has_adapter(rule)
        )
        if adapterless:
            msg = (
                "enforcement catalog declares fix actions with no registered "
                f"fixer adapter: {', '.join(adapterless)}"
            )
            raise ValueError(msg)
        return FlextInfraEnforcementEngine.selected_rules(
            catalog=catalog, wanted=self.rules, safe_only=self.safe_only
        )

    def _has_adapter(self, rule: m.EnforcementRuleSpec) -> bool:
        """Return whether ``rule`` has a registered fixer adapter."""
        fix_action = rule.fix_action
        if fix_action is None:
            return False
        return self._adapter_for(fix_action) is not None

    def _resolve_projects(self) -> p.Result[t.SequenceOf[p.Infra.ProjectInfo]]:
        """Resolve the project list from CLI selection or workspace discovery."""
        projects_result = u.Infra.projects(self.repository_root)
        if projects_result.failure:
            return r[t.SequenceOf[p.Infra.ProjectInfo]].from_failure(projects_result)
        discovered = tuple(projects_result.unwrap())
        selected_projects: t.StrSequence = (
            self.project_names if self.project_names is not None else ()
        )
        scope: frozenset[str] = frozenset(selected_projects)
        available_names = {
            name
            for project in discovered
            for name in (project.name, project.path.name)
            if name
        }
        missing = scope - available_names
        if missing:
            return r[t.SequenceOf[p.Infra.ProjectInfo]].fail(
                f"Requested projects were not discovered: {', '.join(sorted(missing))}"
            )
        selected = (
            tuple(p for p in discovered if p.name in scope or p.path.name in scope)
            if scope
            else discovered
        )
        return r[t.SequenceOf[p.Infra.ProjectInfo]].ok(selected)

    def _fix_project(
        self, project: p.Infra.ProjectInfo, rules: t.SequenceOf[m.EnforcementRuleSpec]
    ) -> t.SequenceOf[m.Infra.ProjectFixResult]:
        """Collect violations and apply fixes for one project.

        Every rule reaching this point resolved to an adapter at preflight. An
        adapter that raises is a defect of that adapter: the exception escapes
        with its traceback instead of becoming a per-project finding.
        """
        project_dir = project.path
        results: list[m.Infra.ProjectFixResult] = []
        for adapter_cls, adapter_rules in self._group_by_adapter(rules).items():
            adapter = self._instantiate_adapter(adapter_cls)
            violations, failures = self._collect_violations(
                project_dir=project_dir, rules=adapter_rules
            )
            if failures:
                results.append(
                    m.Infra.ProjectFixResult(
                        project=project_dir.name, failed=tuple(failures)
                    )
                )
                if self.fail_fast:
                    return tuple(results)
            if not violations:
                continue
            result = adapter.fix_project(project_dir, violations, self._command_ctx())
            results.append(result)
            if result.failed and self.fail_fast:
                return tuple(results)
        return tuple(results)

    def _group_by_adapter(
        self, rules: t.SequenceOf[m.EnforcementRuleSpec]
    ) -> MutableMapping[type[FlextInfraFixerAdapter], list[m.EnforcementRuleSpec]]:
        """Group preflighted rules by the adapter that owns their fix_action."""
        grouped: MutableMapping[
            type[FlextInfraFixerAdapter], list[m.EnforcementRuleSpec]
        ] = defaultdict(list)
        for rule in rules:
            fix_action = rule.fix_action
            if fix_action is None:
                continue
            adapter_cls = self._adapter_for(fix_action)
            if adapter_cls is None:
                msg = f"fix action without adapter escaped preflight: {rule.id}"
                raise ValueError(msg)
            grouped[adapter_cls].append(rule)
        return grouped

    def _adapter_for(
        self, fix_action: m.EnforcementFixAction
    ) -> type[FlextInfraFixerAdapter] | None:
        """Return the first adapter class that accepts ``fix_action``."""
        for adapter_cls in self._ADAPTER_CLASSES:
            if self._instantiate_adapter(adapter_cls).can_fix(fix_action):
                return adapter_cls
        return None

    def _instantiate_adapter(
        self, adapter_cls: type[FlextInfraFixerAdapter]
    ) -> FlextInfraFixerAdapter:
        """Create an adapter instance, injecting repository root."""
        return adapter_cls(self.repository_root)

    def _engine(self) -> FlextInfraEnforcementEngine:
        """Build the shared enforcement engine for this workspace."""
        return FlextInfraEnforcementEngine(self.repository_root)

    def _collect_violations(
        self, project_dir: Path, rules: t.SequenceOf[m.EnforcementRuleSpec]
    ) -> t.Pair[
        list[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]], list[m.Infra.FailedFix]
    ]:
        """Collect violations for ``rules`` inside ``project_dir``."""
        evaluation = self._engine().collect_project(project_dir, rules)
        return evaluation.violations, evaluation.failures

    def _command_ctx(self) -> m.Infra.FixEnforcementCommand:
        """Build a command context for adapters from the service fields.

        Dry-run (``apply=False``) must never trigger post-fix checks, because
        check-after gates may rewrite files in place and restore originals.
        Forcing ``check_after=False`` keeps the run 100% read-only regardless
        of the CLI default or any future check-after implementation.
        """
        return m.Infra.FixEnforcementCommand(
            repository_root=str(self.repository_root),
            projects=self.project_names,
            apply=self.apply,
            rules=self.rules,
            safe_only=self.safe_only,
            check_after=self.check_after and self.apply,
            fail_fast=self.fail_fast,
        )

    @staticmethod
    def _render_report(results: t.SequenceOf[m.Infra.ProjectFixResult]) -> str:
        """Render a concise text report from all project results."""
        total_fixed = sum(len(r.fixed) for r in results)
        total_previewed = sum(len(r.previewed) for r in results)
        total_skipped = sum(len(r.skipped) for r in results)
        total_failed = sum(len(r.failed) for r in results)
        project_count = len({r.project for r in results})
        lines = [
            "Enforcement fix report:",
            f"  projects: {project_count}",
            f"  fixed: {total_fixed}",
            f"  previewed: {total_previewed}",
            f"  skipped: {total_skipped}",
            f"  failed: {total_failed}",
        ]
        for result in results:
            if not (
                result.fixed or result.previewed or result.skipped or result.failed
            ):
                continue
            interesting_skipped = [
                skipped
                for skipped in result.skipped
                if skipped.reason != "no changes produced"
            ]
            lines.append(f"  {result.project}:")
            lines.extend(
                f"    + {fixed.rule_id}: {fixed.file_path}" for fixed in result.fixed
            )
            lines.extend(
                f"    ? {preview.rule_id}: {preview.file_path}"
                for preview in result.previewed
            )
            lines.extend(
                f"    ~ {skipped.rule_id}: {skipped.reason}"
                for skipped in interesting_skipped
            )
            lines.extend(
                f"    ! {failed.rule_id}: {failed.error}" for failed in result.failed
            )
        return "\n".join(lines)


__all__: list[str] = ["FlextInfraEnforcementFixerOrchestrator"]
