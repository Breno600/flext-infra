"""Persist dependency reports through real public discovery and tools.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import u

# Real dependency discovery provisions a consumer from external package sources.
pytestmark = [pytest.mark.slow, pytest.mark.remote]


class TestsFlextInfraDepsDetectorReport:
    """Tests for ``FlextInfraDepsDetectorReport``."""

    @staticmethod
    @pytest.mark.parametrize("custom", [False, True])
    def test_report_path_and_real_project_identity(
        real_detector_project: Path,
        *,
        custom: bool,
    ) -> None:
        """Test report path and real project identity."""
        root = real_detector_project
        destination = root / (
            "custom-report.json"
            if custom
            else ".reports/dependencies/detect-runtime-dev-latest.json"
        )
        arguments = ("--output", str(destination)) if custom else ()
        outcome = tm.ok(u.Tests.run_real_detector(root, "--no-pip-check", *arguments))
        tm.that(
            u.Cli.process_succeeded(outcome.outcome),
            eq=True,
            msg=f"{outcome.stdout}\n{outcome.stderr}",
        )
        tm.that(destination.is_file(), eq=True)
        report = u.Cli.json_as_mapping(tm.ok(u.Cli.json_read(destination)))
        tm.that(u.Cli.json_as_mapping(report.get("projects")), keys=[root.name])

    @staticmethod
    def test_blocked_report_path_preserves_writer_failure(
        real_detector_project: Path,
    ) -> None:
        """Test blocked report path preserves writer failure."""
        root = real_detector_project
        blocked = root / "blocked"
        blocked.write_text("not-a-directory", encoding="utf-8")
        outcome = tm.ok(
            u.Tests.run_real_detector(
                root,
                "--no-pip-check",
                "--output",
                str(blocked / "report.json"),
            ),
        )
        tm.that(u.Cli.process_succeeded(outcome.outcome), eq=False)
        tm.that(outcome.stdout + outcome.stderr, has="json_write failed")
