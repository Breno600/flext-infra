"""Workspace check report rendering: markdown + SARIF + summary — extracted concern.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import operator
from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import c, m, p, r, t, u
from flext_infra.__version__ import FlextInfraVersion


class FlextInfraWorkspaceCheckReportsMixin:
    """Render markdown/SARIF reports and print the run summary.

    Composed into FlextInfraWorkspaceChecker via inheritance; pure rendering
    over gate results (no checker state).
    """

    @staticmethod
    def _generate_markdown(
        results: t.SequenceOf[m.Infra.ProjectResult],
        gates: t.StrSequence,
        timestamp: str,
    ) -> str:
        """Render markdown check report from project gate results.

        Returns:
            The resulting ``str``.

        """
        lines: list[str] = [
            "# Workspace Check Report",
            "",
            f"Generated: {timestamp}",
            f"Projects: {len(results)}",
            "",
            "## Summary",
            "",
            "| Project | Status | Findings |",
            "|---|---:|---:|",
        ]
        for project in results:
            status = "PASS" if project.passed else "FAIL"
            lines.append(f"| {project.project} | {status} | {project.total_findings} |")
        lines.extend(["", "## Details", ""])
        for project in results:
            lines.append(f"### {project.project}")
            for gate in gates:
                execution = project.gates.get(gate)
                if execution is None:
                    continue
                gate_status = "PASS" if execution.result.passed else "FAIL"
                lines.append(
                    f"- {gate}: {gate_status} ({len(execution.issues)} issues)",
                )
                lines.extend(f"  - {issue.formatted}" for issue in execution.issues)
                if execution.raw_receipt is not None:
                    lines.extend([
                        (
                            f"  - Native output receipt: "
                            f"[{execution.raw_receipt.name}]"
                            f"({execution.raw_receipt.resolve().as_uri()})"
                        ),
                    ])
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def _generate_sarif(
        cls,
        results: t.SequenceOf[m.Infra.ProjectResult],
        gates: t.StrSequence,
    ) -> m.Infra.SarifReport:
        """Build the SARIF 2.1.0 report model from workspace gate results.

        Returns:
            The resulting ``m.Infra.SarifReport``.

        """
        rules_by_id: MutableMapping[str, m.Infra.SarifRule] = {}
        sarif_results: list[m.Infra.SarifResult] = []
        for project in results:
            for gate in gates:
                execution = project.gates.get(gate)
                if execution is None:
                    continue
                tool_name, tool_url = c.Infra.SARIF_TOOL_INFO[gate]
                for issue in execution.issues:
                    rule_id = issue.code or gate
                    rules_by_id.setdefault(
                        rule_id,
                        m.Infra.SarifRule.model_validate({
                            "id": rule_id,
                            "short_description": f"{tool_name} ({gate}) issue",
                            "help_uri": tool_url,
                        }),
                    )
                    sarif_results.append(cls._sarif_issue(issue, rule_id))
        return m.Infra.SarifReport(
            runs=(
                m.Infra.SarifRun(
                    tool_name="flext-infra-check",
                    information_uri=FlextInfraVersion.__url__,
                    rules=tuple(rules_by_id.values()),
                    results=tuple(sarif_results),
                ),
            ),
        )

    @staticmethod
    def _sarif_issue(issue: m.Infra.Issue, rule_id: str) -> m.Infra.SarifResult:
        """Render one blocking occurrence while retaining its native severity.

        Returns:
            The resulting ``m.Infra.SarifResult``.

        """
        level = (
            "warning"
            if issue.severity.lower() == c.Infra.SeverityLevel.WARNING
            else "error"
        )
        return m.Infra.SarifResult.model_validate({
            "rule_id": rule_id,
            "level": level,
            "message": issue.message,
            "locations": list(issue.locations)
            if issue.locations
            else [
                m.Infra.SarifLocation(
                    uri=issue.file,
                    start_line=issue.line,
                    start_column=issue.column,
                ),
            ],
            "related_locations": issue.related_locations,
        })

    @classmethod
    def _write_reports_and_summary(
        cls,
        resolved_gates: t.StrSequence,
        report_base: Path,
        outcome: p.Infra.WorkspaceLoopOutcome,
    ) -> p.Result[t.SequenceOf[m.Infra.ProjectResult]]:
        """Write markdown/SARIF reports and print summary to output.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.ProjectResult]]``.

        """
        results = outcome.results
        timestamp = u.now().strftime("%Y-%m-%d %H:%M:%S %Z")
        md_path = report_base / c.Infra.CHECK_REPORT_MARKDOWN_FILENAME
        md_write_result = u.Cli.atomic_write_text_file(
            md_path,
            FlextInfraWorkspaceCheckReportsMixin._generate_markdown(
                results,
                resolved_gates,
                timestamp,
            ),
        )
        if md_write_result.failure:
            return r[t.SequenceOf[m.Infra.ProjectResult]].from_failure(md_write_result)
        sarif_path = report_base / c.Infra.CHECK_REPORT_SARIF_FILENAME
        sarif_report = cls._generate_sarif(results, resolved_gates)
        try:
            u.Infra.export_pydantic_json(sarif_report, sarif_path)
        except OSError as exc:
            return r[t.SequenceOf[m.Infra.ProjectResult]].fail(
                f"failed to write sarif report: {exc}",
                exception=exc,
            )
        total_findings = sum(project.total_findings for project in results)
        success = len(results) - outcome.failed
        u.Cli.summary(
            m.Infra.SummaryStats(
                verb=c.Infra.VERB_CHECK,
                total=len(results),
                success=success,
                failed=outcome.failed,
                skipped=0,
                elapsed=outcome.total_elapsed,
            ),
        )
        u.Cli.info(f"Reports: {md_path}")
        u.Cli.info(f"         {sarif_path}")
        if total_findings > 0:
            u.Cli.info("Findings by project (see reports for detail):")
            for project in sorted(
                results,
                key=operator.attrgetter("total_findings"),
                reverse=True,
            ):
                if project.total_findings == 0:
                    continue
                breakdown = ", ".join(
                    f"{gate}={project.gates[gate].finding_count}"
                    for gate in resolved_gates
                    if gate in project.gates and project.gates[gate].finding_count
                )
                u.Cli.info(
                    f"{project.project:30s} {project.total_findings:6d}  ({breakdown})",
                )
        return r[t.SequenceOf[m.Infra.ProjectResult]].ok(results)


__all__: list[str] = ["FlextInfraWorkspaceCheckReportsMixin"]
