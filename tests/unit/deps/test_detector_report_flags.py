"""Public report flags against real project discovery and installed tools.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from flext_tests import tm

from tests import c, u

# Real dependency discovery provisions a consumer from external package sources.
pytestmark = [pytest.mark.slow, pytest.mark.remote]


class TestsFlextInfraDepsDetectorReportFlags:
    """Tests for ``FlextInfraDepsDetectorReportFlags``."""

    @pytest.mark.parametrize("no_fail", [False, True])
    def test_real_dependency_and_environment_issues_respect_no_fail(
        self,
        real_detector_project: Path,
        *,
        no_fail: bool,
    ) -> None:
        """Test real dependency and environment issues respect no fail."""
        root = real_detector_project
        (root / "src/detector_fixture/undeclared.py").write_text(
            "import undeclared_detector_dependency\n",
            encoding="utf-8",
        )
        tm.ok(
            u.Cli.run_checked(
                [
                    os.environ.get("UV", c.Infra.UV),
                    "pip",
                    "uninstall",
                    "--python",
                    str(root / ".venv/bin/python"),
                    "requests",
                ],
                cwd=root,
            ),
        )
        arguments = ("--no-fail",) if no_fail else ()
        outcome = tm.ok(u.Tests.run_real_detector(root, *arguments))
        tm.that(
            u.Cli.process_succeeded(outcome.outcome),
            eq=no_fail,
            msg=outcome.stderr,
        )
        report = u.Cli.json_as_mapping(
            tm.ok(
                u.Cli.json_read(
                    root / ".reports/dependencies/detect-runtime-dev-latest.json",
                ),
            ),
        )
        tm.that(u.Cli.json_as_mapping(report.get("pip_check")).get("ok"), eq=False)
        project = u.Cli.json_as_mapping(
            u.Cli.json_as_mapping(report.get("projects")).get(root.name),
        )
        tm.that(
            u.Cli.json_pick_int(
                u.Cli.json_as_mapping(project.get("deptry")),
                "raw_count",
            ),
            gt=0,
        )

    @staticmethod
    def test_run_with_json_stdout_flag(real_detector_project: Path) -> None:
        """Test run with json stdout flag."""
        outcome = tm.ok(
            u.Tests.run_real_detector(
                real_detector_project,
                "--format",
                "json",
                "--no-pip-check",
            ),
        )
        tm.that(u.Cli.process_succeeded(outcome.outcome), eq=True, msg=outcome.stderr)
