"""Lazy-init per-directory generation service — extracted concern."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, u

from ._lazy_init_generation_files import (
    FlextInfraCodegenLazyInitGenerationFilePlanMixin,
)
from ._lazy_init_generation_registry import (
    FlextInfraCodegenLazyInitGenerationRegistryMixin,
)

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from pathlib import Path

    from flext_infra import m, t
    from flext_infra.codegen.lazy_init_planner import FlextInfraCodegenLazyInitPlanner


# flext-i6nq.10: Root manifests and initializers are synchronized as one artifact set.
class FlextInfraCodegenLazyInitGenerationMixin(
    FlextInfraCodegenLazyInitGenerationFilePlanMixin,
    FlextInfraCodegenLazyInitGenerationRegistryMixin,
):
    """Plan ``__init__.py`` artifact sets per package directory."""

    if TYPE_CHECKING:
        repository_root: Path

    def _plan_all_inits(
        self,
        pkg_dirs: t.SequenceOf[Path],
        *,
        planner: FlextInfraCodegenLazyInitPlanner,
        target_package_dir: Path | None = None,
    ) -> t.VariadicTuple[m.Infra.LazyInitPlan]:
        """Resolve every selected package plan bottom-up without effects."""
        dir_exports: MutableMapping[str, t.LazyAliasMap] = {}
        planned: list[m.Infra.LazyInitPlan] = []
        progress_interval = max(1, len(pkg_dirs) // 20) if pkg_dirs else 1
        for idx, pkg_dir in enumerate(pkg_dirs, start=1):
            if idx == 1 or idx == len(pkg_dirs) or idx % progress_interval == 0:
                rel_path = (
                    pkg_dir.relative_to(self.repository_root)
                    if self.repository_root in pkg_dir.parents
                    else pkg_dir
                )
                u.Cli.info(f"lazy-init: progress {idx}/{len(pkg_dirs)} — {rel_path}")
            plan = planner.build_plan(pkg_dir, dir_exports=dir_exports)
            if plan.lazy_map:
                dir_exports[str(pkg_dir.resolve())] = dict(plan.lazy_map)
            should_process = (
                target_package_dir is None
                or pkg_dir.resolve() == target_package_dir.resolve()
                or (
                    target_package_dir.name == c.Infra.DIR_TESTS
                    and pkg_dir.resolve().is_relative_to(target_package_dir.resolve())
                )
            )
            if should_process:
                planned.append(plan)
            if (
                target_package_dir is not None
                and pkg_dir.resolve() == target_package_dir.resolve()
            ):
                break
        u.Cli.info(f"lazy-init: resolved {len(planned)} package artifact plans")
        return tuple(planned)


__all__: list[str] = ["FlextInfraCodegenLazyInitGenerationMixin"]
