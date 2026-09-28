"""Read-only inventory of retired lazy-init support files."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, t, u

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenLazyInitGenerationRegistryMixin:
    """Describe stale generated sidecars without publishing any effect."""

    if TYPE_CHECKING:

        @staticmethod
        def _is_generated(content: bytes | None) -> bool: ...

    @staticmethod
    def _optional_state(path: Path) -> p.Result[m.Cli.AtomicFileState]:
        """Read one optional physical file state through the atomic owner."""
        return u.Cli.atomic_read_binary_file_state(path, required=False)

    @staticmethod
    def _path_flags(path: Path) -> p.Result[t.Quad[bool, bool, bool, bool]]:
        """Read one path classification while preserving filesystem failures."""
        try:
            flags = (path.is_symlink(), path.is_file(), path.exists(), path.is_dir())
        except OSError as exc:
            return r[tuple[bool, bool, bool, bool]].fail_op(
                f"classify lazy-init support path {path}", exc
            )
        return r[tuple[bool, bool, bool, bool]].ok(flags)

    @staticmethod
    def _glob_paths(
        directory: Path, pattern: str, *, operation: str
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Return deterministic glob results with their causal I/O failure."""
        try:
            paths = tuple(sorted(directory.glob(pattern)))
        except OSError as exc:
            return r[t.VariadicTuple[Path]].fail_op(operation, exc)
        return r[t.VariadicTuple[Path]].ok(paths)

    def _cleanup_generated_support_file_states(
        self, plan: m.Infra.LazyInitPlan
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicFileState]]:
        """Return the complete physical file set selected for deletion."""
        states: MutableMapping[Path, m.Cli.AtomicFileState] = {}
        for result in (
            self._obsolete_generated_file_states(plan),
            self._obsolete_root_support_states(plan),
            self._generated_export_sidecar_states(plan),
            self._generated_typing_stub_states(plan),
        ):
            if result.failure:
                return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(result)
            for state in result.value:
                previous = states.get(state.path)
                if previous is not None and previous != state:
                    return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                        f"lazy-init sidecar changed during inventory: {state.path}"
                    )
                states[state.path] = state
        return r[tuple[m.Cli.AtomicFileState, ...]].ok(
            tuple(states[path] for path in sorted(states))
        )

    def _obsolete_root_support_states(
        self, plan: m.Infra.LazyInitPlan
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicFileState]]:
        """Inventory closed root registries superseded by inline maps."""
        context = plan.context
        if (
            context.pkg_dir.parent.name != c.Infra.DEFAULT_SRC_DIR
            or "." in context.current_pkg
        ):
            return r[tuple[m.Cli.AtomicFileState, ...]].ok(())
        module_paths = tuple(
            context.pkg_dir / f"{name}.py"
            for name in sorted(c.Infra.OBSOLETE_ROOT_SUPPORT_NAMES)
        )
        package_paths = tuple(
            context.pkg_dir / name
            for name in sorted(c.Infra.OBSOLETE_ROOT_SUPPORT_NAMES)
        )
        stale_paths: list[Path] = []
        for path in (*module_paths, *package_paths):
            flags = self._path_flags(path)
            if flags.failure:
                return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(flags)
            is_symlink, is_file, exists, is_dir = flags.value
            if is_symlink:
                return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                    f"refusing obsolete root-support symlink: {path}"
                )
            if is_file:
                stale_paths.append(path)
                continue
            if not exists:
                continue
            if not is_dir:
                return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                    f"unexpected obsolete root-support path type: {path}"
                )
            children = self._glob_paths(
                path, "**/*", operation="inventory obsolete root support"
            )
            if children.failure:
                return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(children)
            for child in children.value:
                child_flags = self._path_flags(child)
                if child_flags.failure:
                    return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(
                        child_flags
                    )
                child_is_symlink, child_is_file, _, child_is_dir = child_flags.value
                if child_is_symlink:
                    return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                        f"refusing obsolete root-support symlink: {child}"
                    )
                if child_is_dir:
                    if child.name != "__pycache__":
                        return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                            f"unexpected directory in obsolete root support: {child}"
                        )
                    continue
                if not child_is_file or child.suffix not in {".py", ".pyi", ".pyc"}:
                    return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                        f"unexpected file in obsolete root support: {child}"
                    )
                stale_paths.append(child)
        return u.Infra.required_file_states(stale_paths)

    def _obsolete_generated_file_states(
        self, plan: m.Infra.LazyInitPlan
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicFileState]]:
        """Inventory generated artifacts retired by the inline-root contract."""
        states: list[m.Cli.AtomicFileState] = []
        for filename in c.Infra.OBSOLETE_GENERATED_INIT_FILES:
            path = plan.context.pkg_dir / filename
            state = self._optional_state(path)
            if state.failure:
                return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(state)
            if self._is_generated(state.value.content):
                states.append(state.value)
        return r[tuple[m.Cli.AtomicFileState, ...]].ok(tuple(states))

    def _generated_typing_stub_states(
        self, plan: m.Infra.LazyInitPlan
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicFileState]]:
        """Inventory stale codegen-owned ``__init__.pyi`` files."""
        stub_path = plan.context.pkg_dir / c.Infra.INIT_PYI
        state = self._optional_state(stub_path)
        if state.failure:
            return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(state)
        return r[tuple[m.Cli.AtomicFileState, ...]].ok(
            (state.value,) if self._is_generated(state.value.content) else ()
        )

    def _generated_export_sidecar_states(
        self, plan: m.Infra.LazyInitPlan
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicFileState]]:
        """Inventory legacy generated export files outside the canonical owner."""
        search_dirs = {
            plan.context.pkg_dir,
            plan.context.pkg_dir / c.Infra.ROOT_EXPORTS_DIR,
        }
        stale_paths: set[Path] = set()
        for base_dir in sorted(search_dirs):
            flags = self._path_flags(base_dir)
            if flags.failure:
                return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(flags)
            is_symlink, _, _, is_dir = flags.value
            if is_symlink:
                return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                    f"refusing generated sidecar directory symlink: {base_dir}"
                )
            if not is_dir:
                continue
            candidates = self._glob_paths(
                base_dir, "*.py", operation="inventory generated export sidecars"
            )
            if candidates.failure:
                return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(candidates)
            for path in candidates.value:
                if not c.Infra.GENERATED_EXPORT_SIDECAR_RE.match(path.name):
                    continue
                path_flags = self._path_flags(path)
                if path_flags.failure:
                    return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(path_flags)
                path_is_symlink, path_is_file, _, _ = path_flags.value
                if path_is_symlink:
                    return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                        f"refusing generated sidecar symlink: {path}"
                    )
                if path_is_file:
                    stale_paths.add(path)
        constants_dir = plan.context.pkg_dir / c.Infra.ROOT_EXPORTS_DIR
        constants_init = constants_dir / c.Infra.INIT_PY
        init_flags = self._path_flags(constants_init)
        if init_flags.failure:
            return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(init_flags)
        init_is_symlink, init_is_file, _, _ = init_flags.value
        if init_is_symlink:
            return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                f"refusing generated constants initializer symlink: {constants_init}"
            )
        if init_is_file:
            modules = self._glob_paths(
                constants_dir, "*.py", operation="inventory generated constants package"
            )
            if modules.failure:
                return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(modules)
            remaining_modules = tuple(
                path
                for path in modules.value
                if path.name != c.Infra.INIT_PY and path not in stale_paths
            )
            if not remaining_modules:
                init_state = self._optional_state(constants_init)
                if init_state.failure:
                    return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(init_state)
                if self._is_generated(init_state.value.content):
                    stale_paths.add(constants_init)
        return u.Infra.required_file_states(stale_paths)


__all__: list[str] = ["FlextInfraCodegenLazyInitGenerationRegistryMixin"]
