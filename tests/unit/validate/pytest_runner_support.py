"""Shared runtime helpers for the public pytest runner test modules.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

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
    slow_phase: bool = False,
    target_file: Path | None = None,
) -> FlextInfraPytestRunner:
    """Bind one runner to the fixture project's canonical cache paths.

    Returns:
        The resulting ``FlextInfraPytestRunner``.

    """
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
        target_file=target_file,
        reports=cache.reports_directory,
        testmon_db=testmon_db,
        slow_phase=slow_phase,
    )


def declare_parallel_project(project_root: Path) -> None:
    """Declare the fixture as a project whose worker ceiling admits xdist.

    The fleet default is one worker (a serial dispatch), so a case that needs
    real xdist workers declares a project that owns a multi-worker override in
    the config-owned map, never a hardcoded name or count.
    """
    policy = config.Infra.tooling.tools.pytest
    parallel_project = next(
        name
        for name, ceiling in policy.parallel_worker_overrides.items()
        if (isinstance(ceiling, int) and ceiling > 1)
        or (
            not isinstance(ceiling, int)
            and ceiling.workers is not None
            and ceiling.workers > 1
        )
    )
    pyproject = project_root / c.PYPROJECT_FILENAME
    pyproject.write_text(
        f'[project]\nname = "{parallel_project}"\nversion = "0.0.0"\n'
        + pyproject.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # The declaration only matters through the runner's derived budget: prove
    # the runtime admits xdist workers instead of assuming the override does.
    tm.that(runner_for(project_root).parallel_worker_budget(policy) > 1, eq=True)


def profile_parent(runner: FlextInfraPytestRunner, output: Path) -> int:
    """Exercise the real -m entry in a fresh process with the Make-owned inputs.

    Returns:
        The resulting ``int``.

    Raises:
        RuntimeError: If ``not u.Cli.process_succeeded(outcome)``.

    """
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
                },
            ),
            deadline=m.Cli.ProcessDeadline(
                expires_at_monotonic=(
                    runner.started_at_monotonic + policy.run_timeout_seconds
                ),
                termination_grace_seconds=policy.termination_grace_seconds,
            ),
        ),
    )
    if not u.Cli.process_succeeded(outcome):
        raise RuntimeError(log.read_text(encoding="utf-8"))
    return outcome.raw_return_code


def profile_collection(
    output: Path,
    receipt: Path,
    arguments: t.StrTuple,
) -> p.Cli.CommandOutput:
    """Use the real child transport invoked by the canonical profiling runner.

    Returns:
        The resulting ``p.Cli.CommandOutput``.

    """
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
        ),
    )


def summary(reports_root: Path) -> str:
    """Read the latest report summary through the files facade.

    Returns:
        The resulting ``str``.

    """
    latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
    return tm.ok(u.Cli.files_read_text(reports_root / latest_name / "summary.txt"))
