"""FLEXT pyrefly quality gate."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, u

from .base_gate import FlextInfraGate

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraPyreflyGate(FlextInfraGate):
    """Pyrefly quality gate."""

    gate_id: ClassVar[str] = c.Infra.PYREFLY
    gate_name: ClassVar[str] = "Pyrefly"
    can_fix: ClassVar[bool] = False
    checker_info_prefixes: ClassVar[t.StrSequence] = ("INFO",)

    @override
    def _get_check_dirs(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.StrSequence:
        """Check only local Python roots to avoid scanning dependency trees."""
        _ = ctx
        return u.Infra.discover_python_targets(project_dir)

    @override
    def _build_check_command(
        self, project_dir: Path, ctx: m.Infra.GateContext, check_dirs: t.StrSequence
    ) -> t.StrSequence:
        """Build check command."""
        json_file = self._check_report_path(project_dir, ctx)
        target_args = u.Infra.pyrefly_target_args(project_dir, tuple(check_dirs))
        return self._python_module_command(
            c.Infra.PYREFLY,
            c.Infra.CHECK,
            *target_args,
            "--config",
            c.PYPROJECT_FILENAME,
            "--python-interpreter-path",
            sys.executable,
            "--output-format",
            c.Infra.OUTPUT_JSON,
            "--min-severity",
            "warn",
            "-o",
            str(json_file),
            "--summary=none",
        )

    @override
    def _check_report_path(self, project_dir: Path, ctx: m.Infra.GateContext) -> Path:
        """Use the existing native report owner, freshly replaced for every run."""
        return ctx.reports_dir / f"{project_dir.name}-pyrefly.json"

    @override
    def _check_remove_env_keys(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.StrSequence:
        """Use configured search paths without Pyrefly's inherited-path warning."""
        return (
            *super()._check_remove_env_keys(project_dir, ctx),
            c.Infra.ORCHESTRATOR_ENV_PYTHONPATH,
        )

    @override
    def _parse_check_output(
        self, result: p.Cli.CommandOutput, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse check output."""
        json_file = self._check_report_path(project_dir, ctx)
        if not u.Cli.process_succeeded(result.outcome) and not json_file.exists():
            return False, (
                self._command_error_issue(
                    result, tool=c.Infra.PYREFLY, file=str(json_file), line=0, column=0
                ),
            )
        validated: p.Result[m.Infra.PyreflyReport] = u.validate_value(
            m.Infra.PyreflyReport,
            json_file.read_text(encoding="utf-8"),
            from_json=True,
            strict=True,
        )
        if validated.failure:
            return False, (
                self._malformed_report_issue(
                    str(validated.error), tool=c.Infra.PYREFLY, file=str(json_file)
                ),
            )
        report = validated.value
        issues: t.MutableSequenceOf[m.Infra.Issue] = [
            m.Infra.Issue(
                file=diag.path,
                line=diag.line,
                column=diag.column,
                code=diag.name,
                message=diag.description,
                severity=diag.severity,
            )
            for diag in report.errors
        ]
        issues.extend(self._checker_stderr_issues(result, project_dir))
        if (not issues) and not u.Cli.process_succeeded(result.outcome):
            message = (result.stderr or result.stdout).strip()
            if not message:
                message = (
                    f"pyrefly exited with code {result.outcome.raw_return_code} "
                    "without JSON diagnostics"
                )
            issues.append(
                m.Infra.Issue(
                    file=c.PYPROJECT_FILENAME,
                    line=1,
                    column=1,
                    code="pyrefly-exec",
                    message=message,
                    severity=c.Infra.ERROR,
                )
            )
        return (
            u.Cli.process_succeeded(result.outcome)
            and not any(
                issue.severity.lower() in {"error", "warning", "warn"}
                for issue in issues
            ),
            issues,
        )


__all__: list[str] = ["FlextInfraPyreflyGate"]
