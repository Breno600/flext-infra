"""Verify ci.yml reuses the declared tool caches and saves them on failure.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import c, config, t
from tests import u
from tests.unit.codegen.test_ci_integration_branch_triggers import (
    TestsFlextInfraCiIntegrationBranchTriggers,
)


class TestsFlextInfraCiToolCacheReuse:
    """A cold tool cache must not be recomputed on every run."""

    @staticmethod
    def test_ci_reuses_and_saves_the_declared_tool_caches() -> None:
        """Test ci reuses and saves the declared tool caches."""
        steps = u.CodegenTestSupport.Ci.ci_job_steps(
            TestsFlextInfraCiIntegrationBranchTriggers.render_ci(
                repository_branch="0.12.0-dev",
            ),
        )
        named = {}
        for step in steps:
            name = step.get("name")
            if isinstance(name, str):
                named[name] = step
        cache = config.Infra.codegen.github_actions["cache"]
        restore = named["Restore tool caches"]
        save = named["Save tool caches"]
        tm.that(restore.get("uses"), eq=f"{cache.repository}/restore@{cache.version}")
        tm.that(save.get("uses"), eq=f"{cache.repository}/save@{cache.version}")
        # A failing gate must still warm the next run.
        tm.that("always()" in str(save.get("if")), eq=True)
        restore_with = t.Cli.JSON_MAPPING_ADAPTER.validate_python(restore["with"])
        save_with = t.Cli.JSON_MAPPING_ADAPTER.validate_python(save["with"])
        restore_paths = str(restore_with["path"]).split()
        for directory in config.Infra.codegen.make.clean.cache_dirs:
            tm.that(directory in restore_paths, eq=True)
        tm.that(save_with["key"], eq=restore_with["key"])

    @staticmethod
    def test_ci_carries_no_type_checker_cache() -> None:
        """No type checker runs in CI, so CI restores and saves no Mypy cache."""
        make = config.Infra.codegen.make
        tm.that(set(make.check_gates_ci) & c.Infra.TYPE_CHECKER_GATES, eq=set())
        steps = u.CodegenTestSupport.Ci.ci_job_steps(
            TestsFlextInfraCiIntegrationBranchTriggers.render_ci(
                repository_branch="0.12.0-dev",
            ),
        )
        mypy_storage = str(make.mypy_cache.external_storage_directory)
        for step in steps:
            options = step.get("with")
            if options is None:
                continue
            path = t.Cli.JSON_MAPPING_ADAPTER.validate_python(options).get("path")
            tm.that(mypy_storage in str(path), eq=False)
