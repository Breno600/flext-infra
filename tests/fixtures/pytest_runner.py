"""Shared construction and receipt reading for public pytest runner contracts."""

from __future__ import annotations

import time
from pathlib import Path

from flext_tests import tm

from flext_infra import FlextInfraPytestRunner, config, u


class PytestRunnerContract:
    """Provide real runner setup without replacing runtime owners."""

    @staticmethod
    def runner_for(
        cached_runner_project: Path,
        *,
        ci_context: bool = False,
        profile_enabled: bool = False,
    ) -> FlextInfraPytestRunner:
        """Bind one runner to the fixture project's canonical cache paths."""
        cache = config.Infra.codegen.make.testmon_cache
        testmon_db = (
            cached_runner_project.parent
            / ".testmon-cache"
            / cached_runner_project.name
            / cache.database_filename
        )
        testmon_db.parent.mkdir(parents=True, exist_ok=True)
        return FlextInfraPytestRunner(
            repository_root=cached_runner_project,
            ci_context=ci_context,
            profile_enabled=profile_enabled,
            started_at_monotonic=time.monotonic(),
            target=cache.target_directory,
            reports=cache.reports_directory,
            testmon_db=testmon_db,
        )

    @staticmethod
    def summary(reports_root: Path) -> str:
        """Read the latest report summary through the files facade."""
        latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        return tm.ok(u.Cli.files_read_text(reports_root / latest_name / "summary.txt"))
