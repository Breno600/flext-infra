"""Alias resolution (local and inherited) for the lazy-init planner."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, u

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraCodegenLazyInitPlannerAliasesMixin:
    if TYPE_CHECKING:
        rope_workspace: p.Infra.RopeWorkspaceDsl
        lazy_init: m.Infra.LazyInitConfig
        _parent_package_cache: dict[str, t.StrSequence]

        def _source_package_name(self, pkg_dir: Path, inherited_key: str) -> str: ...

        def _module_exports(
            self,
            py_file: Path,
            module_path: str,
            *,
            export_options: m.Infra.ExportOptions | None = None,
        ) -> t.MutableLazyAliasMap: ...

        def _package_entry(
            self, pkg_dir: Path
        ) -> m.Infra.RopePackageIndexEntry | None: ...

        def _parents_from_constants_module(
            self, module_path: Path, current_pkg: str, visited: set[str] | None = None
        ) -> t.StrSequence: ...

        def _resolve_inherited_alias_source(
            self,
            package_names: t.StrSequence,
            alias_name: str,
            *,
            current_pkg: str,
            use_test_runtime_aliases: bool,
        ) -> str: ...

    def _resolve_aliases(
        self,
        lazy_map: t.MutableLazyAliasMap,
        *,
        current_pkg: str,
        pkg_dir: Path,
        surface: str,
    ) -> None:
        """Inject configured namespace aliases into root-package lazy maps only.

        Nested packages export only their own discovered symbols; namespace
        aliases (``c``, ``t``, ``p``, ``m``, ``u``, ``s``) originate from
        project roots and wrapper surfaces only.
        """
        if not u.Infra.matches_project_namespace_package(current_pkg):
            return
        self._resolve_local_aliases(lazy_map, current_pkg=current_pkg, pkg_dir=pkg_dir)
        inherited_key = (
            surface if surface in self.lazy_init.inherited_exports else "src"
        )
        inherited_packages = self._resolve_transitive_parent_packages((
            *self._parent_packages(pkg_dir),
            self._source_package_name(pkg_dir, inherited_key),
        ))
        runtime_alias_names: list[str] = []
        if current_pkg == c.Infra.DIR_TESTS:
            runtime_alias_names = list(c.Infra.TEST_RUNTIME_ALIAS_TARGETS)
        alias_names = tuple(
            dict.fromkeys((
                *self.lazy_init.inherited_exports.get(inherited_key, ()),
                *runtime_alias_names,
            ))
        )
        local_alias_names = frozenset(
            alias_name
            for file_name, alias_name in self.lazy_init.public_file_aliases.items()
            if (pkg_dir / file_name).is_file()
        )
        for alias_name in alias_names:
            existing = lazy_map.get(alias_name)
            if (
                existing is not None
                and existing[0].startswith(current_pkg)
                and alias_name in local_alias_names
            ):
                continue
            package_name = self._resolve_inherited_alias_source(
                inherited_packages,
                alias_name,
                current_pkg=current_pkg,
                use_test_runtime_aliases=current_pkg == c.Infra.DIR_TESTS,
            )
            if package_name and package_name != current_pkg:
                lazy_map[alias_name] = (package_name, alias_name)

    def _resolve_local_aliases(
        self, lazy_map: t.MutableLazyAliasMap, *, current_pkg: str, pkg_dir: Path
    ) -> None:
        """Inject public_file_aliases from the lazy-init config into the lazy map."""
        alias_to_files: dict[str, list[str]] = {}
        for file_name, alias_name in self.lazy_init.public_file_aliases.items():
            alias_to_files.setdefault(alias_name, []).append(file_name)
        for alias_name, file_names in alias_to_files.items():
            existing = lazy_map.get(alias_name)
            if existing is not None and existing[0].startswith(current_pkg):
                continue
            for file_name in file_names:
                base_name = Path(file_name).stem
                module_file = pkg_dir / file_name
                package_dir = pkg_dir / base_name
                module_name = f"{current_pkg}.{base_name}"
                if module_file.is_file() and alias_name in self._module_exports(
                    module_file,
                    module_name,
                    export_options=m.Infra.ExportOptions(allow_assignments=True),
                ):
                    lazy_map[alias_name] = (module_name, alias_name)
                    break
                if package_dir.is_dir() and (package_dir / c.Infra.INIT_PY).is_file():
                    package_exports = self._module_exports(
                        package_dir / c.Infra.INIT_PY,
                        module_name,
                        export_options=m.Infra.ExportOptions(allow_assignments=True),
                    )
                    if alias_name in package_exports:
                        lazy_map[alias_name] = (module_name, alias_name)
                        break

    def _resolve_transitive_parent_packages(
        self, package_names: t.StrSequence
    ) -> t.StrSequence:
        """Return package_names plus transitive parents, ordered nearest-first.

        Breadth-first from the immediate parents outward: a directly declared
        parent (e.g. ``flext_web`` for ``flext_api``) is always resolved before
        its own ancestors (``flext_core`` and its submodules). This guarantees
        an inherited alias is sourced from the nearest owning facade rather than
        falling through to a distant root package that also re-exports it.
        """
        ordered: list[str] = []
        queue: list[str] = list(package_names)
        while queue:
            package_name = queue.pop(0)
            if not package_name or package_name in ordered:
                continue
            ordered.append(package_name)
            package_dir = self.rope_workspace.workspace_index.package_dir_by_name.get(
                package_name
            )
            if package_dir is not None:
                queue.extend(self._parent_packages(package_dir))
        return tuple(ordered)

    def _parent_packages(self, pkg_dir: Path) -> t.StrSequence:
        """Return the list of parent package names declared in constants.py."""
        cache_key = str(pkg_dir.resolve())
        cached = self._parent_package_cache.get(cache_key)
        if cached is not None:
            return cached
        package_entry = self._package_entry(pkg_dir)
        current_pkg = package_entry.package_name if package_entry is not None else ""
        constants_path = (pkg_dir / c.Infra.CONSTANTS_PY).resolve()
        if self.rope_workspace.resource(constants_path) is None:
            self._parent_package_cache[cache_key] = ()
            return ()
        parents = self._parents_from_constants_module(constants_path, current_pkg)
        self._parent_package_cache[cache_key] = parents
        return parents

    def _parents_from_constants_module(
        self, module_path: Path, current_pkg: str, visited: set[str] | None = None
    ) -> t.StrSequence:
        """Extract upstream package parents from a constants module."""
        seen = visited if visited is not None else set()
        seen.add(str(module_path.resolve()))
        state = self.rope_workspace.semantic(module_path)
        base_packages = tuple(
            package_name
            for class_info in state.class_infos
            if "Constants" in class_info.name
            for base_name in class_info.bases
            if (
                package_name := self._package_name_from_target(
                    state.declared_imports.get(base_name)
                    or state.semantic_imports.get(base_name, "")
                )
            )
        )
        declared_packages = tuple(
            package_name
            for target in state.declared_imports.values()
            if (package_name := self._package_name_from_target(target))
            and package_name != current_pkg
        )
        same_package_parents = tuple(
            parent
            for target in state.declared_imports.values()
            if target.startswith(f"{current_pkg}.")
            and (
                module_file := self._module_file(self._module_path_from_target(target))
            )
            is not None
            and str(module_file.resolve()) not in seen
            for parent in self._parents_from_constants_module(
                module_file, current_pkg, seen
            )
        )
        parents: list[str] = []
        for package_name in (*base_packages, *declared_packages, *same_package_parents):
            if (
                package_name
                and package_name != current_pkg
                and package_name not in parents
            ):
                parents.append(package_name)
        return tuple(parents)

    @staticmethod
    def _module_path_from_target(target: str) -> str:
        """Strip the trailing CapWords class name (if any) to yield a module path."""
        if "." not in target:
            return target
        prefix, suffix = target.rsplit(".", maxsplit=1)
        if suffix and suffix[0].isupper():
            return prefix
        return target

    def _package_name_from_target(self, target: str) -> str:
        """Return the longest workspace package name matching the dotted target."""
        parts = tuple(part for part in target.split(".") if part)
        for size in range(len(parts), 0, -1):
            package_name = ".".join(parts[:size])
            if package_name in self.rope_workspace.workspace_index.package_dir_by_name:
                return package_name
        if not parts:
            return ""
        sibling_project_root = self.rope_workspace.workspace_root.parent / parts[
            0
        ].replace("_", "-")
        sibling_package_root = sibling_project_root / c.Infra.DEFAULT_SRC_DIR / parts[0]
        if (
            sibling_project_root.joinpath(c.Infra.PYPROJECT_FILENAME).is_file()
            and sibling_package_root.joinpath(c.Infra.INIT_PY).is_file()
        ):
            return parts[0]
        if u.Infra.package_importable(parts[0]):
            return parts[0]
        return ""

    def _resolve_inherited_alias_source(
        self,
        package_names: t.StrSequence,
        alias_name: str,
        *,
        current_pkg: str,
        use_test_runtime_aliases: bool,
    ) -> str:
        """Return the package that owns the given alias in the inheritance chain."""
        candidate_packages: t.StrSequence = tuple(
            name for name in package_names if name
        )
        canonical_target = (
            c.Infra.TEST_RUNTIME_ALIAS_TARGETS.get(alias_name)
            if use_test_runtime_aliases
            else None
        )
        if canonical_target is not None:
            canonical_package: str = canonical_target[0]
            if canonical_package != current_pkg:
                return canonical_package
        for package_name in candidate_packages:
            if alias_name in self._export_names_for_package(package_name):
                return f"{package_name}"
        for package_name in candidate_packages:
            if (
                package_name
                not in self.rope_workspace.workspace_index.package_dir_by_name
                and alias_name in u.Infra.installed_package_exports(package_name)
            ):
                return f"{package_name}"
        return ""
