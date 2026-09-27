"""Prove an existing import is the requested facade through declared ancestry."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from libcst.metadata import QualifiedNameSource, Scope

from flext_infra import c, u

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraRefactorImportFacades:
    """Reuse static facade discovery without importing dependency business code."""

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
        owners = u.Infra.discover(modules)
        bindings, _exports = u.Infra.declared_exports(modules)
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
                bindings=bindings,
                class_bases=u.Infra.class_bases(modules),
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
            owners = u.Infra.discover(modules)
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
    def _imported_packages(tree: ast.Module) -> frozenset[str]:
        """Read imports in a facade declaration without evaluating the module."""
        return frozenset(
            node.module.split(".", maxsplit=1)[0]
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and not node.level and node.module
        )


__all__: list[str] = ["FlextInfraRefactorImportFacades"]
