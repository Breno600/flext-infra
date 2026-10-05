"""FLEXT pyrefly quality gate.

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


class FlextInfraPyreflyGate(FlextInfraGate):
    """Pyrefly quality gate."""

    gate_id: ClassVar[str] = c.Infra.PYREFLY
    gate_name: ClassVar[str] = "Pyrefly"
    can_fix: ClassVar[bool] = False
    checker_info_prefixes: ClassVar[t.StrSequence] = ("INFO",)
    requires_python_targets: ClassVar[bool] = True
    # Native JSON report replaced before every run: ``{project}-pyrefly.json``.
    check_report_filename: ClassVar[str] = "pyrefly.json"
    check_remove_env_keys: ClassVar[t.StrSequence] = (
        *FlextInfraGate.check_remove_env_keys,
        c.Infra.ORCHESTRATOR_ENV_PYTHONPATH,
    )

    def _native_report_path(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> Path:
        """Resolve the JSON report this gate replaces before every run.

        Returns:
            The resulting ``Path``.

        Raises:
            RuntimeError: If ``check_report_filename`` is empty.

        """
        report_path = self._check_report_path(project_dir, ctx)
        if report_path is None:
            msg = "FlextInfraPyreflyGate.check_report_filename is empty"
            raise RuntimeError(msg)
        return report_path

    @override
    def _get_check_dirs(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.StrSequence:
        """Check only local Python roots to avoid scanning dependency trees.

        Returns:
            The resulting ``t.StrSequence``.

        """
        _ = ctx
        return self._python_targets(project_dir)

    @override
    def _build_check_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        check_dirs: t.StrSequence,
    ) -> t.StrSequence:
        """Run Pyrefly against the project config, writing its JSON report file.

        Returns:
            The Pyrefly invocation bound to ``sys.executable``.

        """
        json_file = self._native_report_path(project_dir, ctx)
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
    def _parse_check_output(
        self,
        result: p.Cli.CommandOutput,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Read Pyrefly's freshly written JSON report file into findings.

        Returns:
            The run's verdict and its diagnostics or stderr failures.

        """
        json_file = self._native_report_path(project_dir, ctx)
        if not u.Cli.process_succeeded(result.outcome) and not json_file.exists():
            return False, (
                self._command_error_issue(
                    result,
                    tool=c.Infra.PYREFLY,
                    file=str(json_file),
                    line=0,
                    column=0,
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
                    str(validated.error),
                    tool=c.Infra.PYREFLY,
                    file=str(json_file),
                ),
            )
        issues = self._checker_issues(
            result,
            project_dir,
            tuple(
                m.Infra.Issue(
                    file=diag.path,
                    line=diag.line,
                    column=diag.column,
                    code=diag.name,
                    message=diag.description,
                    severity=diag.severity,
                )
                for diag in validated.value.errors
            ),
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
