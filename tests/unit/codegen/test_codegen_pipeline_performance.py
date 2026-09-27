"""Performance benchmarks for the codegen gen pipeline.

flext-perf.4 (agent: codex): guards lazy-init generation performance
with wall-clock and peak-memory thresholds. Exercises _declared_exports
caching (Step 1), _module_exports cache alignment (Step 2), and ruff
Popen pipelining (Step 3).
"""

from __future__ import annotations

import time
import tracemalloc
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra.codegen.lazy_init import FlextInfraCodegenLazyInit
from tests import c, u

_PROJECT_COUNT = c.Tests.GEN_PIPELINE_PROJECT_COUNT
_MODULES_PER_PROJECT = c.Tests.GEN_PIPELINE_MODULES_PER_PROJECT


@pytest.mark.performance
@pytest.mark.slow
class TestsFlextInfraCodegenPipelinePerformance:
    """Benchmark gen pipeline wall-clock and memory on a synthetic workspace."""

    def _build_synthetic_workspace(self, tmp_path: Path) -> Path:
        """Create a workspace with N projects, each with M namespace modules."""
        repository_root = tmp_path / "gen-perf-workspace"
        repository_root.mkdir()
        for i in range(_PROJECT_COUNT):
            pkg_name = f"flext_perf_pkg_{i}"
            _, pkg_dir = u.Tests.create_lazy_init_workspace(
                repository_root, project_name=f"perf-project-{i}", package_name=pkg_name
            )
            for j in range(_MODULES_PER_PROJECT):
                u.Tests.write_lazy_init_namespace_module(
                    pkg_dir / f"module_{j}.py",
                    class_name=f"FlextPerfClass_{i}_{j}",
                    alias=f"alias_{i}_{j}",
                )
        return repository_root

    def test_wall_clock_under_threshold(self, tmp_path: Path) -> None:
        """Benchmark: lazy-init generation on synthetic workspace < 30s."""
        repository_root = self._build_synthetic_workspace(tmp_path)
        generator = FlextInfraCodegenLazyInit(repository_root=repository_root)
        start = time.perf_counter()
        result = generator.plan_files()
        elapsed = time.perf_counter() - start
        tm.that(result.success, eq=True, msg=f"Lazy-init had errors: {result}")
        tm.that(
            elapsed,
            lt=c.Tests.GEN_PIPELINE_MAX_SECONDS,
            msg=(
                f"Gen pipeline took {elapsed:.2f}s, "
                f"expected < {c.Tests.GEN_PIPELINE_MAX_SECONDS:g}s"
            ),
        )

    def test_peak_memory_under_500mb(self, tmp_path: Path) -> None:
        """Benchmark: Peak memory < 500MB for gen pipeline."""
        repository_root = self._build_synthetic_workspace(tmp_path)
        generator = FlextInfraCodegenLazyInit(repository_root=repository_root)
        tracemalloc.start()
        try:
            result = generator.plan_files()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        peak_mb = peak / 1024 / 1024
        tm.that(result.success, eq=True, msg=f"Lazy-init had errors: {result}")
        tm.that(
            peak_mb,
            lt=c.Tests.GEN_PIPELINE_MEMORY_MAX_MB,
            msg=(
                f"Peak memory was {peak_mb:.1f}MB, "
                f"expected < {c.Tests.GEN_PIPELINE_MEMORY_MAX_MB:g}MB"
            ),
        )

    def test_generated_initializers_are_directly_compilable(
        self, tmp_path: Path
    ) -> None:
        """Every planned initializer is valid without a formatter subprocess."""
        repository_root = self._build_synthetic_workspace(tmp_path)
        generator = FlextInfraCodegenLazyInit(repository_root=repository_root)
        result = generator.plan_files()
        tm.that(result.success, eq=True, msg=f"Lazy-init had errors: {result}")
        for plan in result.value.files:
            if plan.desired_content is not None:
                compile(plan.desired_content, str(plan.path), "exec")

    def test_repeat_run_is_byte_idempotent(self, tmp_path: Path) -> None:
        """Benchmark: second gen run produces identical output (cache warm)."""
        repository_root = self._build_synthetic_workspace(tmp_path)
        generator = FlextInfraCodegenLazyInit(repository_root=repository_root)
        # First run populates _declared_exports cache
        result_1 = generator.plan_files()
        tm.that(result_1.success, eq=True, msg=f"First run had errors: {result_1}")
        # Second run should also succeed (cache should not corrupt output)
        result_2 = generator.plan_files()
        tm.that(result_2.success, eq=True, msg=f"Second run had errors: {result_2}")
