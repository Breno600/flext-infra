"""Verify ci.yml reuses the declared tool caches and saves them on failure."""

from __future__ import annotations

from flext_tests import tm

from flext_infra import config, t

from ._support import CodegenTestSupport
from .test_ci_integration_branch_triggers import (
    TestsFlextInfraCiIntegrationBranchTriggers,
)


class TestsFlextInfraCiToolCacheReuse:
    """A cold Mypy/Pyrefly/Ruff cache must not be recomputed on every run."""

    def test_ci_reuses_and_saves_the_declared_tool_caches(self) -> None:
        steps = CodegenTestSupport.Ci.ci_job_steps(
            TestsFlextInfraCiIntegrationBranchTriggers.render_ci(
                repository_branch="0.12.0-dev"
            )
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

    def test_ci_restores_and_always_saves_the_mypy_cache(self) -> None:
        """Every run starts from the newest Mypy cache and hands its own on.

        The cache is saved on every outcome, a failing or killed Mypy included,
        under a key unique to the run; the restore takes the newest earlier one.
        """
        steps = CodegenTestSupport.Ci.ci_job_steps(
            TestsFlextInfraCiIntegrationBranchTriggers.render_ci(
                repository_branch="0.12.0-dev"
            )
        )
        names = [step.get("name") for step in steps]
        named = {
            name: step
            for name, step in zip(names, steps, strict=True)
            if isinstance(name, str)
        }
        cache = config.Infra.codegen.github_actions["cache"]
        spec = config.Infra.codegen.make.mypy_cache
        restore = named["Restore Mypy cache"]
        save = named["Save Mypy cache"]
        tm.that(restore.get("uses"), eq=f"{cache.repository}/restore@{cache.version}")
        tm.that(save.get("uses"), eq=f"{cache.repository}/save@{cache.version}")
        tm.that(str(save.get("if")), eq="${{ always() }}")
        restore_with = t.Cli.JSON_MAPPING_ADAPTER.validate_python(restore["with"])
        save_with = t.Cli.JSON_MAPPING_ADAPTER.validate_python(save["with"])
        path = f"~/{spec.home_cache_directory}/{spec.external_storage_directory}"
        tm.that(restore_with["path"], eq=path)
        tm.that(save_with["path"], eq=path)
        tm.that(save_with["key"], eq=restore_with["key"])
        tm.that(str(restore_with["key"]), has="${{ github.run_id }}")
        restore_prefix = str(restore_with["restore-keys"]).strip()
        tm.that(str(restore_with["key"]).startswith(restore_prefix), eq=True)
        tm.that(
            names.index("Restore Mypy cache") < names.index("Save Mypy cache"), eq=True
        )
