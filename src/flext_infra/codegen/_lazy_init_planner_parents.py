"""Rope-semantic parent resolution for the lazy-init planner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, u

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraCodegenLazyInitPlannerParentsMixin:
    """Resolve inherited packages from Rope scopes and import names only."""

    if TYPE_CHECKING:
        rope_workspace: p.Infra.RopeWorkspaceDsl
        _source_exports_cache: MutableMapping[str, frozenset[str]]

        def _module_file(self, module_path: str) -> Path | None: ...

        def _parent_packages(self, pkg_dir: Path) -> t.StrSequence: ...

    def _parents_from_constants_module(
        self, module_path: Path, current_pkg: str, visited: set[str] | None = None
    ) -> t.StrSequence:
        """Follow declared facade bases, including same-package compositions.

        Importing a dependency does not make it a facade ancestor. Only bases
        contribute parents; walking every import leaked unrelated APIs such
        as regex helpers into workspace-dependent publication plans.
        """
        seen = visited if visited is not None else set()
        seen.add(str(module_path.resolve()))
        resource = self.rope_workspace.resource(module_path)
        if resource is None:
            msg = f"parent declaration source unavailable: {module_path}"
            raise ValueError(msg)
        imports = u.Infra.get_declared_module_imports(
            self.rope_workspace.rope_project, resource
        )
        classes = u.Infra.class_info_from_source(resource.read())
        base_targets = tuple(
            target + (f".{tail}" if tail else "")
            for class_info in classes
            if "Constants" in class_info.name
            for base_name in class_info.bases
            for head, _separator, tail in (base_name.partition("."),)
            if (target := imports.get(head))
        )
        base_packages = tuple(
            self._declared_parent_package(target)
            for target in base_targets
            if not target.startswith(f"{current_pkg}.")
        )
        same_package_parents = tuple(
            parent
            for target in base_targets
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
        # flext-j47u (codex): Rope state is the sole parent fact source; the old
        # stdlib-AST fallback duplicated this exact import/class walk.
        parents: list[str] = []
        for package_name in (*base_packages, *same_package_parents):
            if (
                package_name
                and package_name != current_pkg
                and package_name not in parents
            ):
                parents.append(package_name)
        return tuple(parents)

    def _declared_parent_package(self, target: str) -> str:
        """Return the package a class base declares as facade parent.

        A base names a DECLARED parent: it must resolve (indexed source or the
        active environment). Resolving nowhere is a fact to surface, never a
        silently dropped parent (flext-b3xmn).
        """
        package_name = self._package_name_from_target(target)
        if package_name:
            return package_name
        msg = (
            f"lazy-init: declared facade parent '{target.split('.', 1)[0]}' "
            "resolves nowhere in the active environment"
        )
        raise ValueError(msg)

    @staticmethod
    def _module_path_from_target(target: str) -> str:
        """Strip the trailing CapWords class name (if any) to yield a module path.

        ``rope`` ``declared_imports`` values are fully-qualified dotted symbol
        paths -- for ``from pkg.sub import FooBar`` the value is
        ``pkg.sub.FooBar``. Drop the last segment when it starts with an
        uppercase letter (class convention).
        """
        if "." not in target:
            return target
        prefix, suffix = target.rsplit(".", maxsplit=1)
        if suffix and suffix[0].isupper():
            return prefix
        return target

    def _resolve_inherited_alias_source(
        self, package_names: t.StrSequence, alias_name: str, *, current_pkg: str
    ) -> str:
        """Return the nearest facade parent serving an inherited facade letter.

        Only facade letters are inherited (ADR-015 R1a): a name whose declarer,
        reached through the parent's published re-export chain, binds it to a
        class. Singleton instances and entry points (``cli``, ``infra``,
        ``main``, ``docs_main``) stay in the root that declares them (operator
        ruling 2026-09-23). The letter is sourced from the NEAREST parent that
        declares or re-exports it, never the distant declaring owner (operator
        ruling 2026-09-23), so workspace and standalone plans render one form.
        """
        candidate_packages: t.StrSequence = tuple(
            name for name in package_names if name and name != current_pkg
        )
        # ADR-018 p.1: the owner of a letter is the package whose own module
        # DECLARES it in its explicit __all__ (flext_core/result.py owns `r`).
        # Every generated initializer re-exports the letters it inherits, so
        # "the nearest parent whose init lists the name" would elect whichever
        # dependency sorts first — a tooling package re-exporting `r` made a
        # test package import it through flext_infra and cycle at runtime.
        for package_name in candidate_packages:
            if package_name == current_pkg:
                continue
            if alias_name in self._declared_alias_names_for_package(package_name):
                return f"{package_name}"
        for package_name in candidate_packages:
            if self._serves_facade_letter(package_name, alias_name, visited=set()):
                return f"{package_name}"
        return ""

    def _serves_facade_letter(
        self, package_name: str, alias_name: str, *, visited: set[str]
    ) -> bool:
        """Return whether a package declares a letter or re-exports a declarer's.

        The re-export chain follows facade parents for indexed packages and the
        published initializer for external ones, so a standalone plan reaches
        the declaring owner exactly like a workspace plan does, without
        consulting any dependency table or this run's stale output.
        """
        if package_name in visited:
            return False
        visited.add(package_name)
        if alias_name in self._declared_alias_names_for_package(package_name):
            return True
        return any(
            self._serves_facade_letter(source_package, alias_name, visited=visited)
            for source_package in self._reexport_sources(package_name, alias_name)
        )

    def _reexport_sources(self, package_name: str, alias_name: str) -> t.StrSequence:
        """Return the packages a package re-exports a name from.

        An indexed package is regenerated by this run, so its facade parents
        (declared sources) are the chain; only an external package's published
        initializer is read, through its absolute ``from X import`` statements.
        """
        indexed_dir = self.rope_workspace.workspace_index.package_dir_by_name.get(
            package_name
        )
        if indexed_dir is not None:
            return self._parent_packages(indexed_dir)
        package_dir = u.Infra.declared_package_dir(package_name)
        init_path = None if package_dir is None else package_dir / c.Infra.INIT_PY
        if init_path is None or not init_path.is_file():
            return ()
        return u.Infra.absolute_import_sources_source(
            init_path.read_text(encoding=c.Cli.ENCODING_DEFAULT), name=alias_name
        )

    def _declared_alias_names_for_package(self, package_name: str) -> frozenset[str]:
        """Return the facade letters a package's own modules declare in __all__.

        Only class aliases qualify (``u.Infra.facade_letter_names_source``):
        singleton instances and entry points such as ``cli``, ``infra``,
        ``main`` and ``docs_main`` belong to their declaring namespace root only.
        """
        cache_key = f"declared:{package_name}"
        cached = self._source_exports_cache.get(cache_key)
        if cached is not None:
            return cached
        # A parent outside the scan scope is read from the one package the
        # active environment declares (R32), so a standalone plan and a
        # workspace plan elect the same owner.
        package_dir = self.rope_workspace.workspace_index.package_dir_by_name.get(
            package_name
        ) or u.Infra.declared_package_dir(package_name)
        declared: set[str] = set()
        if package_dir is not None:
            for module_path in sorted(package_dir.glob("*.py")):
                if module_path.name == c.Infra.INIT_PY:
                    continue
                declared.update(
                    u.Infra.facade_letter_names_source(
                        module_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
                    )
                )
        names = frozenset(declared)
        self._source_exports_cache[cache_key] = names
        return names

    def _package_name_from_target(self, target: str) -> str:
        """Return the longest workspace package name matching the dotted target."""
        parts = tuple(part for part in target.split(".") if part)
        for size in range(len(parts), 0, -1):
            package_name = ".".join(parts[:size])
            if package_name in self.rope_workspace.workspace_index.package_dir_by_name:
                return package_name
        if not parts:
            return ""
        # Why (flext-27a9e.1, flext-b3xmn, R32): project-scoped Rope indexes
        # omit declared parents; u.Infra resolves the name in the declared
        # environment. "" is the typed answer for "not a package here".
        if u.Infra.declared_package_dir(parts[0]) is not None:
            return parts[0]
        return ""
