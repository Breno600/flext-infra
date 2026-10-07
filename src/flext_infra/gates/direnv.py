"""FLEXT direnv environment contract gate.

Two fail-closed stages per checked workspace: the static environment-file
contracts (see ``flext_infra.workspace.environment_contracts``) followed by a
real ``direnv exec`` activation smoke. A workspace without ``.envrc`` skips.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraDirenvGate(FlextInfraGate):
    """Enforce direnv file contracts, then prove real activation."""

    gate_id: ClassVar[str] = "direnv"
    gate_name: ClassVar[str] = "DIRENV ENVIRONMENT CONTRACT"
    can_fix: ClassVar[bool] = False

    @staticmethod
    def _contract_boundary() -> type[p.Infra.WorkspaceEnvironmentContracts]:
        """Return the contract owner typed at its published ``p.Infra`` boundary.

        Returns:
            The contract owner typed at its published ``p.Infra`` boundary.

        """
        from flext_infra.workspace.environment_contracts import FlextInfraWorkspaceEnvironmentContracts
        return FlextInfraWorkspaceEnvironmentContracts

    @staticmethod
    def _contract_issue(
        file: str,
        violation: m.Infra.EnvironmentContractViolation,
    ) -> m.Infra.Issue:
        """Render one typed contract violation as a gate issue.

        Returns:
            The resulting ``m.Infra.Issue``.

        """
        return m.Infra.Issue(
            file=file,
            line=violation.line,
            column=0,
            code="DIRENV_CONTRACT",
            message=f"line {violation.line}: {violation.message}",
            severity="ERROR",
        )

    @override
    def check(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.GateExecution:
        """Run the static contracts, then the activation smoke.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        """
        started = time.monotonic()
        envrc = project_dir / c.Infra.ENVRC_FILENAME
        if not envrc.is_file():
            return self._skip_result(project_dir, started)
        content = u.Cli.files_read_text(envrc)
        if content.failure:
            issue = m.Infra.Issue(
                file=c.Infra.ENVRC_FILENAME,
                line=0,
                column=0,
                code="DIRENV_READ",
                message=content.error or f"cannot read {envrc}",
                severity="ERROR",
            )
            return self._build_check_gate_execution(
                project_dir,
                passed=False,
                issues=(issue,),
                raw_output=issue.message,
                started=started,
            )
        violations = self._contract_boundary().envrc_contract_violations(
            content.value,
            root=project_dir,
        )
        issues = tuple(
            FlextInfraDirenvGate._contract_issue(c.Infra.ENVRC_FILENAME, violation)
            for violation in violations
        )
        local = project_dir / c.Infra.ENVRC_LOCAL_RELPATH
        if local.is_file():
            local_read = u.Cli.files_read_text(local)
            if local_read.failure:
                issues = (
                    *issues,
                    m.Infra.Issue(
                        file=c.Infra.ENVRC_LOCAL_RELPATH,
                        line=0,
                        column=0,
                        code="DIRENV_READ",
                        message=local_read.error or f"cannot read {local}",
                        severity="ERROR",
                    ),
                )
            else:
                issues = (
                    *issues,
                    *(
                        FlextInfraDirenvGate._contract_issue(
                            c.Infra.ENVRC_LOCAL_RELPATH,
                            violation,
                        )
                        for violation in (
                            self._contract_boundary().envrc_local_contract_violations(
                                local_read.value,
                            )
                        )
                    ),
                )
        if issues:
            return self._build_check_gate_execution(
                project_dir,
                passed=False,
                issues=issues,
                raw_output="\n".join(issue.message for issue in issues),
                started=started,
            )
        return super().check(project_dir, ctx)

    @override
    def _get_check_dirs(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.StrSequence:
        """One marker dir drives the base flow; the smoke targets the root.

        Returns:
            The resulting ``t.StrSequence``.

        """
        _ = ctx
        return (
            (str(project_dir),)
            if (project_dir / c.Infra.ENVRC_FILENAME).exists()
            else ()
        )

    @override
    def _build_check_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        check_dirs: t.StrSequence,
    ) -> t.StrSequence:
        """Activate the workspace environment for one no-op command.

        Returns:
            The resulting ``t.StrSequence``.

        """
        _ = ctx, check_dirs
        return (c.Infra.CLI_DIRENV, "exec", str(project_dir), "true")

    @override
    def _parse_check_output(
        self,
        result: p.Cli.CommandOutput,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Pass only on a zero-exit activation.

        Returns:
            The resulting ``t.Pair[bool, t.SequenceOf[m.Infra.Issue]]``.

        """
        _ = project_dir, ctx
        if u.Cli.process_succeeded(result.outcome):
            return True, ()
        detail = result.stderr.strip() or result.stdout.strip() or "direnv exec failed"
        return (
            False,
            (
                m.Infra.Issue(
                    file=c.Infra.ENVRC_FILENAME,
                    line=0,
                    column=0,
                    code="DIRENV_ACTIVATE",
                    message=detail,
                    severity="ERROR",
                ),
            ),
        )


__all__: t.VariadicTuple[str] = ("FlextInfraDirenvGate",)
