"""Tests for constants-quality-gate CLI wiring.

Validates CLI dispatch, argument parsing, and verdict classification
using real service instances with temporary workspaces.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import main
from flext_infra.codegen.constants_quality_gate import FlextInfraCodegenQualityGate
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraCodegenConstantsQualityGate:
    """CLI dispatch, argument parsing, and verdict classification."""

    def test_dispatch_returns_int(self, tmp_path: Path) -> None:
        """main() dispatches constants-quality-gate command to handler."""
        result = main([
            "codegen",
            "constants-quality-gate",
            "--repository-root",
            str(tmp_path),
        ])
        tm.that(result, is_=int)

    def test_json_format_exits_with_int(self, tmp_path: Path) -> None:
        """JSON mode returns an integer exit code."""
        result = main([
            "codegen",
            "constants-quality-gate",
            "--repository-root",
            str(tmp_path),
            "--format",
            "json",
        ])
        tm.that(result, is_=int)

    def test_text_format_exits_with_int(self, tmp_path: Path) -> None:
        """Text mode returns an integer exit code."""
        result = main([
            "codegen",
            "constants-quality-gate",
            "--repository-root",
            str(tmp_path),
            "--format",
            "text",
        ])
        tm.that(result, is_=int)

    def test_success_verdict_accepts_pass(self) -> None:
        """successful_verdict returns True for PASS."""
        tm.that(FlextInfraCodegenQualityGate.successful_verdict("PASS"), eq=True)

    def test_success_verdict_rejects_conditional_pass(self) -> None:
        """successful_verdict returns False for removed conditional verdicts."""
        tm.that(
            not FlextInfraCodegenQualityGate.successful_verdict("CONDITIONAL_PASS"),
            eq=True,
        )

    def test_success_verdict_rejects_fail(self) -> None:
        """successful_verdict returns False for FAIL."""
        tm.that(not FlextInfraCodegenQualityGate.successful_verdict("FAIL"), eq=True)

    def test_real_workspace_run_returns_report(self, tmp_path: Path) -> None:
        """Quality gate runs on real empty workspace without errors."""
        gate = FlextInfraCodegenQualityGate(repository_root=tmp_path)
        report_result = gate.build_report()
        tm.ok(report_result)
        tm.that(report_result.value, has="verdict")

    def test_build_report_uses_canonical_census_duplicates(
        self, tmp_path: Path
    ) -> None:
        """Duplicate groups are sourced from the canonical refactor census."""
        constant_source = (
            '"""Shared constant fixture."""\n\n'
            "from typing import Final\n\n"
            "SHARED_TIMEOUT: Final[int] = 30\n"
        )
        for project_name in ("flext-cli", "flext-core"):
            u.Tests.create_codegen_project(
                tmp_path=tmp_path,
                name=project_name,
                pkg_name=project_name.replace("-", "_"),
                files={
                    "constants.py": constant_source,
                    "typings.py": '"""Empty typing fixture."""\n',
                },
            )
        u.Tests.declare_workspace_projects(tmp_path, ("flext-cli", "flext-core"))
        # Why: the workspace-wide rope index now discovers every governed
        # project (flext-1wjg1), so the gate's own lazy-init precheck sees the
        # fixture's real __init__.py files and requires them conformant first.
        tm.that(u.Tests.run_lazy_init(tmp_path), eq=0)
        gate = FlextInfraCodegenQualityGate(repository_root=tmp_path)
        report_result = gate.build_report()
        tm.ok(report_result)
        report = report_result.value
        after = u.Cli.json_deep_mapping(report, "after")
        duplicate_groups = u.Cli.json_deep_mapping_list(
            report, "duplicate_constant_groups"
        )

        tm.that(u.Cli.json_pick_int(after, "duplicate_groups"), gte=1)
        matching_groups = [
            group
            for group in duplicate_groups
            if u.Cli.json_pick_str(group, "name") == "SHARED_TIMEOUT"
        ]
        tm.that(matching_groups, length=1)
        tm.that(u.Cli.json_pick_str(matching_groups[0], "canonical"), eq="flext-cli")
