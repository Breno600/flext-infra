"""FLEXT bandit quality gate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, ClassVar, override

from flext_core import r
from flext_infra.constants import c
from flext_infra.gates.base_gate import FlextInfraGate
from flext_infra.models import m
from flext_infra.typings import t
from flext_infra.utilities import u

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
        gate severity vocabulary and stays in the raw report.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.Issue]``.

        """
        return tuple(
            m.Infra.Issue(
                file=u.Cli.json_pick_str(raw_item, "filename", "?"),
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
