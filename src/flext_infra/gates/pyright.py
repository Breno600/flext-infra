"""FLEXT pyright quality gate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraPyrightGate(FlextInfraGate):
    """Pyright quality gate."""

    gate_id: ClassVar[str] = c.Infra.PYRIGHT
    gate_name: ClassVar[str] = "Pyright"
    can_fix: ClassVar[bool] = False
    requires_python_targets: ClassVar[bool] = True
    check_timeout: ClassVar[int] = c.Infra.TIMEOUT_LONG

    @override
    def _get_check_dirs(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.StrSequence:
        """Use the project pyright config as SSOT when it exists.

        Returns:
            The resulting ``t.StrSequence``.

        """
        _ = ctx
        if self._has_project_pyright_config(project_dir):
            return [c.Infra.PYRIGHT_PROJECT_ARG, c.Infra.PYRIGHT_PROJECT_CONFIG_TARGET]
        return super()._get_check_dirs(project_dir, ctx)

    @override
    def _build_check_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        check_dirs: t.StrSequence,
    ) -> t.StrSequence:
        """Run Pyright on the workspace interpreter with its JSON report.

        Returns:
            The Pyright invocation bound to ``sys.executable``.

        """
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
        """Return whether pyproject.toml declares [tool.pyright].

        Returns:
            Whether pyproject.toml declares [tool.pyright].

        """
        doc = u.Cli.toml_read(project_dir / c.PYPROJECT_FILENAME)
        if doc is None:
            return False
        tool_table = u.Cli.toml_table_child(doc, c.Infra.TOOL)
        return (
            tool_table is not None
            and u.Cli.toml_table_child(tool_table, c.Infra.PYRIGHT) is not None
        )

    @override
    def _parse_check_output(
        self,
        result: p.Cli.CommandOutput,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Grade Pyright's JSON report together with its own summary counts.

        Returns:
            The run's verdict and its diagnostics, stderr failures or lost scan.

        """
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
            m.Infra.PyrightReport,
            result.stdout,
            from_json=True,
            strict=True,
        )
        if validated.failure:
            return False, (
                self._malformed_report_issue(
                    str(validated.error),
                    tool=c.Infra.PYRIGHT,
                    file=str(project_dir),
                ),
            )
        report = validated.value
        diagnostics = tuple(
            m.Infra.Issue(
                file=diag.file,
                line=diag.range.start.line + 1 if diag.range is not None else 0,
                column=diag.range.start.character + 1 if diag.range is not None else 0,
                code=diag.rule or "",
                message=diag.message,
                severity=diag.severity,
            )
            for diag in report.general_diagnostics
        )
        if report.summary.files_analyzed == 0:
            # The gate is selected only for projects with Python targets, so an
            # empty analysis is a lost scan, never a pass; the report's own
            # diagnostics travel with it because they carry the cause.
            return False, (
                *diagnostics,
                self._malformed_report_issue(
                    "pyright analyzed no files for a project with Python targets",
                    tool=c.Infra.PYRIGHT,
                    file=str(project_dir),
                ),
            )
        issues = self._checker_issues(result, project_dir, diagnostics)
        return (
            u.Cli.process_succeeded(result.outcome)
            and not report.summary.error_count
            and not report.summary.warning_count
            and not any(issue.severity == "ERROR" for issue in issues),
            issues,
        )


__all__: list[str] = ["FlextInfraPyrightGate"]
