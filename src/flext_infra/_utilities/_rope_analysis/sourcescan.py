"""Source-level rope parsing, literal scanning, and reference extraction.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from typing import ClassVar

from flext_infra import t
from flext_infra._utilities._rope_analysis.asthelpers import (
    FlextInfraUtilitiesRopeAnalysisAstHelpers,
)


class FlextInfraUtilitiesRopeAnalysisSourceScan:
    """Source-level rope parsing, literal scanning, and reference extraction.

    Every ``*_source`` reader parses the module with :mod:`ast` and reads the
    node it needs; source that does not parse raises its ``SyntaxError``.
    """

    _INSTALL_LAZY_IMPORTS_ARG_INDEX: ClassVar[int] = 2

    @staticmethod
    def literal_string_sequence(node: t.Infra.RopeAstNode | None) -> t.StrSequence:
        """Return string entries from a parsed literal sequence node.

        Returns:
            String entries from a parsed literal sequence node.

        """
        if node is None:
            return ()
        if FlextInfraUtilitiesRopeAnalysisAstHelpers.node_kind(node) not in {
            "List",
            "Tuple",
            "Set",
        }:
            return ()
        values: list[str] = []
        for element in getattr(node, "elts", ()) or ():
            if not FlextInfraUtilitiesRopeAnalysisAstHelpers.ast_node(element):
                return ()
            element_kind = FlextInfraUtilitiesRopeAnalysisAstHelpers.node_kind(element)
            if element_kind == "Constant":
                value = getattr(element, "value", None)
            elif element_kind == "Str":
                value = getattr(element, "s", None)
            else:
                return ()
            if not isinstance(value, str):
                return ()
            values.append(value)
        return tuple(values)

    @staticmethod
    def _top_level_value(source: str, name: str) -> ast.expr | None:
        """Return the value node assigned to one top-level symbol.

        Parsing the module keeps assignments embedded in string literals (for
        example source templates inside tests) from reading as real bindings.

        Returns:
            The value node assigned to one top-level symbol.

        """
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign):
                targets: t.SequenceOf[ast.expr] = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = (node.target,)
            else:
                continue
            if any(
                isinstance(target, ast.Name) and target.id == name for target in targets
            ):
                return node.value
        return None

    @staticmethod
    def _sequence_constructor_ref(value: ast.expr | None) -> str:
        """Return the name a value binds directly or wraps in one sequence constructor.

        Returns:
            The name a value binds directly or wraps in one sequence constructor.

        """
        if isinstance(value, ast.Name):
            return value.id
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id in {"tuple", "list", "frozenset", "set"}
            and len(value.args) == 1
            and not value.keywords
            and isinstance(value.args[0], ast.Name)
        ):
            return value.args[0].id
        return ""

    @staticmethod
    def module_assignment_strings_source(source: str, name: str) -> t.StrSequence:
        """Collect strings from a literal module-level assignment.

        Returns:
            The resulting ``t.StrSequence``.

        """
        scan = FlextInfraUtilitiesRopeAnalysisSourceScan
        value = scan._top_level_value(source, name)
        values = scan.literal_string_sequence(value)
        if values:
            return values
        # Generated roots use ``__all__ = tuple(_PUBLIC_EXPORTS)``; follow the
        # bound name so docs validate matches the live lazy-init ABI.
        nested_name = scan._sequence_constructor_ref(value)
        if not nested_name or nested_name == name:
            return ()
        return scan.module_assignment_strings_source(source, nested_name)

    @staticmethod
    def module_mapping_assignment_source(
        source: str,
        name: str,
    ) -> t.Pair[t.VariadicTuple[t.Pair[str, t.StrSequence]], t.StrSequence]:
        """Collect mapping entries and referenced names from an assignment.

        Returns:
            The resulting ``t.Pair[t.VariadicTuple[t.Pair[str, t.StrSequence]],
                t.StrSequence]``.

        """
        scan = FlextInfraUtilitiesRopeAnalysisSourceScan
        return scan.mapping_entries_refs(scan._top_level_value(source, name))

    @staticmethod
    def mapping_entries_refs(
        node: t.Infra.RopeAstNode | None,
    ) -> t.Pair[t.VariadicTuple[t.Pair[str, t.StrSequence]], t.StrSequence]:
        """Return literal mapping entries plus variable references.

        Returns:
            Literal mapping entries plus variable references.

        """
        if node is None:
            return ((), ())
        kind = FlextInfraUtilitiesRopeAnalysisAstHelpers.node_kind(node)
        if kind == "Name":
            node_name = FlextInfraUtilitiesRopeAnalysisAstHelpers.name_of(node)
            return ((), (node_name,) if node_name else ())
        if kind == "Dict":
            return FlextInfraUtilitiesRopeAnalysisSourceScan._dict_entries_refs(node)
        if kind != "Call":
            return ((), ())
        func = getattr(node, "func", None)
        function_name = (
            FlextInfraUtilitiesRopeAnalysisAstHelpers.name_of(func)
            if func is not None
            and FlextInfraUtilitiesRopeAnalysisAstHelpers.ast_node(func)
            else ""
        )
        args = getattr(node, "args", ()) or ()
        if function_name in {"MappingProxyType", "build_lazy_import_map"} and args:
            first_arg = args[0]
            if FlextInfraUtilitiesRopeAnalysisAstHelpers.ast_node(first_arg):
                return FlextInfraUtilitiesRopeAnalysisSourceScan.mapping_entries_refs(
                    first_arg,
                )
        if function_name != "merge_lazy_imports":
            return ((), ())
        entries: list[t.Pair[str, t.StrSequence]] = []
        refs: list[str] = []
        for argument in args:
            if not FlextInfraUtilitiesRopeAnalysisAstHelpers.ast_node(argument):
                continue
            next_entries, next_refs = (
                FlextInfraUtilitiesRopeAnalysisSourceScan.mapping_entries_refs(argument)
            )
            entries.extend(next_entries)
            refs.extend(next_refs)
        return (tuple(entries), tuple(dict.fromkeys(refs)))

    @staticmethod
    def _dict_entries_refs(
        node: t.Infra.RopeAstNode,
    ) -> t.Pair[t.VariadicTuple[t.Pair[str, t.StrSequence]], t.StrSequence]:
        """Return string-sequence dict entries and unpack references.

        Returns:
            String-sequence dict entries and unpack references.

        """
        keys = getattr(node, "keys", ()) or ()
        values = getattr(node, "values", ()) or ()
        entries: list[t.Pair[str, t.StrSequence]] = []
        refs: list[str] = []
        for key_node, value_node in zip(keys, values, strict=False):
            if key_node is None:
                if FlextInfraUtilitiesRopeAnalysisAstHelpers.ast_node(value_node):
                    ref_name = FlextInfraUtilitiesRopeAnalysisAstHelpers.name_of(
                        value_node,
                    )
                    if ref_name:
                        refs.append(ref_name)
                continue
            if not FlextInfraUtilitiesRopeAnalysisAstHelpers.ast_node(key_node):
                continue
            key_value = getattr(key_node, "value", None)
            if not isinstance(key_value, str):
                continue
            if FlextInfraUtilitiesRopeAnalysisAstHelpers.ast_node(value_node):
                value_strings = (
                    FlextInfraUtilitiesRopeAnalysisSourceScan.literal_string_sequence(
                        value_node,
                    )
                )
            else:
                value_strings = ()
            if value_strings:
                entries.append((key_value, value_strings))
        return (tuple(entries), tuple(dict.fromkeys(refs)))

    @staticmethod
    def relative_import_module_name(
        *,
        current_module: str,
        imported_module: str,
        level: int,
        package_module: bool,
    ) -> str:
        """Resolve a parsed ``from`` import module into an absolute module name.

        Returns:
            The resulting ``str``.

        """
        if level == 0:
            return imported_module
        current_parts = current_module.split(".")
        base_count = len(current_parts) - level + (1 if package_module else 0)
        base = ".".join(current_parts[: max(base_count, 0)])
        return ".".join(part for part in (base, imported_module) if part)

    @classmethod
    def imported_symbol_binding_source(
        cls,
        source: str,
        *,
        current_module: str,
        symbol_name: str,
        package_module: bool,
    ) -> t.Pair[str, str]:
        """Return ``(module, original_name)`` for one imported symbol binding.

        Returns:
            ``(module, original_name)`` for one imported symbol binding.

        """
        imports = sorted(
            (
                node
                for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.ImportFrom)
            ),
            key=lambda node: (node.lineno, node.col_offset),
        )
        for node in imports:
            for alias in node.names:
                if (alias.asname or alias.name) != symbol_name:
                    continue
                module_name = cls.relative_import_module_name(
                    current_module=current_module,
                    imported_module=node.module or "",
                    level=node.level,
                    package_module=package_module,
                )
                return (module_name, alias.name)
        return ("", "")

    @staticmethod
    def _top_level_class(source: str, class_name: str) -> ast.ClassDef | None:
        """Return the top-level class statement named ``class_name``.

        Returns:
            The top-level class statement named ``class_name``.

        """
        for node in ast.parse(source).body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node
        return None

    @staticmethod
    def class_bases_source(source: str, class_name: str) -> t.StrSequence:
        """Return declared base names for one class in source.

        Returns:
            Declared base names for one class in source.

        """
        node = FlextInfraUtilitiesRopeAnalysisSourceScan._top_level_class(
            source,
            class_name,
        )
        if node is None:
            return ()
        return tuple(
            base_name
            for base in node.bases
            if (base_name := FlextInfraUtilitiesRopeAnalysisAstHelpers.name_of(base))
        )

    @staticmethod
    def class_declared_source(source: str, class_name: str) -> bool:
        """Return whether one class is declared at the top level of source.

        Returns:
            Whether one class is declared at the top level of source.

        """
        return (
            FlextInfraUtilitiesRopeAnalysisSourceScan._top_level_class(
                source,
                class_name,
            )
            is not None
        )

    @staticmethod
    def _first_call(source: str, function_name: str) -> ast.Call | None:
        """Return the first call, in source order, whose callee is ``function_name``.

        Returns:
            The first call, in source order, whose callee is ``function_name``.

        """
        calls = sorted(
            (
                node
                for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.Call)
                and FlextInfraUtilitiesRopeAnalysisAstHelpers.name_of(node.func)
                == function_name
            ),
            key=lambda node: (node.lineno, node.col_offset),
        )
        return calls[0] if calls else None

    @staticmethod
    def _keyword_value(call: ast.Call | None, keyword: str) -> ast.expr | None:
        """Return one keyword argument value of a call.

        Returns:
            One keyword argument value of a call.

        """
        if call is None:
            return None
        return next((item.value for item in call.keywords if item.arg == keyword), None)

    @staticmethod
    def lazy_public_exports_source(source: str) -> t.Pair[t.StrSequence, str]:
        """Return lazy-loader public exports or the local symbol holding them.

        Returns:
            Lazy-loader public exports or the local symbol holding them.

        """
        scan = FlextInfraUtilitiesRopeAnalysisSourceScan
        public_exports = scan._keyword_value(
            scan._first_call(source, "install_lazy_exports"),
            "public_exports",
        )
        if public_exports is None:
            return ((), "")
        values = scan.literal_string_sequence(public_exports)
        if values:
            return (values, "")
        return ((), FlextInfraUtilitiesRopeAnalysisAstHelpers.name_of(public_exports))

    @staticmethod
    def lazy_imports_name_source(source: str) -> str:
        """Return the local symbol passed as the lazy import map.

        Returns:
            The local symbol passed as the lazy import map.

        """
        scan = FlextInfraUtilitiesRopeAnalysisSourceScan
        call = scan._first_call(source, "install_lazy_exports")
        if call is None:
            return ""
        if len(call.args) > scan._INSTALL_LAZY_IMPORTS_ARG_INDEX:
            return FlextInfraUtilitiesRopeAnalysisAstHelpers.name_of(
                call.args[scan._INSTALL_LAZY_IMPORTS_ARG_INDEX],
            )
        keyword_value = scan._keyword_value(call, "lazy_imports")
        if keyword_value is None:
            return ""
        return FlextInfraUtilitiesRopeAnalysisAstHelpers.name_of(keyword_value)

    @staticmethod
    def export_target_modules_source(
        source: str,
        package_name: str,
        exports: t.StrSequence,
    ) -> MutableMapping[str, str]:
        """Map exports → defining module via rope's parsed-source import table.

        Returns:
            The resulting ``MutableMapping[str, str]``.

        """
        export_names = {name for name in exports if name}
        target_map: MutableMapping[str, str] = dict.fromkeys(export_names, package_name)
        pymodule = FlextInfraUtilitiesRopeAnalysisAstHelpers.parse_string_module(source)
        module_ast = pymodule.get_ast()
        for node in FlextInfraUtilitiesRopeAnalysisAstHelpers.walk_ast_nodes(
            module_ast,
        ):
            kind = FlextInfraUtilitiesRopeAnalysisAstHelpers.node_kind(node)
            if kind == "ImportFrom":
                module_name = getattr(node, "module", "") or ""
                names = getattr(node, "names", []) or []
                for alias in names:
                    local = getattr(alias, "asname", None) or getattr(alias, "name", "")
                    if isinstance(local, str) and local in export_names and module_name:
                        target_map[local] = module_name
            elif kind == "Import":
                names = getattr(node, "names", []) or []
                for alias in names:
                    raw_name = getattr(alias, "name", "") or ""
                    local = getattr(alias, "asname", None) or raw_name.partition(".")[0]
                    if isinstance(local, str) and local in export_names and raw_name:
                        module_name = (
                            raw_name.rsplit(".", maxsplit=1)[0]
                            if "." in raw_name
                            else raw_name
                        )
                        target_map[local] = module_name
        return target_map
