"""FLEXT bandit quality gate."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, ClassVar, override

from flext_core import r
from flext_infra import c, m, t, u

from .base_gate import FlextInfraGate

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
    def _get_check_dirs(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.StrSequence:
        """Get check dirs."""
        _ = ctx
        if not (project_dir / c.Infra.DEFAULT_SRC_DIR).exists():
            return []
        return [c.Infra.DEFAULT_SRC_DIR]

    @override
    def _empty_targets_result(
        self, project_dir: Path, started: float
    ) -> m.Infra.GateExecution:
        """No ``src`` tree means no Python package surface to audit.

        A package:false workspace root declares no importable package, so
        bandit has no legitimate target there; absence is topology, not a
        lost scan.
        """
        return self._neutral_skip_result(
            project_dir,
            started,
            message=(
                f"{self.gate_id}: no src tree — package:false project declares "
                "no Python package surface to audit"
            ),
        )

    @override
    def _parse_check_output(
        self, result: p.Cli.CommandOutput, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse check output."""
        _ = project_dir, ctx
        issues: t.MutableSequenceOf[m.Infra.Issue] = []
        if not u.Cli.process_succeeded(result.outcome) and not result.stdout.strip():
            issues.append(
                self._command_error_issue(
                    result, tool=c.Infra.BANDIT, file="<bandit>", line=0, column=0
                )
            )
            return False, issues
        if not result.stdout.strip():
            issues.append(self._parse_error_issue("bandit produced no JSON output"))
            return False, issues
        try:
            parsed_payload = self._parse_bandit_payload(result.stdout)
        except c.EXC_VALIDATION_TYPE as err:
            issues.append(
                self._parse_error_issue(
                    f"Tool output parsing failed: {type(err).__name__}"
                )
            )
            return False, issues
        if parsed_payload.failure:
            issues.append(
                self._parse_error_issue(
                    parsed_payload.error or "Tool output parsing failed"
                )
            )
            return False, issues
        issues.extend(self._bandit_issues(parsed_payload.unwrap()))
        if not issues and not u.Cli.process_succeeded(result.outcome):
            issues.append(
                self._command_error_issue(
                    result, tool=c.Infra.BANDIT, file="<bandit>", line=0, column=0
                )
            )
        return u.Cli.process_succeeded(result.outcome), issues

    @staticmethod
    def _parse_bandit_payload(stdout: str) -> p.Result[t.MappingKV[str, t.JsonValue]]:
        """Parse Bandit JSON stdout into a typed payload mapping."""
        parsed_result = u.Cli.json_parse(stdout)
        if parsed_result.failure:
            return r[t.MappingKV[str, t.JsonValue]].from_failure(parsed_result)
        raw_payload = parsed_result.unwrap()
        if not isinstance(raw_payload, Mapping):
            return r[t.MappingKV[str, t.JsonValue]].fail(
                "Bandit output is not a JSON object"
            )
        return r[t.MappingKV[str, t.JsonValue]].ok(u.Cli.json_as_mapping(raw_payload))

    @staticmethod
    def _bandit_issues(
        bandit_data: t.MappingKV[str, t.JsonValue],
    ) -> t.SequenceOf[m.Infra.Issue]:
        """Build typed gate issues from parsed Bandit result entries."""
        return tuple(
            m.Infra.Issue(
                file=u.Cli.json_pick_str(raw_item, "filename", "?"),
                line=u.Cli.json_pick_int(raw_item, "line_number"),
                column=0,
                code=u.Cli.json_pick_str(raw_item, "test_id"),
                message=u.Cli.json_pick_str(raw_item, "issue_text"),
                severity=u.Cli.json_pick_str(
                    raw_item, "issue_severity", "MEDIUM"
                ).lower(),
            )
            for raw_item in u.Cli.json_as_mapping_list(
                bandit_data.get(c.Infra.BANDIT_RESULTS_KEY, [])
            )
        )

    @staticmethod
    def _parse_error_issue(message: str) -> m.Infra.Issue:
        """Build the canonical Bandit output parse issue."""
        return m.Infra.Issue(
            file="<bandit-output>",
            line=0,
            column=0,
            code="PARSE_ERROR",
            message=message,
            severity="ERROR",
        )


__all__: list[str] = ["FlextInfraBanditGate"]
