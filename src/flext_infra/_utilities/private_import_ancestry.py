"""Static lexical inheritance discovery for public facade cutover.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from importlib.util import resolve_name

from flext_infra import t


class FlextInfraUtilitiesPrivateImportAncestry:
    """Canonical namespace owner."""

    class _ClassBaseCollector:
        """Collect one module's class bases with scope-aware import bindings."""

        def __init__(self, *, module: str, package: str) -> None:
            self._module = module
            self._package = package
            self.bases: t.MutableMappingKV[str, t.VariadicTuple[str]] = {}
            self.module_names: t.MutableStrMapping = {}

        def collect_root(self, statements: t.SequenceOf[ast.stmt]) -> None:
            """Walk the module body, seeding the module-level scope."""
            self.collect(statements, scope=self._module, names=self.module_names)

        def collect(
            self,
            statements: t.SequenceOf[ast.stmt],
            *,
            scope: str,
            names: t.MutableStrMapping,
        ) -> None:
            """Index bases and scope bindings for one statement suite."""
            for node in statements:
                if isinstance(node, ast.ImportFrom) and node.module:
                    self._bind_import_from(names, node)
                elif isinstance(node, ast.Import):
                    self._bind_import(names, node)
                elif isinstance(node, ast.ClassDef):
                    self._collect_class(node, scope=scope, names=names)
                elif isinstance(node, ast.Assign | ast.AnnAssign):
                    self._bind_assignment(node, scope=scope, names=names)

        def _reference(self, node: ast.expr, names: t.MutableStrMapping) -> str:
            expression = ast.unparse(
                node.value if isinstance(node, ast.Subscript) else node,
            )
            root, separator, suffix = expression.partition(".")
            return names.get(root, f"{self._module}.{root}") + (
                f".{suffix}" if separator else ""
            )

        def _bind_import_from(
            self,
            names: t.MutableStrMapping,
            node: ast.ImportFrom,
        ) -> None:
            imported = (
                resolve_name(f"{'.' * node.level}{node.module}", self._package)
                if node.level
                else node.module
            )
            for alias in node.names:
                names[alias.asname or alias.name] = f"{imported}.{alias.name}"

        @staticmethod
        def _bind_import(
            names: t.MutableStrMapping,
            node: ast.Import,
        ) -> None:
            for alias in node.names:
                names[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0]
                )

        def _collect_class(
            self,
            node: ast.ClassDef,
            *,
            scope: str,
            names: t.MutableStrMapping,
        ) -> None:
            identity = f"{scope}.{node.name}"
            self.bases[identity] = tuple(
                self._reference(base, names)
                for base in node.bases
                if isinstance(
                    base,
                    ast.Name | ast.Attribute | ast.Subscript,
                )
            )
            # Bases see the declaration scope; class bodies do not close over an
            # enclosing class's local namespace.
            self.collect(
                node.body,
                scope=identity,
                names=dict(self.module_names),
            )
            names[node.name] = identity

        def _bind_assignment(
            self,
            node: ast.Assign | ast.AnnAssign,
            *,
            scope: str,
            names: t.MutableStrMapping,
        ) -> None:
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    names[target.id] = (
                        self._reference(value, names)
                        if isinstance(value, ast.Name | ast.Attribute)
                        else f"{scope}.{target.id}"
                    )

    class FlextInfraUtilitiesPrivateImportAncestry:
        """Resolve bases using bindings present when each class is declared."""

        @staticmethod
        def class_bases(
            sources: t.MappingKV[str, t.Pair[str, bool]],
        ) -> t.MappingKV[str, t.VariadicTuple[str]]:
            """Index static class ancestry, including private intermediate owners.

            Returns:
                The resulting ``t.MappingKV[str, t.VariadicTuple[str]]``.

            """
            bases: t.MutableMappingKV[str, t.VariadicTuple[str]] = {}
            for module, (source, is_package) in sources.items():
                tree = ast.parse(source, filename=module)
                package = module if is_package else module.rpartition(".")[0]
                collector = (
                    FlextInfraUtilitiesPrivateImportAncestry._ClassBaseCollector(
                        module=module,
                        package=package,
                    )
                )
                collector.collect_root(tree.body)
                bases.update(collector.bases)
            return bases


# The flat module-level re-export: the package lazy map and the internal
# from-import contract resolve this name at module scope (the S6 nesting
# moved the class inside the family facade).
__all__: list[str] = ["FlextInfraUtilitiesPrivateImportAncestry"]
