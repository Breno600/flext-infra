"""Tests for check model types — _m.Infra.Issue and _ProjectResult.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import pytest
from flext_tests import tm

from tests import m, t, u


class TestsFlextInfraModels:
    """Tests for ``FlextInfraModels``."""

    @staticmethod
    @pytest.mark.parametrize("end", [None, (12, 0)])
    def test_sarif_locations_round_trip_optional_spans(
        end: t.Pair[int, int] | None,
    ) -> None:
        """SARIF protocol coordinates and related-location order survive JSON."""
        primary = m.Infra.SarifLocation(
            uri="src/first.py",
            start_line=3,
            start_column=0,
            end_line=end[0] if end else None,
            end_column=end[1] if end else None,
        )
        related = m.Infra.SarifLocation(
            uri="other-project/src/second.py",
            start_line=7,
            start_column=2,
        )
        result = m.Infra.SarifResult.model_validate({
            "rule_id": "similar-code",
            "level": "error",
            "message": "Native comparison",
            "locations": [primary],
            "related_locations": (related, primary),
        })
        published = result.model_dump_json()
        restored = m.Infra.SarifResult.model_validate_json(published)
        tm.that(restored, eq=result)
        tm.that("endLine" in primary.model_dump_json(), eq=end is not None)
        tm.that("endColumn" in primary.model_dump_json(), eq=end is not None)
        tm.that(published, has="relatedLocations")

    @staticmethod
    @pytest.mark.parametrize(
        "region",
        [None, {}, {"startLine": 7}, {"startLine": 0, "startColumn": 0}],
    )
    def test_native_partial_sarif_spans_preserve_missing_coordinates(
        region: t.JsonMapping | None,
    ) -> None:
        """Partial primary and related SARIF spans retain absence and zero."""
        physical: t.JsonDict = {"artifactLocation": {"uri": "src/partial.py"}}
        if region is not None:
            physical["region"] = dict(region)
        native: t.JsonDict = {
            "ruleId": "similar-code",
            "level": "error",
            "message": {"text": "Partial native comparison"},
            "locations": [{"physicalLocation": physical}],
            "relatedLocations": [{"physicalLocation": physical}],
        }
        payload = tm.ok(u.Cli.json_dumps(native))
        result = m.Infra.SarifResult.model_validate_json(payload)
        emitted = u.Cli.json_as_mapping(
            tm.ok(u.Cli.json_parse(result.model_dump_json())),
        )
        for key in ("locations", "relatedLocations"):
            location = u.Cli.json_deep_mapping_list(emitted, key)[0]
            published_region = u.Cli.json_deep_mapping(
                u.Cli.json_deep_mapping(location, "physicalLocation"),
                "region",
            )
            tm.that(published_region, eq=region or {})

    @staticmethod
    def _sample_issues() -> t.Triple[m.Infra.Issue, m.Infra.Issue, m.Infra.Issue]:
        """Build three distinct sample gate issues for summary assertions.

        Returns:
            The resulting ``t.Triple[m.Infra.Issue, m.Infra.Issue, m.Infra.Issue]``.

        """
        issue1 = m.Infra.Issue(
            file="a.py",
            line=1,
            column=1,
            code="E1",
            message="m1",
            severity="error",
        )
        issue2 = m.Infra.Issue(
            file="b.py",
            line=2,
            column=1,
            code="E2",
            message="m2",
            severity="error",
        )
        issue3 = m.Infra.Issue(
            file="c.py",
            line=3,
            column=1,
            code="E3",
            message="m3",
            severity="error",
        )
        return issue1, issue2, issue3

    # Why: flattened nested TestCheckIssueFormatted/TestRunCommandGateParsing/
    # TestProjectResultProperties/TestWorkspaceCheckerErrorSummary sibling classes into
    # this outer class — a nested class does not inherit the outer one, so calling
    # _sample_issues via a throwaway instance was external private-member access
    # (ruff SLF001).
    @staticmethod
    def test_formatted_with_code() -> None:
        """Test _m.Infra.Issue.formatted property with a code."""
        issue = m.Infra.Issue(
            file="test.py",
            line=10,
            column=5,
            code="E001",
            message="Error",
            severity="error",
        )
        tm.that(issue.formatted, contains="[E001]")
        tm.that(issue.formatted, contains="test.py:10:5")

    @staticmethod
    def test_formatted_without_code() -> None:
        """Test _m.Infra.Issue.formatted property without a code."""
        issue = m.Infra.Issue(
            file="test.py",
            line=10,
            column=5,
            code="",
            message="Error",
            severity="error",
        )
        tm.that(issue.formatted, contains="test.py:10:5")

    @staticmethod
    def test_run_command_splits_csv_gate_in_sequence_payload() -> None:
        """Test run-command gate parsing for check workflows."""
        command = m.Infra.RunCommand.model_validate({
            "projects": ["flext-core"],
            "gates": ["lint,format,pyrefly,mypy,pyright,security,markdown"],
        })

        tm.that(
            command.gates,
            eq=("lint", "format", "pyrefly", "mypy", "pyright", "security", "markdown"),
        )

    def test_total_findings_multiple_gates(self) -> None:
        """Every gate's findings add to the project total."""
        gate1 = m.Infra.GateResult(
            gate="lint",
            project="p",
            passed=True,
            errors=[],
            duration=0.0,
        )
        gate2 = m.Infra.GateResult(
            gate="format",
            project="p",
            passed=True,
            errors=[],
            duration=0.0,
        )
        issue1, issue2, issue3 = self._sample_issues()
        exec1 = m.Infra.GateExecution(
            result=gate1,
            issues=(issue1, issue2),
            raw_output="",
        )
        exec2 = m.Infra.GateExecution(result=gate2, issues=(issue3,), raw_output="")
        project = m.Infra.ProjectResult(
            project="p",
            gates={"lint": exec1, "format": exec2},
        )
        tm.that(project.total_findings, eq=3)

    @staticmethod
    def test_warning_findings_count_like_every_finding() -> None:
        """A warning that fails the gate is counted like any other finding.

        Every finding blocks, so the gate result carrying a warning is failed
        and lists it in its errors exactly as a real gate execution does.
        """
        warning = m.Infra.Issue(
            file="a.py",
            line=1,
            column=1,
            code="reportPrivateUsage",
            message="warning",
            severity="warning",
        )
        gate = m.Infra.GateResult(
            gate="pyright",
            project="p",
            passed=False,
            errors=[warning.formatted],
            duration=0.0,
        )
        execution = m.Infra.GateExecution(result=gate, issues=(warning,), raw_output="")
        project = m.Infra.ProjectResult(project="p", gates={"pyright": execution})

        tm.that(execution.finding_count, eq=1)
        tm.that(project.total_findings, eq=1)
        tm.that(project.passed, eq=False)

    @staticmethod
    def test_informational_gate_findings_keep_reported_but_pass_project() -> None:
        """Informational findings stay in the report but never fail the project.

        The config-owned posture names gate ids; the project verdict ignores
        exactly those gates while their findings still count as findings.
        """
        gate = m.Infra.GateResult(
            gate="pyright",
            project="p",
            passed=False,
            errors=["a.py:1:1 reportPrivateUsage warning"],
            duration=0.0,
        )
        execution = m.Infra.GateExecution(
            result=gate,
            issues=(
                m.Infra.Issue(
                    file="a.py",
                    line=1,
                    column=1,
                    code="reportPrivateUsage",
                    message="warning",
                    severity="warning",
                ),
            ),
            raw_output="",
        )
        project = m.Infra.ProjectResult(
            project="p",
            gates={"pyright": execution},
            informational_gates=("pyright",),
        )

        tm.that(project.total_findings, eq=1)
        tm.that(project.passed, eq=True)

    @staticmethod
    def test_informational_posture_covers_only_declared_gates() -> None:
        """A blocking gate outside the informational set still fails the project.

        One informational failure and one blocking failure together keep the
        project red: the posture excuses only the gate ids it declares.
        """
        informational = m.Infra.GateExecution(
            result=m.Infra.GateResult(
                gate="pyright",
                project="p",
                passed=False,
                errors=["a.py:1:1 reportPrivateUsage warning"],
                duration=0.0,
            ),
            issues=(),
            raw_output="",
        )
        blocking = m.Infra.GateExecution(
            result=m.Infra.GateResult(
                gate="lint",
                project="p",
                passed=False,
                errors=["b.py:2:1 E501 line too long"],
                duration=0.0,
            ),
            issues=(),
            raw_output="",
        )
        project = m.Infra.ProjectResult(
            project="p",
            gates={"pyright": informational, "lint": blocking},
            informational_gates=("pyright",),
        )

        tm.that(project.passed, eq=False)

    @staticmethod
    def test_passed_all_gates_pass() -> None:
        """Test _ProjectResult.passed when all gates pass."""
        gate1 = m.Infra.GateResult(
            gate="lint",
            project="p",
            passed=True,
            errors=[],
            duration=0.0,
        )
        gate2 = m.Infra.GateResult(
            gate="format",
            project="p",
            passed=True,
            errors=[],
            duration=0.0,
        )
        exec1 = m.Infra.GateExecution(result=gate1, issues=(), raw_output="")
        exec2 = m.Infra.GateExecution(result=gate2, issues=(), raw_output="")
        project = m.Infra.ProjectResult(
            project="p",
            gates={"lint": exec1, "format": exec2},
        )
        tm.that(project.passed, eq=True)

    @staticmethod
    def test_passed_one_gate_fails() -> None:
        """Test _ProjectResult.passed when one gate fails."""
        gate1 = m.Infra.GateResult(
            gate="lint",
            project="p",
            passed=True,
            errors=[],
            duration=0.0,
        )
        gate2 = m.Infra.GateResult(
            gate="format",
            project="p",
            passed=False,
            errors=[],
            duration=0.0,
        )
        exec1 = m.Infra.GateExecution(result=gate1, issues=(), raw_output="")
        exec2 = m.Infra.GateExecution(result=gate2, issues=(), raw_output="")
        project = m.Infra.ProjectResult(
            project="p",
            gates={"lint": exec1, "format": exec2},
        )
        tm.that(not project.passed, eq=True)

    def test_error_summary_with_multiple_projects_and_gates(self) -> None:
        """Test error summary reporting across multiple projects and gates."""
        issue1, issue2, issue3 = self._sample_issues()
        gate1 = m.Infra.GateResult(
            gate="lint",
            project="p",
            passed=True,
            errors=[],
            duration=0.0,
        )
        gate2 = m.Infra.GateResult(
            gate="lint",
            project="p",
            passed=True,
            errors=[],
            duration=0.0,
        )
        exec1 = m.Infra.GateExecution(
            result=gate1,
            issues=(issue1, issue2),
            raw_output="",
        )
        exec2 = m.Infra.GateExecution(result=gate2, issues=(issue3,), raw_output="")
        proj1 = m.Infra.ProjectResult(project="proj1", gates={"lint": exec1})
        proj2 = m.Infra.ProjectResult(project="proj2", gates={"format": exec2})
        tm.that(proj1.total_findings, eq=2)
        tm.that(proj2.total_findings, eq=1)
