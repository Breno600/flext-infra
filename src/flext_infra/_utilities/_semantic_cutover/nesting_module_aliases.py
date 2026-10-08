"""Module-alias consumers of modules whose members move under one owner.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Callable
from typing import override

import libcst as cst
from libcst.metadata import MetadataWrapper, ParentNodeProvider

from flext_infra import m, t
from flext_infra._utilities import FlextInfraUtilitiesQualifiedNames


class FlextInfraUtilitiesSemanticCutoverNestingModuleAliases:
    """Find consumers that reach a nested module through a module binding.

    ``from pkg import module as alias`` followed by ``alias.member`` reads a
    member the owner now holds. Such a consumer imports the owner itself and
    reads ``Owner.member``; the module binding survives only while another
    use still needs the module object.
    """

    class _ModuleAliasScan(cst.CSTVisitor):
        """Record nested-module bindings and how one consumer uses them."""

        METADATA_DEPENDENCIES = (ParentNodeProvider,)

        def __init__(
            self,
            *,
            module_name: str,
            is_package_init: bool,
            bindings_by_module: t.MappingKV[str, t.StrMapping],
            classifiers: t.Triple[
                Callable[..., t.Pair[t.StrMapping, frozenset[str]]],
                Callable[..., t.StrMapping],
                Callable[..., bool | None],
            ],
        ) -> None:
            self.module_name = module_name
            self.is_package_init = is_package_init
            self.bindings_by_module = bindings_by_module
            (
                self.from_import_bindings,
                self.import_bindings,
                self.reads_moved_member,
            ) = classifiers
            self.aliases: t.MutableStrMapping = {}
            self.uses: t.MutableMappingKV[str, set[bool]] = {}
            self.owner_imports: set[str] = set()
            self.type_checking_depth = 0

        @staticmethod
        def _guards_type_checking(node: cst.If) -> bool:
            test = node.test
            name = test.attr if isinstance(test, cst.Attribute) else test
            return isinstance(name, cst.Name) and name.value == "TYPE_CHECKING"

        @override
        def visit_If(self, node: cst.If) -> None:
            self.type_checking_depth += self._guards_type_checking(node)

        @override
        def leave_If(self, original_node: cst.If) -> None:
            self.type_checking_depth -= self._guards_type_checking(original_node)

        @override
        def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
            aliases, owner_imports = self.from_import_bindings(
                node,
                module_name=self.module_name,
                is_package_init=self.is_package_init,
                bindings_by_module=self.bindings_by_module,
            )
            self.aliases.update(aliases)
            # An import that exists only for type checking binds nothing at
            # runtime, so it never stands in for the owner import.
            if not self.type_checking_depth:
                self.owner_imports.update(owner_imports)

        @override
        def visit_Import(self, node: cst.Import) -> None:
            self.aliases.update(
                self.import_bindings(node, self.bindings_by_module),
            )

        @override
        def visit_Name(self, node: cst.Name) -> None:
            module = self.aliases.get(node.value)
            if module is None:
                return
            use = self.reads_moved_member(
                node,
                self.get_metadata(ParentNodeProvider, node, None),
                self.bindings_by_module[module],
            )
            if use is not None:
                self.uses.setdefault(node.value, set()).add(use)

    @staticmethod
    def _resolved_relative(
        level: int,
        suffix: str,
        *,
        module_name: str,
        is_package_init: bool,
    ) -> str:
        """Resolve one relative module reference against the importing module.

        Returns:
            The absolute dotted module name, or an empty string past the root.

        """
        package_parts = module_name.split(".")
        if not is_package_init:
            package_parts = package_parts[:-1]
        ascend = level - 1
        if ascend > len(package_parts):
            return ""
        prefix = package_parts[: len(package_parts) - ascend]
        return ".".join((*prefix, suffix) if suffix else prefix)

    @classmethod
    def _imported_module(
        cls,
        node: cst.ImportFrom,
        *,
        module_name: str,
        is_package_init: bool,
    ) -> str:
        """Return the absolute module one ``from`` import reads.

        Returns:
            The absolute dotted module name.

        """
        suffix = FlextInfraUtilitiesQualifiedNames.dotted_name(node.module) or ""
        if not node.relative:
            return suffix
        return cls._resolved_relative(
            len(node.relative),
            suffix,
            module_name=module_name,
            is_package_init=is_package_init,
        )

    @staticmethod
    def _bound_name(imported: cst.ImportAlias) -> str:
        """Return the local name one import alias binds.

        Returns:
            The ``as`` name, else the imported dotted name.

        """
        if imported.asname is not None and isinstance(imported.asname.name, cst.Name):
            return imported.asname.name.value
        return FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name) or ""

    @classmethod
    def _from_import_bindings(
        cls,
        node: cst.ImportFrom,
        *,
        module_name: str,
        is_package_init: bool,
        bindings_by_module: t.MappingKV[str, t.StrMapping],
    ) -> t.Pair[t.StrMapping, frozenset[str]]:
        """Classify one ``from`` import against the nested modules.

        Returns:
            Module bindings it creates (local name to nested module), and the
            nested modules whose members or owner it already imports.

        """
        if isinstance(node.names, cst.ImportStar):
            return {}, frozenset()
        base = cls._imported_module(
            node,
            module_name=module_name,
            is_package_init=is_package_init,
        )
        bindings = bindings_by_module.get(base, {})
        known = frozenset(bindings) | frozenset(bindings.values())
        aliases: t.MutableStrMapping = {}
        owner_imports: set[str] = set()
        for imported in node.names:
            name = FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name) or ""
            if name in known:
                owner_imports.add(base)
            full = f"{base}.{name}" if base else name
            if full in bindings_by_module:
                aliases[cls._bound_name(imported)] = full
        return aliases, frozenset(owner_imports)

    @classmethod
    def _nested_import_bindings(
        cls,
        node: cst.Import,
        bindings_by_module: t.MappingKV[str, t.StrMapping],
    ) -> t.StrMapping:
        """Return the ``import a.b as x`` bindings of nested modules.

        Returns:
            Local name to nested module.

        """
        bound: t.MutableStrMapping = {}
        for imported in node.names:
            full = FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name) or ""
            if imported.asname is not None and full in bindings_by_module:
                bound[cls._bound_name(imported)] = full
        return bound

    @staticmethod
    def _reads_moved_member(
        node: cst.Name,
        parent: cst.CSTNode | None,
        members: t.StrMapping,
    ) -> bool | None:
        """Classify one use of a module binding.

        Returns:
            ``True`` for ``binding.<moved member>``, ``None`` for the binding's
            own spelling (import, ``as`` name, attribute name), ``False`` for a
            use that still needs the module object.

        """
        if FlextInfraUtilitiesQualifiedNames.rebinds_name_in_place(
            parent,
            node,
        ) or isinstance(parent, cst.AsName):
            return None
        return (
            isinstance(parent, cst.Attribute)
            and parent.value is node
            and parent.attr.value in members
        )

    @classmethod
    def _module_alias_scan(
        cls,
        source: str,
        *,
        module_name: str,
        is_package_init: bool,
        bindings_by_module: t.MappingKV[str, t.StrMapping],
    ) -> m.Infra.NestingModuleAliasScan:
        """Collect module bindings of nested modules and how they are used.

        Returns:
            Bound module per local name, names still needing the module object,
            names read through a moved member, and modules already importing
            their owner.

        """
        scan = cls._ModuleAliasScan(
            module_name=module_name,
            is_package_init=is_package_init,
            bindings_by_module=bindings_by_module,
            classifiers=(
                cls._from_import_bindings,
                cls._nested_import_bindings,
                cls._reads_moved_member,
            ),
        )
        MetadataWrapper(cst.parse_module(source)).visit(scan)
        return m.Infra.NestingModuleAliasScan(
            aliases=scan.aliases,
            residual=frozenset(
                name for name, uses in scan.uses.items() if False in uses
            ),
            read=frozenset(name for name, uses in scan.uses.items() if True in uses),
            owner_imports=frozenset(scan.owner_imports),
        )


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverNestingModuleAliases"]
