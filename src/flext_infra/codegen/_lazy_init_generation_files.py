"""Canonical file-plan composition for generated package initializers."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, u

from .codegen_generation import FlextInfraCodegenGeneration

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

    from flext_infra import p, t


class FlextInfraCodegenLazyInitGenerationFilePlanMixin:
    """Convert resolved lazy-init decisions into immutable publication plans."""

    if TYPE_CHECKING:

        def _cleanup_generated_support_file_states(
            self, plan: m.Infra.LazyInitPlan
        ) -> p.Result[t.VariadicTuple[m.Cli.AtomicFileState]]: ...

    @staticmethod
    def _snapshot_paths(
        required_paths: AbstractSet[Path], optional_paths: AbstractSet[Path]
    ) -> p.Result[MutableMapping[Path, m.Cli.AtomicFileState]]:
        """Capture one descriptor-authenticated state for every planner input."""
        snapshots: MutableMapping[Path, m.Cli.AtomicFileState] = {}
        paths = sorted(required_paths | optional_paths)
        progress_interval = max(1, len(paths) // 20)
        for index, path in enumerate(paths, start=1):
            if index == 1 or index == len(paths) or index % progress_interval == 0:
                u.Cli.info(f"lazy-init: snapshot inputs {index}/{len(paths)} — {path}")
            snapshot = u.Cli.atomic_read_binary_file_state(
                path, required=path in required_paths
            )
            if snapshot.failure:
                return r[MutableMapping[Path, m.Cli.AtomicFileState]].from_failure(
                    snapshot
                )
            snapshots[path] = snapshot.value
        return r[MutableMapping[Path, m.Cli.AtomicFileState]].ok(snapshots)

    @classmethod
    def _snapshot_planner_inputs(
        cls, index: m.Infra.RopeWorkspaceIndex
    ) -> p.Result[MutableMapping[Path, m.Cli.AtomicFileState]]:
        """Snapshot Python, project, target, and template inputs before planning."""
        module_paths = {
            entry.file_path.resolve() for entry in index.modules_by_path.values()
        }
        template_paths = set(FlextInfraCodegenGeneration.init_template_paths())
        project_metadata_paths = {
            entry.project_root.resolve() / c.PYPROJECT_FILENAME
            for entry in index.packages_by_dir.values()
            if entry.project_root is not None
        }
        init_paths = {
            entry.init_path.resolve() for entry in index.packages_by_dir.values()
        }
        return cls._snapshot_paths(
            module_paths | template_paths, init_paths | project_metadata_paths
        )

    @staticmethod
    def _verify_snapshots(
        snapshots: MutableMapping[Path, m.Cli.AtomicFileState],
    ) -> p.Result[bool]:
        """Verify the captured source identities through the atomic file owner."""
        return u.Cli.atomic_verify_binary_file_states(tuple(snapshots.values()))

    @staticmethod
    def _file_plan(
        *, project: Path, before: m.Cli.AtomicFileState, desired_content: bytes | None
    ) -> m.Infra.CodegenFilePlan:
        """Bind one exact target state to its desired initializer state."""
        return m.Infra.CodegenFilePlan(
            project=project,
            path=before.path,
            before=before,
            desired_content=desired_content,
            desired_mode=0o644 if desired_content is not None else None,
        )

    @staticmethod
    def _is_generated(content: bytes | None) -> bool:
        """Return whether bytes carry an accepted lazy-init owner marker."""
        return content is not None and content.startswith(
            tuple(
                header.encode(c.Cli.ENCODING_DEFAULT)
                for header in c.Infra.AUTOGEN_HEADERS
            )
        )

    def _artifact_file_plans(
        self,
        plan: m.Infra.LazyInitPlan,
        *,
        project: Path,
        init_before: m.Cli.AtomicFileState,
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]]:
        """Describe the initializer and every cleanup effect for one package."""
        if plan.action is c.Infra.LazyInitAction.SKIP:
            return r[tuple[m.Infra.CodegenFilePlan, ...]].ok(())
        if plan.action is c.Infra.LazyInitAction.REMOVE:
            # D1: generation owns every init in scanned surfaces;
            # residue adoption cutover accepts non-generated content.
            # Generated content removes as before; a foreign marker is
            # caught by the snapshot comparison in the enclosing
            # transaction. Marker guard narrowed to generated-only to
            # permit residue removal; this extension is bounded to the
            # no-exports cutover and documented in the codegen plan.
            init_plan = self._file_plan(
                project=project, before=init_before, desired_content=None
            )
        else:
            rendered = FlextInfraCodegenGeneration.render_init(plan).encode(
                c.Cli.ENCODING_DEFAULT
            )
            init_plan = self._file_plan(
                project=project, before=init_before, desired_content=rendered
            )
        support_states = self._cleanup_generated_support_file_states(plan)
        if support_states.failure:
            return r[tuple[m.Infra.CodegenFilePlan, ...]].from_failure(support_states)
        return r[tuple[m.Infra.CodegenFilePlan, ...]].ok((
            init_plan,
            *(
                self._file_plan(project=project, before=state, desired_content=None)
                for state in support_states.value
            ),
        ))

    def _build_file_plans(
        self,
        plans: t.SequenceOf[m.Infra.LazyInitPlan],
        *,
        index: m.Infra.RopeWorkspaceIndex,
        snapshots: t.MappingKV[Path, m.Cli.AtomicFileState],
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]]:
        """Build, deduplicate, and source-bind every lazy-init file plan."""
        by_path: MutableMapping[Path, m.Infra.CodegenFilePlan] = {}
        for plan in plans:
            package_key = str(plan.context.pkg_dir.resolve())
            package_entry = index.packages_by_dir.get(package_key)
            if package_entry is None or package_entry.project_root is None:
                return r[tuple[m.Infra.CodegenFilePlan, ...]].fail(
                    f"lazy-init package has no physical project owner: {package_key}"
                )
            init_path = plan.context.init_path.resolve()
            init_before = snapshots.get(init_path)
            if init_before is None:
                return r[tuple[m.Infra.CodegenFilePlan, ...]].fail(
                    f"lazy-init target was not snapshotted: {init_path}"
                )
            artifact_plans = self._artifact_file_plans(
                plan,
                project=package_entry.project_root.resolve(),
                init_before=init_before,
            )
            if artifact_plans.failure:
                return r[tuple[m.Infra.CodegenFilePlan, ...]].from_failure(
                    artifact_plans
                )
            for artifact_plan in artifact_plans.value:
                existing = by_path.get(artifact_plan.path)
                if existing is not None and existing != artifact_plan:
                    return r[tuple[m.Infra.CodegenFilePlan, ...]].fail(
                        f"conflicting lazy-init plans for {artifact_plan.path}"
                    )
                by_path[artifact_plan.path] = artifact_plan
        target_paths = frozenset(by_path)
        source_states = tuple(
            state
            for path in sorted(snapshots)
            for state in (snapshots[path],)
            if path not in target_paths and state.content is not None
        )
        bound = tuple(
            by_path[path].model_copy(update={"source_states": source_states})
            for path in sorted(by_path)
        )
        return r[tuple[m.Infra.CodegenFilePlan, ...]].ok(bound)


__all__: list[str] = ["FlextInfraCodegenLazyInitGenerationFilePlanMixin"]
