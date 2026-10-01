"""Shared runtime helpers for the public pytest runner test modules."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from flext_tests import tm

from flext_infra import FlextInfraPytestRunner, c, config, m, p, t, u


def runner_for(
    cached_runner_project: Path,
    *,
    ci_context: bool = False,
    profile_collection: bool = False,
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
        collection_command_prefix=(
            (
                sys.executable,
                "-X",
                "utf8",
                "-m",
                "flext_infra._pytest_entry",
                "profile-collection",
            )
            if profile_collection
            else ()
        ),
        started_at_monotonic=time.monotonic(),
        target=cache.target_directory,
        reports=cache.reports_directory,
        testmon_db=testmon_db,
    )


def profile_parent(runner: FlextInfraPytestRunner, output: Path) -> int:
    """Exercise the real -m entry in a fresh process with the Make-owned inputs."""
    output.parent.mkdir(parents=True, exist_ok=True)
    policy = config.Infra.tooling.tools.pytest
    cache = config.Infra.codegen.make.testmon_cache
    log = output.with_suffix(".log")
    outcome = tm.ok(
        u.Cli.run_to_file(
            (sys.executable, "-m", "flext_infra._pytest_entry", "profile", str(output)),
            log,
            cwd=runner.root,
            env=u.Cli.process_env(
                overrides={
                    c.Infra.PYTEST_ENV_TARGET: str(runner.target),
                    c.Infra.PYTEST_ENV_REPORTS: str(runner.reports),
                    cache.database_environment_variable: str(runner.testmon_db),
                }
            ),
            deadline=m.Cli.ProcessDeadline(
                expires_at_monotonic=(
                    runner.started_at_monotonic + policy.run_timeout_seconds
                ),
                termination_grace_seconds=policy.termination_grace_seconds,
            ),
        )
    )
    if not u.Cli.process_succeeded(outcome):
        raise RuntimeError(log.read_text(encoding="utf-8"))
    return outcome.raw_return_code


def profile_collection(
    output: Path, receipt: Path, arguments: t.StrTuple
) -> p.Cli.CommandOutput:
    """Use the real child transport invoked by the canonical profiling runner."""
    return tm.ok(
        u.Cli.run_raw(
            (
                sys.executable,
                "-m",
                "flext_infra._pytest_entry",
                "profile-collection",
                str(output),
                str(receipt),
                *arguments,
            ),
            cwd=receipt.parent,
            timeout=config.Infra.tooling.tools.pytest.run_timeout_seconds,
        )
    )


def summary(reports_root: Path) -> str:
    """Read the latest report summary through the files facade."""
    latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
    return tm.ok(u.Cli.files_read_text(reports_root / latest_name / "summary.txt"))
