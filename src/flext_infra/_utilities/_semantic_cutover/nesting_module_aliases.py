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

    @staticmethod
    def _bound_name(imported: cst.ImportAlias) -> str:
        """Return the local name one import alias binds.

        Returns:
            The ``as`` name, else the imported dotted name.

        """
        import libcst as cst

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
        import libcst as cst

        if isinstance(node.names, cst.ImportStar):
            return {}, frozenset()
        base = cls._imported_module(
            node,
            module_name=module_name,
            is_package_init=is_package_init,
        )
        bindings = bindings_by_module.get(base, {})
        known = frozenset(bindings) | frozenset(bindings.values())
        aliases: dict[str, str] = {}
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
    def _import_bindings(
        cls,
        node: cst.Import,
        bindings_by_module: t.MappingKV[str, t.StrMapping],
    ) -> t.StrMapping:
        """Return the ``import a.b as x`` bindings of nested modules.

        Returns:
            Local name to nested module.

        """
        return {
            cls._bound_name(imported): full
            for imported in node.names
            if imported.asname is not None
            and (full := FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name))
            in bindings_by_module
        }

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
        import libcst as cst

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
        import libcst as cst
        from libcst.metadata import MetadataWrapper, ParentNodeProvider

        resolver = cls

        class _ModuleAliasScan(cst.CSTVisitor):
            METADATA_DEPENDENCIES = (ParentNodeProvider,)

            def __init__(self) -> None:
                self.aliases: dict[str, str] = {}
                self.uses: dict[str, set[bool]] = {}
                self.owner_imports: set[str] = set()

            @override
            def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
                aliases, owner_imports = resolver._from_import_bindings(
                    node,
                    module_name=module_name,
                    is_package_init=is_package_init,
                    bindings_by_module=bindings_by_module,
                )
                self.aliases.update(aliases)
                self.owner_imports.update(owner_imports)

            @override
            def visit_Import(self, node: cst.Import) -> None:
                self.aliases.update(
                    resolver._import_bindings(node, bindings_by_module),
                )

            @override
            def visit_Name(self, node: cst.Name) -> None:
                module = self.aliases.get(node.value)
                if module is None:
                    return
                use = resolver._reads_moved_member(
                    node,
                    self.get_metadata(ParentNodeProvider, node, None),
                    bindings_by_module[module],
                )
                if use is not None:
                    self.uses.setdefault(node.value, set()).add(use)

        scan = _ModuleAliasScan()
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
