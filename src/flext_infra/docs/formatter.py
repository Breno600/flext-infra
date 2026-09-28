"""Documentation formatter service."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_infra import c, m, u
from flext_infra.gates.markdown_format import FlextInfraMarkdownFormatGate

from .base import FlextInfraDocServiceBase

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraDocFormatter(FlextInfraDocServiceBase):
    """Format governed docs scopes through the canonical markdown-format gate.

    The service never builds its own prettier invocation: configuration,
    ignore handling, and command construction stay owned by the gate, so
    ``docs fmt`` and ``make fmt`` can never disagree about the formatting
    contract. The single-pass verb law holds: one operation per scope — the
    mutating pass with ``--apply``, the read-only ``prettier --check``
    preview without it.
    """

    def format(
        self,
        repository_root: Path,
        *,
        projects: t.StrSequence | None = None,
        output_dir: Path | str | None = None,
        apply: bool = False,
    ) -> p.Result[t.SequenceOf[m.Infra.DocsPhaseReport]]:
        """Run markdown formatting across project scopes."""
        return self.run_scoped_docs(
            repository_root,
            projects=projects,
            output_dir=output_dir,
            handler=lambda scope: self._format_scope(scope, apply=apply),
        )

    @override
    def execute(self) -> p.Result[bool]:
        """Execute the configured docs format flow."""
        return self._propagate_phase_outcome(
            "fmt",
            self.format(
                repository_root=self.repository_root,
                projects=self.selected_projects,
                output_dir=self.output_dir,
                apply=self.apply_changes,
            ),
            failure_predicate=lambda report: not report.passed,
        )

    def _format_scope(
        self, scope: m.Infra.DocScope, *, apply: bool
    ) -> m.Infra.DocsPhaseReport:
        """Format one scope through the canonical markdown-format gate."""
        gate = FlextInfraMarkdownFormatGate(scope.path)
        ctx = m.Infra.GateContext(
            repository_root=scope.repository_root,
            reports_dir=scope.report_dir,
            apply_fixes=apply,
        )
        execution = gate.fix(scope.path, ctx) if apply else gate.check(scope.path, ctx)
        if apply:
            files = tuple(
                match.group("file")
                for line in execution.raw_output.splitlines()
                if (match := c.Infra.DOCS_PRETTIER_WRITE_LINE_RE.match(line.strip()))
            )
        else:
            files = tuple(issue.file for issue in execution.issues)
        items = tuple(
            m.Infra.DocsPhaseItemModel(phase="fmt", file=file) for file in files
        )
        u.Infra.docs_write_fmt_reports(scope, items=items, apply=apply)
        report = m.Infra.DocsPhaseReport(
            phase="fmt",
            scope=scope.name,
            changed_files=len(items),
            applied=apply,
            items=items,
            result=(
                c.Infra.ResultStatus.OK
                if execution.result.passed
                else c.Infra.ResultStatus.FAIL
            ),
            reason=f"{'formatted' if apply else 'pending'}:{len(items)}",
            passed=execution.result.passed,
        )
        self.logger.info(
            "docs_format_scope_completed",
            project=scope.name,
            phase="fmt",
            result=report.result,
            reason=report.reason,
        )
        return report


__all__: list[str] = ["FlextInfraDocFormatter"]
