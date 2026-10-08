"""FLEXT bandit quality gate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, config, m, r, t, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraBanditGate(FlextInfraGate):
    """Bandit security quality gate."""

    gate_id: ClassVar[str] = c.Infra.SECURITY
    gate_name: ClassVar[str] = "Bandit"
    can_fix: ClassVar[bool] = False
    check_module_command_prefix: ClassVar[t.StrSequence] = (c.Infra.BANDIT, "-r")
    check_module_command_suffix: ClassVar[t.StrSequence] = (
        "-f",
        c.Infra.OUTPUT_JSON,
        "--quiet",
    )

    @override
    def selected_for(self, project_dir: Path) -> bool:
        """Only a project with a ``src`` package surface selects bandit.

        Returns:
            The resulting ``bool``.

        """
        return (project_dir / c.Infra.DEFAULT_SRC_DIR).is_dir()

    @override
    def _get_check_dirs(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.StrSequence:
        """Audit only the ``src`` package surface, never tests or scripts.

        Returns:
            ``src`` when the project has it, otherwise nothing to audit.

        """
        _ = ctx
        if not (project_dir / c.Infra.DEFAULT_SRC_DIR).exists():
            return []
        return [c.Infra.DEFAULT_SRC_DIR]

    @override
    def _build_check_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        check_dirs: t.StrSequence,
    ) -> t.StrSequence:
        """Audit the package surface minus generated trees and owner modules.

        Bandit reads no Git ignore rules, so the generated-source globs of the
        codegen artifact SSOT are passed as its exclusion list. The modules of
        every authorized exception are excluded as well: their own invocation
        audits them with every test except the authorized ones.

        Returns:
            The Bandit invocation over ``check_dirs``.

        """
        command = super()._build_check_command(project_dir, ctx, check_dirs)
        owned = tuple(
            path
            for _, files in self._owner_scopes(project_dir, check_dirs)
            for path in files
        )
        return self._with_exclusions(command, owned)

    @override
    def _execute_check_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        targets: t.StrSequence,
        started: float,
    ) -> m.Infra.GateExecution:
        """Audit unscoped modules and each owner scope in its own invocation.

        Bandit applies ``--skip`` to a whole run and reads no per-path
        exception, so each authorized exception gets one more native run over
        exactly its owner modules that skips only its tests. The gate passes
        only when every run passes; findings of every run are reported.

        Returns:
            The gate execution combining every Bandit run.

        """
        executions = (
            super()._execute_check_command(project_dir, ctx, targets, started),
            *(
                self._parsed_gate_execution(
                    project_dir,
                    ctx,
                    self._run(
                        self._with_exclusions(
                            self._python_module_command(
                                *self.check_module_command_prefix,
                                *files,
                                *self.check_module_command_suffix,
                                "--skip",
                                ",".join(tests),
                            ),
                            (),
                        ),
                        project_dir,
                        timeout=self._check_timeout(project_dir, ctx),
                        env=self._check_env(project_dir, ctx),
                        remove_env_keys=self._check_remove_env_keys(project_dir, ctx),
                    ),
                    started,
                )
                for tests, files in self._owner_scopes(project_dir, targets)
            ),
        )
        if len(executions) == 1:
            return executions[0]
        issues = tuple(issue for execution in executions for issue in execution.issues)
        # ToolOutcome declares CLEAN < FINDINGS < ERROR; the worst run decides.
        ranking = tuple(c.Infra.ToolOutcome)
        return m.Infra.GateExecution(
            result=self._gate_result(
                project_dir,
                passed=all(execution.result.passed for execution in executions),
                errors=[issue.formatted for issue in issues],
                started=started,
            ),
            issues=issues,
            raw_output="\n".join(execution.raw_output for execution in executions),
            outcome=max(
                (execution.outcome for execution in executions),
                key=ranking.index,
            ),
        )

    @staticmethod
    def _owner_scopes(
        project_dir: Path,
        targets: t.StrSequence,
    ) -> t.SequenceOf[t.Pair[t.StrSequence, t.StrSequence]]:
        """Resolve each authorized exception to its owner modules under targets.

        Returns:
            One ``(tests, files)`` pair per exception that owns a file under
            ``targets``; files are project-relative POSIX paths.

        """
        roots = tuple(PurePosixPath(target) for target in targets)
        scopes = (
            (
                entry.tests,
                tuple(
                    sorted({
                        str(relative)
                        for pattern in entry.files
                        for relative in (
                            PurePosixPath(path.relative_to(project_dir).as_posix())
                            for path in project_dir.glob(pattern)
                            if path.is_file()
                        )
                        if any(relative.is_relative_to(root) for root in roots)
                    }),
                ),
            )
            for entry in config.Infra.tooling.tools.bandit.authorized_exceptions
        )
        return tuple((tests, files) for tests, files in scopes if files)

    @staticmethod
    def _with_exclusions(
        command: t.StrSequence,
        owned: t.StrSequence,
    ) -> t.StrSequence:
        """Append the generated-source globs and ``owned`` as Bandit exclusions.

        Returns:
            ``command`` with its ``--exclude`` list, or unchanged when empty.

        """
        excluded = (*config.Infra.codegen.generated_source_globs, *owned)
        if not excluded:
            return command
        return (*command, "--exclude", ",".join(excluded))

    @override
    def _parse_check_output(
        self,
        result: p.Cli.CommandOutput,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Read Bandit's JSON report; every reported result blocks the gate.

        Returns:
            The run's verdict and its findings, parse error or failed exit.

        """
        del ctx
        if not result.stdout.strip():
            if u.Cli.process_succeeded(result.outcome):
                return False, (
                    self._parse_error_issue("bandit produced no JSON output"),
                )
            return self._finalize_parse_result(result, project_dir, (), c.Infra.BANDIT)
        parsed_payload = self._parse_bandit_payload(result.stdout)
        if parsed_payload.failure:
            return False, (
                self._parse_error_issue(
                    parsed_payload.error or "Tool output parsing failed",
                ),
            )
        return self._finalize_parse_result(
            result,
            project_dir,
            self._bandit_issues(parsed_payload.unwrap()),
            c.Infra.BANDIT,
        )

    @staticmethod
    def _parse_bandit_payload(stdout: str) -> p.Result[t.MappingKV[str, t.JsonValue]]:
        """Parse Bandit JSON stdout into a typed payload mapping.

        Returns:
            The resulting ``p.Result[t.MappingKV[str, t.JsonValue]]``.

        """
        parsed_result = u.Cli.json_parse(stdout)
        if parsed_result.failure:
            return r[t.MappingKV[str, t.JsonValue]].from_failure(parsed_result)
        raw_payload = parsed_result.unwrap()
        if not isinstance(raw_payload, Mapping):
            return r[t.MappingKV[str, t.JsonValue]].fail(
                "Bandit output is not a JSON object",
            )
        return r[t.MappingKV[str, t.JsonValue]].ok(u.Cli.json_as_mapping(raw_payload))

    @staticmethod
    def _bandit_issues(
        bandit_data: t.MappingKV[str, t.JsonValue],
    ) -> t.SequenceOf[m.Infra.Issue]:
        """Build typed gate issues from parsed Bandit result entries.

        Bandit fails its run on every reported result, so each one is a
        blocking gate finding; Bandit's own LOW/MEDIUM/HIGH rating is not the
        gate severity vocabulary and stays in the raw report. Bandit names a
        file given on its command line ``./<path>`` and a discovered one
        ``<path>``; the issue carries the one project-relative spelling.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.Issue]``.

        """
        return tuple(
            m.Infra.Issue(
                file=str(
                    PurePosixPath(u.Cli.json_pick_str(raw_item, "filename", "?")),
                ),
                line=u.Cli.json_pick_int(raw_item, "line_number"),
                column=0,
                code=u.Cli.json_pick_str(raw_item, "test_id"),
                message=u.Cli.json_pick_str(raw_item, "issue_text"),
                severity=c.Infra.GateSeverity.ERROR.value,
            )
            for raw_item in u.Cli.json_as_mapping_list(
                bandit_data.get(c.Infra.BANDIT_RESULTS_KEY, []),
            )
        )

    @staticmethod
    def _parse_error_issue(message: str) -> m.Infra.Issue:
        """Build the canonical Bandit output parse issue.

        Returns:
            The resulting ``m.Infra.Issue``.

        """
        return m.Infra.Issue(
            file="<bandit-output>",
            line=0,
            column=0,
            code=c.Infra.ToolOutcome.ERROR.value,
            message=message,
            severity="ERROR",
        )


__all__: list[str] = ["FlextInfraBanditGate"]
