"""Prove an existing import is the requested facade through declared ancestry."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from libcst.metadata import QualifiedNameSource, Scope

from flext_infra import c, u

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from flext_infra import t


class FlextInfraRefactorImportFacades:
    """Reuse static facade discovery without importing dependency business code."""

    class _ModuleIndex[V](Mapping[str, V]):
        """Index only the modules an inheritance walk actually reads.

        Every binding or class identity is ``<module>.<name>``; a lookup
        indexes each source module prefixing the identity on first use, so
        proving one facade never parses unrelated dependency modules.
        """

        def __init__(
            self,
            sources: t.MappingKV[str, t.Pair[str, bool]],
            index: Callable[[t.MappingKV[str, t.Pair[str, bool]]], t.MappingKV[str, V]],
        ) -> None:
            self.sources = sources
            self.index = index
            self.indexed: set[str] = set()
            self.entries: t.MutableMappingKV[str, V] = {}

        def _load(self, identity: str) -> None:
            parts = identity.split(".")
            for size in range(1, len(parts) + 1):
                module = ".".join(parts[:size])
                if module in self.sources and module not in self.indexed:
                    self.indexed.add(module)
                    self.entries.update(self.index({module: self.sources[module]}))

        @override
        def __getitem__(self, identity: str) -> V:
            self._load(identity)
            return self.entries[identity]

        @override
        def __iter__(self) -> Iterator[str]:
            return iter(self.entries)

        @override
        def __len__(self) -> int:
            return len(self.entries)

    def __init__(self) -> None:
        self.identities: t.MutableMappingKV[tuple[str, str], bool] = {}

    def require_available(self, scope: Scope, alias: str) -> bool:
        """Reject lexical capture before introducing or reusing a facade name."""
        names = scope.get_qualified_names_for(alias)
        if len(names) > 1 or any(
            name.source is not QualifiedNameSource.IMPORT for name in names
        ):
            msg = f"import migration would capture existing alias {alias!r}"
            raise ValueError(msg)
        for name in names:
            identity = (name.name, alias)
            if identity not in self.identities:
                self.identities[identity] = self.accepts(*identity)
            if not self.identities[identity]:
                msg = (
                    f"import migration requires the declared facade, found {name.name}"
                )
                raise ValueError(msg)
        return bool(names)

    @classmethod
    def accepts(cls, qualified: str, alias: str) -> bool:
        """Require the canonical alias or a facade inheriting its declared owner."""
        expected = f"{c.Infra.PKG_CORE_UNDERSCORE}.{alias}"
        if qualified == expected:
            return True
        package, _, imported = qualified.rpartition(".")
        if imported != alias or not package:
            return False
        modules = cls._facade_sources(package, alias)
        owners = u.Infra.discover(cls._package_modules(modules))
        roots = {
            f"{c.Infra.PKG_CORE_UNDERSCORE}.{file.removesuffix('.py')}.{root}"
            for _tree, letter, root, file in owners.get(c.Infra.PKG_CORE_UNDERSCORE, ())
            if letter == alias
        }
        if len(roots) != 1:
            msg = f"canonical facade identity is not unique: {expected}"
            raise ValueError(msg)
        return (
            u.Infra.public_reference(
                owners=owners.get(package, ()),
                package=package,
                qualified=roots.pop(),
                bindings=cls._ModuleIndex(
                    modules, lambda source: u.Infra.declared_exports(source)[0]
                ),
                class_bases=cls._ModuleIndex(modules, u.Infra.class_bases),
            )
            == alias
        )

    @classmethod
    def _facade_sources(
        cls, package: str, alias: str
    ) -> t.MappingKV[str, t.Pair[str, bool]]:
        """Complete only the dependency ancestry of declared facade owners."""
        modules = u.Infra.source_modules(
            {},
            (
                f"from {package} import {alias}",
                f"from {c.Infra.PKG_CORE_UNDERSCORE} import {alias}",
            ),
        )
        inspected = {module.split(".", maxsplit=1)[0] for module in modules}
        while True:
            owners = u.Infra.discover(cls._package_modules(modules))
            dependencies: set[str] = set()
            for facade_owners in owners.values():
                for tree, _alias, _root, _file in facade_owners:
                    dependencies.update(cls._imported_packages(tree))
            dependencies.difference_update(inspected)
            if not dependencies:
                return modules
            inspected.update(dependencies)
            modules.update(
                u.Infra.source_modules(
                    {},
                    tuple(
                        f"from {dependency} import *"
                        for dependency in sorted(dependencies)
                    ),
                )
            )

    @staticmethod
    def _package_modules(
        modules: t.MappingKV[str, t.Pair[str, bool]],
    ) -> t.MappingKV[str, t.Pair[str, bool]]:
        """Select the direct package modules that may declare a facade letter."""
        return {
            module: source
            for module, source in modules.items()
            if module.count(".") == 1
        }

    @staticmethod
    def _imported_packages(tree: ast.Module) -> frozenset[str]:
        """Read imports in a facade declaration without evaluating the module."""
        return frozenset(
            node.module.split(".", maxsplit=1)[0]
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and not node.level and node.module
        )


__all__: list[str] = ["FlextInfraRefactorImportFacades"]
