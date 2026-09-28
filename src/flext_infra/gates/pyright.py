"""FLEXT pyright quality gate."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, u

from .base_gate import FlextInfraGate

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraPyrightGate(FlextInfraGate):
    """Pyright quality gate."""

    gate_id: ClassVar[str] = c.Infra.PYRIGHT
    gate_name: ClassVar[str] = "Pyright"
    can_fix: ClassVar[bool] = False

    @override
    def _get_check_dirs(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.StrSequence:
        """Use the project pyright config as SSOT when it exists."""
        _ = ctx
        if self._has_project_pyright_config(project_dir):
            return [c.Infra.PYRIGHT_PROJECT_ARG, c.Infra.PYRIGHT_PROJECT_CONFIG_TARGET]
        return super()._get_check_dirs(project_dir, ctx)

    @override
    def _build_check_command(
        self, project_dir: Path, ctx: m.Infra.GateContext, check_dirs: t.StrSequence
    ) -> t.StrSequence:
        """Build check command."""
        _ = project_dir
        return self._python_module_command(
            c.Infra.PYRIGHT,
            "--pythonpath",
            sys.executable,
            *check_dirs,
            *ctx.pyright_args,
            "--outputjson",
        )

    @staticmethod
    def _has_project_pyright_config(project_dir: Path) -> bool:
        """Return whether pyproject.toml declares [tool.pyright]."""
        doc = u.Cli.toml_read(project_dir / c.PYPROJECT_FILENAME)
        if doc is None:
            return False
        tool_table = u.Cli.toml_table_child(doc, c.Infra.TOOL)
        return (
            tool_table is not None
            and u.Cli.toml_table_child(tool_table, c.Infra.PYRIGHT) is not None
        )

    @override
    def _check_timeout(self, project_dir: Path, ctx: m.Infra.GateContext) -> int:
        """Check timeout."""
        _ = project_dir, ctx
        timeout: int = c.Infra.TIMEOUT_LONG
        return timeout

    @override
    def _parse_check_output(
        self, result: p.Cli.CommandOutput, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse check output."""
        _ = ctx
        if not u.Cli.process_succeeded(result.outcome) and not result.stdout.strip():
            return False, (
                self._command_error_issue(
                    result,
                    tool=c.Infra.PYRIGHT,
                    file=str(project_dir),
                    line=0,
                    column=0,
                ),
            )
        validated: p.Result[m.Infra.PyrightReport] = u.validate_value(
            m.Infra.PyrightReport, result.stdout, from_json=True, strict=True
        )
        if validated.failure:
            return False, (
                self._malformed_report_issue(
                    str(validated.error), tool=c.Infra.PYRIGHT, file=str(project_dir)
                ),
            )
        report = validated.value
        issues: t.MutableSequenceOf[m.Infra.Issue] = [
            m.Infra.Issue(
                file=diag.file,
                line=diag.range.start.line + 1 if diag.range is not None else 0,
                column=diag.range.start.character + 1 if diag.range is not None else 0,
                code=diag.rule or "",
                message=diag.message,
                severity=diag.severity,
            )
            for diag in report.general_diagnostics
        ]
        issues.extend(self._checker_stderr_issues(result, project_dir))
        if (not issues) and not u.Cli.process_succeeded(result.outcome):
            message = (result.stderr or result.stdout).strip()
            if not message:
                message = (
                    f"pyright exited with code {result.outcome.raw_return_code} "
                    "without JSON diagnostics"
                )
            issues.append(
                m.Infra.Issue(
                    file=c.PYPROJECT_FILENAME,
                    line=1,
                    column=1,
                    code="pyright-exec",
                    message=message,
                    severity=c.Infra.ERROR,
                )
            )
        return (
            u.Cli.process_succeeded(result.outcome)
            and not report.summary.error_count
            and not report.summary.warning_count
            and not any(issue.severity == "ERROR" for issue in issues),
            issues,
        )


__all__: list[str] = ["FlextInfraPyrightGate"]
