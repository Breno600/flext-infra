"""Verify ci.yml reuses the declared tool caches and saves them on failure.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import config, t
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
        # One path list for both steps; Mise shims never travel through the
        # cache (a restored shim names an earlier run's Mise binary, which Mise
        # refuses as unmanaged and warns once per tool).
        tm.that(str(save_with["path"]).split(), eq=restore_paths)
        tm.that("!~/.local/share/mise/shims" in restore_paths, eq=True)
