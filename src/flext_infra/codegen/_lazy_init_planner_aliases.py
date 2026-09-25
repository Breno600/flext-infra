"""Alias resolution (local and inherited) for the lazy-init planner."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, u

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraCodegenLazyInitPlannerAliasesMixin:
    if TYPE_CHECKING:
        rope_workspace: p.Infra.RopeWorkspaceDsl
        lazy_init: m.Infra.LazyInitConfig
        _parent_package_cache: MutableMapping[str, t.StrSequence]

        def _source_package_name(self, pkg_dir: Path, inherited_key: str) -> str: ...

        def _package_entry(
            self, pkg_dir: Path
        ) -> m.Infra.RopePackageIndexEntry | None: ...

        def _export_names_for_package(self, package_name: str) -> frozenset[str]: ...

        def _package_name_from_target(self, target: str) -> str: ...

        def _parents_from_constants_module(
            self, module_path: Path, current_pkg: str, visited: set[str] | None = None
        ) -> t.StrSequence: ...

        def _resolve_inherited_alias_source(
            self, package_names: t.StrSequence, alias_name: str, *, current_pkg: str
        ) -> str: ...

    def _resolve_aliases(
        self,
        lazy_map: t.MutableLazyAliasMap,
        *,
        current_pkg: str,
        pkg_dir: Path,
        surface: str,
    ) -> None:
        """Inherit declared aliases without inventing missing local bindings."""
        project_root = u.Infra.project_root(pkg_dir)
        if project_root is None:
            return
        layout = self.rope_workspace.layout(project_root)
        if pkg_dir.parent != project_root and (
            layout is None or pkg_dir != layout.package_dir
        ):
            return
        local_owners = {
            alias
            for module_path in sorted(pkg_dir.glob("*.py"))
            if module_path.name != c.Infra.INIT_PY and module_path.stem.isidentifier()
            if (
                alias := u.Infra.publication_policy(
                    module_path, rope_project=self.rope_workspace.rope_project
                ).expected_alias
            )
            is not None
        }
        inherited_packages = self._resolve_transitive_parent_packages((
            *self._parent_packages(pkg_dir),
            self._source_package_name(pkg_dir, surface),
        ))
        # Discovery reads only the facade parents, never the dependency closure:
        # a dev or codegen dependency is a consumer, never a facade ancestor.
        # An indexed parent is read from its declared sources (its generated
        # initializer is this run's output, never its input); an external
        # parent is read from its published initializer.
        alias_names = tuple(
            dict.fromkeys(
                name
                for package_name in inherited_packages
                for name in self._export_names_for_package(package_name)
                if name.isidentifier() and name.islower() and not name.startswith("_")
            )
        )
        for alias_name in alias_names:
            # A missing local declaration is a source finding. Inheriting a
            # parent's value here would conceal it and change the local MRO.
            if alias_name in local_owners:
                continue
            existing = lazy_map.get(alias_name)
            if existing is not None and existing[0] != current_pkg:
                continue
            package_name = self._resolve_inherited_alias_source(
                inherited_packages, alias_name, current_pkg=current_pkg
            )
            if package_name and package_name != current_pkg:
                lazy_map[alias_name] = (package_name, alias_name)
            elif existing is not None and existing[0] == current_pkg:
                del lazy_map[alias_name]

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
