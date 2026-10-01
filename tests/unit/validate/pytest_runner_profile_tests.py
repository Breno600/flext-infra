"""Native child profiles retain real fixture/test work and failing outcomes."""

from __future__ import annotations

import pstats
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, m
from tests.fixtures.pytest_runner import PytestRunnerContract


class TestsFlextInfraPytestRunnerProfile(PytestRunnerContract):
    """Inspect real cProfile artifacts from canonical runner subprocesses."""

    @pytest.mark.slow
    @pytest.mark.parametrize("succeeds", [True, False])
    def test_child_profile_includes_fixture_and_test_without_normalizing_failure(
        self, cached_runner_project: Path, *, succeeds: bool
    ) -> None:
        target = config.Infra.codegen.make.testmon_cache.target_directory
        source = cached_runner_project / target / "test_runtime.py"
        source.write_text(
            "import pytest\n\n"
            "@pytest.fixture\n"
            "def measured_fixture():\n"
            "    return sum(range(17))\n\n"
            "def test_measured_runtime(measured_fixture):\n"
            "    assert measured_fixture == sum(range(17))\n"
            f"    assert {succeeds!r}\n",
            encoding="utf-8",
        )
        runner = self.runner_for(cached_runner_project, profile_enabled=True)
        status = tm.ok(runner.execute())
        reports = cached_runner_project / runner.reports
        latest = (reports / "latest.txt").read_text(encoding="utf-8").strip()
        report = reports / latest
        outcome = m.Cli.ProcessOutcome.model_validate_json(
            (report / "suite-outcome.json").read_text(encoding="utf-8")
        )
        assert status == outcome.raw_return_code
        assert (status == 0) == succeeds
        assert not outcome.timed_out
        profile = pstats.Stats(str(report / "pytest.pstats"))
        functions = {
            name
            for name, measured in profile.get_stats_profile().func_profiles.items()
            if Path(measured.file_name) == source
        }
        assert {"measured_fixture", "test_measured_runtime"} <= functions
        assert tuple((report / "profiles").glob("*.pstats"))
