"""Report construction helpers for FlextInfraDocAuditor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, config, m

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraDocAuditorReportMixin:
    """Mixin for documentation audit report construction."""

    @staticmethod
    def _audit_warning_posture() -> bool:
        """Whether audit findings warn instead of failing the phase.

        Operator law 2026-09-22: docs audit findings are warnings owned by
        cleanup beads, never CI blockers, when ``make.docs.warning_actions``
        lists ``audit``; the reports keep every finding either way.
        """
        return "audit" in config.Infra.codegen.make.docs.warning_actions

    def _audit_report(
        self,
        scope: m.Infra.DocScope,
        *,
        issues: t.SequenceOf[m.Infra.AuditIssue],
        checks: t.StrSequence,
        params: m.Infra.AuditScopeParams,
        docstring_coverage: m.Infra.DocstringCoverage | None = None,
    ) -> m.Infra.DocsPhaseReport:
        """Build the standard docs audit phase report."""
        issue_count = len(issues)
        coverage_breached = (
            params.docstring_min is not None
            and docstring_coverage is not None
            and docstring_coverage.percent < params.docstring_min
        )
        warning_posture = self._audit_warning_posture()
        passed = (issue_count == 0 and not coverage_breached) or warning_posture
        result = c.Infra.ResultStatus.OK if passed else c.Infra.ResultStatus.FAIL
        message = (
            f"docstring coverage {docstring_coverage.percent}% below minimum "
            f"{params.docstring_min}%"
            if coverage_breached and docstring_coverage is not None
            else "audit passed"
            if issue_count == 0
            else f"audit passed with {issue_count} warning(s)"
            if warning_posture
            else f"found {issue_count} issue(s)"
        )
        return m.Infra.DocsPhaseReport(
            phase="audit",
            scope=scope.name,
            result=result,
            reason=(
                f"issues:{issue_count};{message}"
                if coverage_breached
                else f"issues:{issue_count}"
            ),
            message=message,
            checks=checks,
            strict=not warning_posture,
            passed=passed,
            items=[
                m.Infra.DocsPhaseItemModel(
                    phase="audit",
                    file=issue.file,
                    issue_type=issue.issue_type,
                    severity=issue.severity,
                    message=issue.message,
                )
                for issue in issues
            ],
        )


__all__: list[str] = ["FlextInfraDocAuditorReportMixin"]
