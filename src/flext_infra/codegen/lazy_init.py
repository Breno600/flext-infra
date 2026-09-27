"""Lazy-init ``__init__.py`` publication planner (PEP 562).

Auto-discovers exports from sibling ``.py`` files and describes clean
lazy-loading ``__init__.py`` artifacts using ``flext_core``.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, override

from flext_core import r

from .. import c, config, m, u
from ..workspace.rope import FlextInfraRopeWorkspace
from ._execution import FlextInfraCodegenExecutionBase
from ._lazy_init_generation import FlextInfraCodegenLazyInitGenerationMixin
from .lazy_init_planner import FlextInfraCodegenLazyInitPlanner

if TYPE_CHECKING:
    from .. import p, t


class FlextInfraCodegenLazyInit(
    FlextInfraCodegenExecutionBase[bool], FlextInfraCodegenLazyInitGenerationMixin
):
    """Plan ``__init__.py`` artifacts with PEP 562 lazy imports.

    Scans sibling ``.py`` files in each package directory, discovers their
    exports, and returns immutable file plans for the generation transaction.
    Processes bottom-up so child packages are generated before parents.
    """

    _modified_files: t.Infra.StrSet = u.PrivateAttr(default_factory=set)

    @property
    def modified_files(self) -> t.StrSequence:
        """Initializer artifacts whose immutable plans require an effect."""
        return tuple(sorted(self._modified_files))

    @override
    def execute(self) -> p.Result[bool]:
        """Check lazy-init drift; publication belongs to conform's transaction."""
        planned = self.plan_files()
        if planned.failure:
            return r[bool].from_failure(planned)
        if not self.effective_dry_run:
            return r[bool].fail(
                "lazy-init publication is owned by codegen conform; "
                "the generation transaction must publish plan_files()"
            )
        changed = tuple(
            plan
            for plan in planned.value.files
            if u.Infra.codegen_file_requires_effect(plan)
        )
        if changed:
            drifted_files = ", ".join(str(plan.path) for plan in changed)
            return r[bool].fail(
                f"init drift detected in {len(changed)} "
                f"generated artifacts: {drifted_files}"
            )
        return r[bool].ok(True)

    def plan_files(self) -> p.Result[m.Infra.CodegenPhaseAnalysis]:
        """Return one complete immutable lazy-init analysis receipt."""
        self._modified_files.clear()
        if not self.repository_root.is_dir():
            return r[m.Infra.CodegenPhaseAnalysis].fail(
                f"lazy-init workspace is not a directory: {self.repository_root}"
            )
        started_at = perf_counter()
        u.Cli.info(
            f"lazy-init: planning read-only artifacts for {self.repository_root}"
        )
        planned = self._plan_in_workspace()
        if planned.failure:
            return r[m.Infra.CodegenPhaseAnalysis].from_failure(planned)
        analysis = planned.value
        changed = tuple(
            plan
            for plan in analysis.files
            if u.Infra.codegen_file_requires_effect(plan)
        )
        self._modified_files.update(str(plan.path) for plan in changed)
        u.Cli.info(
            f"Lazy-init plan: {len(changed)} effects "
            f"({perf_counter() - started_at:.2f}s)"
        )
        return r[m.Infra.CodegenPhaseAnalysis].ok(analysis)

    def _plan_in_workspace(self) -> p.Result[m.Infra.CodegenPhaseAnalysis]:
        """Open Rope once and propagate every planner or filesystem failure.

        Retries the entire planning cycle when snapshot verification detects
        concurrent input changes (RC-A: deterministic lazy-init under concurrency).
        """
        max_retries = (
            self.lazy_init.planning_max_retries if hasattr(self, "lazy_init") else 1
        )
        last_failure: p.Result[m.Infra.CodegenPhaseAnalysis] | None = None
        for attempt in range(max_retries + 1):
            try:
                result = self._plan_attempt()
            except c.EXC_OS_VALUE as exc:
                return r[m.Infra.CodegenPhaseAnalysis].fail_op(
                    "lazy-init planning", exc
                )
            if result.success:
                return result
            # Retry only on snapshot verification failure (a concurrent input
            # change). `failure` is the boolean predicate, so the previous form
            # matched the marker against "True" and never retried; the message
            # lives in `error`.
            concurrent_change = "lazy-init source changed during planning" in (
                result.error or ""
            )
            if concurrent_change and attempt < max_retries:
                u.Cli.info(
                    "lazy-init: concurrent change detected "
                    f"(attempt {attempt + 1}/{max_retries + 1}), retrying"
                )
                last_failure = result
                continue
            return result
        return last_failure or r[m.Infra.CodegenPhaseAnalysis].fail(
            "lazy-init planning failed after retries"
        )

    def _plan_attempt(self) -> p.Result[m.Infra.CodegenPhaseAnalysis]:
        """Run one planning cycle inside its own Rope workspace."""
        with FlextInfraRopeWorkspace.open_workspace(
            self.repository_root, rope_repository_root=self.repository_root
        ) as rope:
            return self._plan_open_workspace(rope)

    def _plan_open_workspace(
        self, rope: FlextInfraRopeWorkspace
    ) -> p.Result[m.Infra.CodegenPhaseAnalysis]:
        """Build immutable plans from one stable Rope workspace snapshot."""
        workspace_index = rope.workspace_index
        resolved_repository_root = self.repository_root.resolve()
        indexed_package_dirs = tuple(
            sorted(
                (
                    package_dir.resolve()
                    for package_dir in workspace_index.package_dirs
                    if package_dir.is_relative_to(resolved_repository_root)
                    and not frozenset(
                        package_dir.relative_to(resolved_repository_root).parts
                    )
                    & c.Infra.OBSOLETE_ROOT_SUPPORT_NAMES
                ),
                key=u.Infra.path_depth,
                reverse=True,
            )
        )
        target_package_dir: Path | None = None
        if self.target_module:
            mapped_package_dir = workspace_index.package_dir_by_name.get(
                self.target_module
            )
            target_module_dirs = frozenset(
                entry.package_dir.resolve()
                for entry in workspace_index.modules_by_path.values()
                if entry.module_name == self.target_module
            )
            if mapped_package_dir is not None:
                target_module_dirs = frozenset((
                    *target_module_dirs,
                    mapped_package_dir.resolve(),
                ))
            sorted_target_dirs = tuple(sorted(target_module_dirs))
            if not sorted_target_dirs:
                return r[m.Infra.CodegenPhaseAnalysis].fail(
                    f"lazy-init target module not found: {self.target_module}"
                )
            if sorted_target_dirs[1:]:
                return r[m.Infra.CodegenPhaseAnalysis].fail(
                    f"lazy-init target module is ambiguous: {self.target_module}"
                )
            target_package_dir = sorted_target_dirs[0]
            if target_package_dir not in indexed_package_dirs:
                return r[m.Infra.CodegenPhaseAnalysis].fail(
                    f"lazy-init target belongs to retired support: {self.target_module}"
                )
        package_dirs = self._package_dirs_for_target(
            indexed_package_dirs,
            target_package_dir=target_package_dir,
            repository_root=resolved_repository_root,
        )
        snapshots = self._snapshot_planner_inputs(workspace_index)
        if snapshots.failure:
            return r[m.Infra.CodegenPhaseAnalysis].from_failure(snapshots)
        planner = FlextInfraCodegenLazyInitPlanner(
            rope_workspace=rope, lazy_init=config.Infra.tooling.lazy_init
        )
        u.Cli.info(f"lazy-init: planning {len(package_dirs)} package dirs")
        package_plans = self._plan_all_inits(
            package_dirs, planner=planner, target_package_dir=target_package_dir
        )
        if planner.collision_count:
            return r[m.Infra.CodegenPhaseAnalysis].fail(
                "lazy-init public export ownership is ambiguous: "
                f"{planner.collision_count} collision(s)"
            )
        file_plans = self._build_file_plans(
            package_plans, index=workspace_index, snapshots=snapshots.value
        )
        if file_plans.failure:
            return r[m.Infra.CodegenPhaseAnalysis].from_failure(file_plans)
        # One writer per destination (render purity, v4 §2.1): templates own
        # every generated surface; alignment is a semantic phase of ``make
        # mod`` (codemod/semantic_apply.py phase 0), never a second writer
        # inside the gen transaction.
        all_plans = file_plans.value
        stable = self._verify_snapshots(snapshots.value)
        if stable.failure:
            return r[m.Infra.CodegenPhaseAnalysis].from_failure(stable)
        return r[m.Infra.CodegenPhaseAnalysis].ok(
            m.Infra.CodegenPhaseAnalysis(
                phase="lazy-init",
                files=all_plans,
                inputs=tuple(snapshots.value[path] for path in sorted(snapshots.value)),
                publications=tuple(package_plans),
            )
        )

    @staticmethod
    def _package_dirs_for_target(
        indexed_package_dirs: t.SequenceOf[Path],
        *,
        target_package_dir: Path | None,
        repository_root: Path,
    ) -> t.VariadicTuple[Path]:
        """Select the target's source/test scope and its production sibling."""
        if target_package_dir is None:
            return tuple(indexed_package_dirs)
        target_parts = target_package_dir.relative_to(repository_root).parts
        boundary_names = frozenset({
            c.Infra.DEFAULT_SRC_DIR,
            *c.Infra.NON_PUBLIC_LAZY_ROOTS,
        })
        boundary_index = next(
            (
                index
                for index, part in enumerate(target_parts)
                if part in boundary_names
            ),
            len(target_parts) - 1,
        )
        scope_prefix = target_parts[: boundary_index + 1]
        project_prefix = target_parts[:boundary_index]
        production_prefix = (*project_prefix, c.Infra.DEFAULT_SRC_DIR)
        return tuple(
            package_dir
            for package_dir in indexed_package_dirs
            if package_dir.relative_to(repository_root).parts[: len(scope_prefix)]
            == scope_prefix
            or package_dir.relative_to(repository_root).parts[: len(production_prefix)]
            == production_prefix
        )


__all__: list[str] = ["FlextInfraCodegenLazyInit"]
