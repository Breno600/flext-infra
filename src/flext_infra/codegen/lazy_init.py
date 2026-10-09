"""Lazy-init ``__init__.py`` publication planner (PEP 562).

Auto-discovers exports from sibling ``.py`` files and describes clean
lazy-loading ``__init__.py`` artifacts using ``flext_core``.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Annotated, override

from flext_infra import c, config, m, r, t, u
from flext_infra.codegen._execution import FlextInfraCodegenExecutionBase
from flext_infra.codegen._lazy_init_generation import (
    FlextInfraCodegenLazyInitGenerationMixin,
)
from flext_infra.codegen._lazy_init_projection_manifest import (
    FlextInfraCodegenLazyInitProjectionManifest,
)
from flext_infra.codegen.lazy_init_planner import FlextInfraCodegenLazyInitPlanner
from flext_infra.workspace.rope import FlextInfraRopeWorkspace

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenLazyInit(
    FlextInfraCodegenExecutionBase[bool],
    FlextInfraCodegenLazyInitGenerationMixin,
):
    """Plan ``__init__.py`` artifacts with PEP 562 lazy imports.

    Scans sibling ``.py`` files in each package directory, discovers their
    exports, and returns immutable file plans for the generation transaction.
    Processes bottom-up so child packages are generated before parents.
    """

    _modified_files: t.Infra.StrSet = u.PrivateAttr(default_factory=set)
    project_scope_roots: Annotated[
        t.VariadicTuple[Path] | None,
        m.Field(
            description=(
                "Repository roots selected by conformance; None plans every "
                "package of the workspace"
            ),
        ),
    ] = None

    @property
    def modified_files(self) -> t.StrSequence:
        """Initializer artifacts whose immutable plans require an effect."""
        return tuple(sorted(self._modified_files))

    @override
    def execute(self) -> p.Result[bool]:
        """Check lazy-init drift; publication belongs to conform's transaction.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        planned = self.plan_files()
        if planned.failure:
            return r[bool].from_failure(planned)
        if not self.effective_dry_run:
            return r[bool].fail(
                "lazy-init publication is owned by codegen conform; "
                "the generation transaction must publish plan_files()",
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
                f"generated artifacts: {drifted_files}",
            )
        return r[bool].ok(value=True)

    def plan_files(self) -> p.Result[m.Infra.CodegenPhaseAnalysis]:
        """Return one complete immutable lazy-init analysis receipt.

        Returns:
            One complete immutable lazy-init analysis receipt.

        """
        self._modified_files.clear()
        if not self.repository_root.is_dir():
            return r[m.Infra.CodegenPhaseAnalysis].fail(
                f"lazy-init workspace is not a directory: {self.repository_root}",
            )
        resolved_repository_root = self.repository_root.resolve()
        for scope_root in self.project_scope_roots or ():
            resolved_scope_root = scope_root.resolve()
            if not resolved_scope_root.is_dir() or not (
                resolved_scope_root.is_relative_to(resolved_repository_root)
            ):
                return r[m.Infra.CodegenPhaseAnalysis].fail(
                    "lazy-init repository scope is missing or outside "
                    f"{resolved_repository_root}: {scope_root}",
                )
        started_at = perf_counter()
        u.Cli.info(
            f"lazy-init: planning read-only artifacts for {self.repository_root}",
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
            f"({perf_counter() - started_at:.2f}s)",
        )
        return r[m.Infra.CodegenPhaseAnalysis].ok(analysis)

    def _plan_in_workspace(self) -> p.Result[m.Infra.CodegenPhaseAnalysis]:
        """Plan once against a stable snapshot and expose the first failure.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenPhaseAnalysis]``.

        """
        return self._plan_attempt()

    def _plan_attempt(self) -> p.Result[m.Infra.CodegenPhaseAnalysis]:
        """Compose explicitly selected repositories without widening their indexes.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenPhaseAnalysis]``.

        """
        roots = (
            (self.repository_root.resolve(),)
            if self.project_scope_roots is None
            else tuple(sorted({root.resolve() for root in self.project_scope_roots}))
        )
        analyses: list[m.Infra.CodegenPhaseAnalysis] = []
        inputs: t.MutableMappingKV[Path, m.Cli.AtomicFileState] = {}
        target_roots = 0
        for root in roots:
            with FlextInfraRopeWorkspace.open_workspace(
                root,
                rope_repository_root=root,
            ) as rope:
                if self.target_module:
                    targets = self._target_package_dirs(rope.workspace_index, root)
                    if not targets:
                        continue
                    target_roots += 1
                    if target_roots > 1:
                        return r[m.Infra.CodegenPhaseAnalysis].fail(
                            f"lazy-init target module is ambiguous: "
                            f"{self.target_module}",
                        )
                planned = self._plan_open_workspace(rope)
                if planned.failure:
                    return r[m.Infra.CodegenPhaseAnalysis].from_failure(planned)
                analyses.append(planned.value)
                for state in planned.value.inputs:
                    previous = inputs.get(state.path)
                    if previous is not None and previous != state:
                        return r[m.Infra.CodegenPhaseAnalysis].fail(
                            f"lazy-init shared input changed between "
                            f"repositories: {state.path}",
                        )
                    inputs[state.path] = state
        if self.target_module and not target_roots:
            return r[m.Infra.CodegenPhaseAnalysis].fail(
                f"lazy-init target module not found: {self.target_module}",
            )
        stable = self._verify_snapshots(inputs)
        if stable.failure:
            return r[m.Infra.CodegenPhaseAnalysis].from_failure(stable)
        composed = tuple(file for analysis in analyses for file in analysis.files)
        manifests = (
            FlextInfraCodegenLazyInitProjectionManifest.projection_manifest_plans(
                files=composed,
            )
        )
        if manifests.failure:
            return r[m.Infra.CodegenPhaseAnalysis].from_failure(manifests)
        return r[m.Infra.CodegenPhaseAnalysis].ok(
            m.Infra.CodegenPhaseAnalysis(
                phase=c.Infra.CodegenStagedFilePhase.LAZY_INIT,
                files=composed + manifests.value,
                inputs=tuple(inputs[path] for path in sorted(inputs)),
                publications=tuple(
                    plan for analysis in analyses for plan in analysis.publications
                ),
            ),
        )

    def _target_package_dirs(
        self,
        index: m.Infra.RopeWorkspaceIndex,
        root: Path,
    ) -> t.VariadicTuple[Path]:
        """Resolve the target through the current repository's authenticated index.

        Returns:
            The resulting ``t.VariadicTuple[Path]``.

        """
        if self.target_module is None:
            return ()
        mapped = index.package_dir_by_name.get(self.target_module)
        targets = {
            entry.package_dir.resolve()
            for entry in index.modules_by_path.values()
            if entry.module_name == self.target_module
            and (self.project_scope_roots is None or entry.project_root == root)
        }
        if mapped is not None and (
            self.project_scope_roots is None
            or index.packages_by_dir[str(mapped)].project_root == root
        ):
            targets.add(mapped.resolve())
        return tuple(sorted(targets))

    def _plan_open_workspace(
        self,
        rope: FlextInfraRopeWorkspace,
    ) -> p.Result[m.Infra.CodegenPhaseAnalysis]:
        """Build immutable plans from one stable Rope workspace snapshot.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenPhaseAnalysis]``.

        """
        workspace_index = rope.workspace_index
        resolved_repository_root = self.repository_root.resolve()
        candidate_entries = tuple(
            workspace_index.packages_by_dir[str(package_dir)]
            for package_dir in workspace_index.package_dirs
            if package_dir.is_relative_to(resolved_repository_root)
            and not frozenset(package_dir.relative_to(resolved_repository_root).parts)
            & c.Infra.OBSOLETE_ROOT_SUPPORT_NAMES
        )
        if self.project_scope_roots is not None:
            unowned = tuple(
                entry.package_dir
                for entry in candidate_entries
                if entry.project_root is None
            )
            if unowned:
                return r[m.Infra.CodegenPhaseAnalysis].fail(
                    f"lazy-init package has no repository owner: {unowned[0]}",
                )
            candidate_entries = tuple(
                entry
                for entry in candidate_entries
                if entry.project_root == rope.repository_root.resolve()
            )
        indexed_package_dirs = tuple(
            sorted(
                (entry.package_dir.resolve() for entry in candidate_entries),
                key=u.Infra.path_depth,
                reverse=True,
            ),
        )
        target_package_dir: Path | None = None
        if self.target_module:
            sorted_target_dirs = self._target_package_dirs(
                workspace_index,
                rope.repository_root.resolve(),
            )
            if not sorted_target_dirs:
                return r[m.Infra.CodegenPhaseAnalysis].fail(
                    f"lazy-init target module not found: {self.target_module}",
                )
            if sorted_target_dirs[1:]:
                return r[m.Infra.CodegenPhaseAnalysis].fail(
                    f"lazy-init target module is ambiguous: {self.target_module}",
                )
            target_package_dir = sorted_target_dirs[0]
            if target_package_dir not in indexed_package_dirs:
                return r[m.Infra.CodegenPhaseAnalysis].fail(
                    f"lazy-init target belongs to retired support: "
                    f"{self.target_module}",
                )
        package_dirs = self._package_dirs_for_target(
            indexed_package_dirs,
            target_package_dir=target_package_dir,
            repository_root=resolved_repository_root,
        )
        snapshots = self._snapshot_planner_inputs(workspace_index, package_dirs)
        if snapshots.failure:
            return r[m.Infra.CodegenPhaseAnalysis].from_failure(snapshots)
        planner = FlextInfraCodegenLazyInitPlanner(
            rope_workspace=rope,
            lazy_init=config.Infra.tooling.lazy_init,
        )
        u.Cli.info(f"lazy-init: planning {len(package_dirs)} package dirs")
        package_plans = self._plan_all_inits(
            package_dirs,
            planner=planner,
            target_package_dir=target_package_dir,
        )
        if planner.collision_count:
            return r[m.Infra.CodegenPhaseAnalysis].fail(
                "lazy-init public export ownership is ambiguous: "
                f"{planner.collision_count} collision(s)",
            )
        file_plans = self._build_file_plans(
            package_plans,
            index=workspace_index,
            snapshots=snapshots.value,
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
            ),
        )

    @staticmethod
    def _package_dirs_for_target(
        indexed_package_dirs: t.SequenceOf[Path],
        *,
        target_package_dir: Path | None,
        repository_root: Path,
    ) -> t.VariadicTuple[Path]:
        """Select the target's source/test scope and its production sibling.

        Returns:
            The resulting ``t.VariadicTuple[Path]``.

        """
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
