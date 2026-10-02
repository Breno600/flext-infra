"""Module-alias consumers of modules whose members move under one owner.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_infra import m
from flext_infra._utilities.qualified_names import FlextInfraUtilitiesQualifiedNames

if TYPE_CHECKING:
    import libcst as cst

    from flext_infra import t


class FlextInfraUtilitiesSemanticCutoverNestingModuleAliases:
    """Find consumers that reach a nested module through a module binding.

    ``from pkg import module as alias`` followed by ``alias.member`` reads a
    member the owner now holds. Such a consumer imports the owner itself and
    reads ``Owner.member``; the module binding survives only while another
    use still needs the module object.
    """

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
        import libcst as cst
        from libcst.metadata import MetadataWrapper, ParentNodeProvider

        resolver = cls

        class _ModuleAliasScan(cst.CSTVisitor):
            METADATA_DEPENDENCIES = (ParentNodeProvider,)

            def __init__(self) -> None:
                self.aliases: dict[str, str] = {}
                self.residual: set[str] = set()
                self.read: set[str] = set()
                self.owner_imports: set[str] = set()

            @staticmethod
            def _local(imported: cst.ImportAlias) -> str:
                if imported.asname is not None and isinstance(
                    imported.asname.name,
                    cst.Name,
                ):
                    return imported.asname.name.value
                return FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name) or ""

            @override
            def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
                if isinstance(node.names, cst.ImportStar):
                    return
                base = resolver._imported_module(
                    node,
                    module_name=module_name,
                    is_package_init=is_package_init,
                )
                bindings = bindings_by_module.get(base, {})
                for imported in node.names:
                    name = (
                        FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name)
                        or ""
                    )
                    if name in bindings or name in set(bindings.values()):
                        self.owner_imports.add(base)
                    full = f"{base}.{name}" if base else name
                    if full in bindings_by_module:
                        self.aliases[self._local(imported)] = full

            @override
            def visit_Import(self, node: cst.Import) -> None:
                for imported in node.names:
                    full = (
                        FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name)
                        or ""
                    )
                    if imported.asname is not None and full in bindings_by_module:
                        self.aliases[self._local(imported)] = full

            @override
            def visit_Name(self, node: cst.Name) -> None:
                module = self.aliases.get(node.value)
                if module is None:
                    return
                parent = self.get_metadata(ParentNodeProvider, node, None)
                if FlextInfraUtilitiesQualifiedNames.rebinds_name_in_place(
                    parent,
                    node,
                ) or isinstance(parent, cst.AsName):
                    return
                if (
                    isinstance(parent, cst.Attribute)
                    and parent.value is node
                    and parent.attr.value in bindings_by_module[module]
                ):
                    self.read.add(node.value)
                    return
                self.residual.add(node.value)

        scan = _ModuleAliasScan()
        MetadataWrapper(cst.parse_module(source)).visit(scan)
        return m.Infra.NestingModuleAliasScan(
            aliases=scan.aliases,
            residual=frozenset(scan.residual),
            read=frozenset(scan.read),
            owner_imports=frozenset(scan.owner_imports),
        )


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverNestingModuleAliases"]
