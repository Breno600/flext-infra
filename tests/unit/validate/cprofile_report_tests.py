"""Focused cProfile report service contracts.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, u
from flext_infra.services import FlextInfraValidationCommandRoutes
from flext_infra.validate import FlextInfraCProfileReport


class TestsFlextInfraCProfileReport:
    """Prove real pstats artifacts render through the typed owner."""

    @staticmethod
    def test_real_profile_renders_bounded_text(tmp_path: Path) -> None:
        """Test real profile renders bounded text."""
        policy = config.Infra.tooling.tools.pytest
        report_dir = tmp_path / ".reports" / "tests" / "profile"
        report_dir.mkdir(parents=True)
        profile_path = report_dir / "profile.pstats"
        output_path = report_dir / "profile.txt"
        profile_target = tmp_path / "profile_target.py"
        profile_target.write_text("_ = sum(range(10))\n", encoding="utf-8")
        profiled = u.Cli.run_checked(
            [
                sys.executable,
                "-m",
                "cProfile",
                "-o",
                str(profile_path),
                str(profile_target),
            ],
            cwd=tmp_path,
        )
        tm.ok(profiled)

        result = FlextInfraCProfileReport(
            repository_root=tmp_path,
            profile=profile_path,
            output=output_path,
            sort=policy.profile_sort,
            limit=policy.profile_limit,
        ).execute()

        tm.ok(result)
        tm.that(output_path.read_text(encoding="utf-8"), has="function calls")

    @staticmethod
    def test_validate_route_uses_typed_profile_owner() -> None:
        """Test validate route uses typed profile owner."""
        routes = {
            route.name: route.model_cls
            for route in FlextInfraValidationCommandRoutes.validate_command_routes
        }

        tm.that(routes["cprofile-report"], eq=FlextInfraCProfileReport)

    @staticmethod
    def test_profile_artifacts_cannot_escape_workspace_reports(
        tmp_path: Path,
    ) -> None:
        """Test profile artifacts cannot escape workspace reports."""
        policy = config.Infra.tooling.tools.pytest

        with pytest.raises(ValueError, match="cProfile path must stay under"):
            FlextInfraCProfileReport(
                repository_root=tmp_path,
                profile=tmp_path / "outside.pstats",
                output=tmp_path / "outside.txt",
                sort=policy.profile_sort,
                limit=policy.profile_limit,
            )
