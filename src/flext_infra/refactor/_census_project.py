"""Census per-project report assembly.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from flext_infra import m

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraRefactorCensusProjectMixin:
    """Build one project report (violations + removal candidates) for census.

    Composed into FlextInfraRefactorCensus via inheritance; borrows the
    rule-inclusion + object-classification helpers from sibling mixins via FLEXT.
    """

    if TYPE_CHECKING:

        @staticmethod
        def _include_rule(
            rule: str,
            *,
            rule_names: t.StrSequence | None,
            selected_rules: frozenset[str] | None = None,
        ) -> bool: ...
        @staticmethod
        def _is_unused(item: m.Infra.Object) -> bool: ...
        @staticmethod
        def _object_key(item: m.Infra.Object) -> str: ...
        @staticmethod
        def _violation(
            item: m.Infra.Object,
            *,
            kind: str,
            description: str,
        ) -> m.Infra.Violation: ...
        @classmethod
        def _removal_candidate(
            cls,
            item: m.Infra.Object,
            *,
            include_unused: bool,
        ) -> m.Infra.RemovalCandidate | None: ...

    def _project_report(
        self,
        project: str,
        *,
        findings: m.Infra.ScanFindings,
        duplicate_keys: frozenset[str],
        scan_config: m.Infra.ScanConfig,
    ) -> m.Infra.ProjectReport:
        """Project report.

        Returns:
            The resulting ``m.Infra.ProjectReport``.

        """
        objects = tuple(findings.project_objects.get(project, ()))
        violations: list[m.Infra.Violation] = []
        rule_names = scan_config.rule_names
        selected_rules = scan_config.selected_rules
        include_unused = self._include_rule(
            "unused",
            rule_names=rule_names,
            selected_rules=selected_rules,
        )
        include_duplicate = self._include_rule(
            "duplicate",
            rule_names=rule_names,
            selected_rules=selected_rules,
        )
        include_wrong_tier = self._include_rule(
            "wrong_tier",
            rule_names=rule_names,
            selected_rules=selected_rules,
        )
        unused_count = 0
        removal_candidates: list[m.Infra.RemovalCandidate] = []
        for item in objects:
            is_unused = self._is_unused(item)
            if include_duplicate and self._object_key(item) in duplicate_keys:
                violations.append(
                    self._violation(
                        item,
                        kind="duplicate",
                        description="Duplicate definition in workspace",
                    ),
                )
            if is_unused and include_unused:
                unused_count += 1
                violations.append(
                    self._violation(
                        item,
                        kind="unused",
                        description="Object has no non-definition references",
                    ),
                )
            if (
                include_wrong_tier
                and item.expected_tier
                and item.actual_tier
                and item.expected_tier != item.actual_tier
            ):
                violations.append(
                    self._violation(
                        item,
                        kind="wrong_tier",
                        description=(
                            f"Expected tier '{item.expected_tier}' "
                            f"but found '{item.actual_tier}'"
                        ),
                    ),
                )
            candidate = self._removal_candidate(item, include_unused=include_unused)
            if candidate is not None:
                removal_candidates.append(candidate)
        return m.Infra.ProjectReport(
            project=project,
            objects=objects,
            objects_total=len(objects),
            objects_by_kind=dict(Counter(item.kind for item in objects)),
            violations=tuple(violations),
            violations_total=len(violations),
            unused_count=unused_count,
            removal_candidate_count=len(removal_candidates),
            removal_candidates=tuple(removal_candidates),
        )


__all__: list[str] = ["FlextInfraRefactorCensusProjectMixin"]
