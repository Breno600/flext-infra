"""Contracts for the canonical focused cProfile report entrypoint."""

from __future__ import annotations

import cProfile
import sys
from pathlib import Path

import pytest

from flext_infra import config, u
from flext_tests import tm


class TestsCProfileEntry:
    # Why (suite budget): spawns a fresh interpreter to render the report;
    # cold interpreter start under xdist contention exceeds the case wall.
    @pytest.mark.slow
    def test_report_uses_typed_pytest_policy(self, tmp_path: Path) -> None:
        """Render a real profile with the same typed policy production consumes."""
        report_root = tmp_path / ".reports" / "cprofile"
        report_root.mkdir(parents=True)
        profiler = cProfile.Profile()
        profiler.enable()
        _ = sum(range(10))
        profiler.disable()
        profiler.dump_stats(report_root / "pytest.pstats")

        rendered = u.Cli.run_checked(
            [sys.executable, "-m", "flext_infra._cprofile_entry"], cwd=tmp_path
        )
        tm.ok(rendered)

        report = (report_root / "pytest.txt").read_text(encoding="utf-8")
        policy = config.Infra.tooling.tools.pytest
        tm.that(bool(report.strip()), eq=True)
        tm.that(len(report.splitlines()) <= policy.profile_limit + 10, eq=True)


__all__: list[str] = []
