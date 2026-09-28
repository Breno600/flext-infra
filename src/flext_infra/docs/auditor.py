"""Documentation auditor service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, override

from flext_infra import m, u

from ._auditor_checks import FlextInfraDocAuditorChecksMixin
from ._auditor_report import FlextInfraDocAuditorReportMixin
from .auditor_mixin import FlextInfraDocAuditorMixin
from .base import FlextInfraDocServiceBase

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraDocAuditor(
    FlextInfraDocServiceBase,
    FlextInfraDocAuditorMixin,
    FlextInfraDocAuditorChecksMixin,
    FlextInfraDocAuditorReportMixin,
):
    """Audit governed docs scopes; every finding is reported.

    There is no issue budget and no findings are dropped: the report always
    carries the complete issue list. The phase verdict follows the configured
    posture — audit is blocking unless ``make.docs.warning_actions`` lists it
    (operator law 2026-09-22: findings then warn, owned by cleanup beads,
    while ``docstring_min`` stays an additional floor in blocking posture).
    """

    checks: Annotated[
        str, m.Field(description="Comma-separated audit checks (default: all)")
    ] = "all"

    docstring_min: Annotated[
        float | None,
        m.Field(
            description="Minimum docstring coverage percent; breach fails the audit"
        ),
    ] = None

    def audit(
        self,
        repository_root: Path,
        *,
        projects: t.StrSequence | None = None,
        output_dir: Path | str | None = None,
        params: m.Infra.AuditScopeParams | None = None,
    ) -> p.Result[t.SequenceOf[m.Infra.DocsPhaseReport]]:
        """Audit root and governed project docs scopes."""
        resolved_params = (
            params
            if params is not None
            else m.Infra.AuditScopeParams(
                check=self.checks, docstring_min=self.docstring_min
            )
        )
        return self.run_scoped_docs(
            repository_root,
            projects=projects,
            output_dir=output_dir,
            handler=lambda scope: self.audit_scope(scope, params=resolved_params),
        )

    def audit_scope(
        self, scope: m.Infra.DocScope, *, params: m.Infra.AuditScopeParams
    ) -> m.Infra.DocsPhaseReport:
        """Audit one scope and persist the standard reports."""
        checks = sorted(self.resolve_checks(params.check))
        issues = self._collect_issues(scope, checks)
        docstring_coverage = (
            u.Infra.docs_public_docstring_coverage(scope)
            if "docstrings" in checks or params.docstring_min is not None
            else None
        )
        report = self._audit_report(
            scope,
            issues=issues,
            checks=checks,
            params=params,
            docstring_coverage=docstring_coverage,
        )
        self.write_audit_reports(
            scope,
            issues,
            set(checks),
            docstring_coverage=docstring_coverage,
            to_markdown_fn=u.Infra.docs_audit_markdown,
        )
        self.logger.info(
            "docs_audit_scope_completed",
            project=scope.name,
            phase="audit",
            result=report.result,
            reason=report.reason,
        )
        return report

    @override
    def execute(self) -> p.Result[bool]:
        """Execute the configured docs audit flow."""
        return self._propagate_phase_outcome(
            "audit",
            self.audit(
                repository_root=self.repository_root,
                projects=self.selected_projects,
                output_dir=self.output_dir,
                params=m.Infra.AuditScopeParams(
                    check=self.checks, docstring_min=self.docstring_min
                ),
            ),
            failure_predicate=lambda report: not report.passed,
        )


if __name__ == "__main__":
    raise SystemExit(0)


__all__: list[str] = ["FlextInfraDocAuditor"]
