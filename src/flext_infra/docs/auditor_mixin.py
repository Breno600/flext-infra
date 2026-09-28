"""Auditor helper mixin for the documentation auditor service.

Provides static helper methods used by the documentation auditor service.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from flext_infra import c, t, u

if TYPE_CHECKING:
    from flext_infra import m


class FlextInfraDocAuditorMixin:
    """Mixin providing helper methods for the documentation auditor."""

    @staticmethod
    def resolve_checks(check: str) -> t.Infra.StrSet:
        """Parse check string into a resolved set of check names."""
        checks = {part.strip() for part in check.split(",") if part.strip()}
        if not checks or "all" in checks:
            return {
                "links",
                "forbidden-terms",
                "placeholders",
                "machine-paths",
                "stale-symbols",
                "scope-boundary",
                "generated-ownership",
                "command-contract",
                "docstrings",
                "python-codeblocks",
            }
        return checks

    @staticmethod
    def write_audit_reports(
        scope: m.Infra.DocScope,
        issues: t.SequenceOf[m.Infra.AuditIssue],
        checks: t.Infra.StrSet,
        *,
        docstring_coverage: m.Infra.DocstringCoverage | None = None,
        to_markdown_fn: Callable[
            [
                m.Infra.DocScope,
                t.SequenceOf[m.Infra.AuditIssue],
                m.Infra.DocstringCoverage | None,
            ],
            t.StrSequence,
        ],
    ) -> None:
        """Persist JSON summary and markdown report to the scope report directory."""
        validated_checks = t.json_list_adapter().validate_python(sorted(checks))
        sorted_checks: t.JsonValueList = list(validated_checks)
        summary: t.JsonDict = {
            c.Infra.RK_SCOPE: scope.name,
            "issues": len(issues),
            c.Infra.VERB_CHECKS: sorted_checks,
            "report_dir": scope.report_dir.as_posix(),
        }
        if docstring_coverage is not None:
            summary["docstring_coverage"] = docstring_coverage.model_dump()
        issues_payload: t.JsonValue = [
            {
                c.Infra.RK_FILE: issue.file,
                "issue_type": issue.issue_type,
                "severity": issue.severity,
                c.Infra.RK_MESSAGE: issue.message,
            }
            for issue in issues
        ]
        summary_payload: t.JsonDict = {
            c.Infra.RK_SUMMARY: summary,
            "issues": issues_payload,
        }
        _ = u.Cli.json_write(scope.report_dir / "audit-summary.json", summary_payload)
        _ = u.Infra.write_markdown(
            scope.report_dir / "audit-report.md",
            to_markdown_fn(scope, issues, docstring_coverage),
        )


__all__: list[str] = ["FlextInfraDocAuditorMixin"]
