"""Source-level rope parsing, literal scanning, and reference extraction."""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from typing import TYPE_CHECKING, ClassVar

from flext_infra import t

if TYPE_CHECKING:
    from collections.abc import Iterator


from .asthelpers import FlextInfraUtilitiesRopeAnalysisAstHelpers


class FlextInfraUtilitiesRopeAnalysisSourceScan:
    """Source-level rope parsing, literal scanning, and reference extraction."""

    _INSTALL_LAZY_IMPORTS_ARG_INDEX: ClassVar[int] = 2

    _STRING_LITERAL_MIN_LENGTH: ClassVar[int] = 2

    _TRIPLE_QUOTE_LENGTH: ClassVar[int] = 3

    _IMPORT_ALIAS_AS_PARTS: ClassVar[int] = 3

    @staticmethod
    def literal_string_sequence(node: t.Infra.RopeAstNode | None) -> t.StrSequence:
        """Return string entries from a parsed literal sequence node."""
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
            if not FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(element):
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
    def _sequence_constructor_ref_source(source: str) -> str:
        """Return the name wrapped by ``tuple``/``list``/``set`` or a bare name."""
        text = source.strip()
        if not text:
            return ""
        if text.isidentifier():
            return text
        for constructor in ("tuple", "list", "frozenset", "set"):
            prefix = f"{constructor}("
            if not text.startswith(prefix) or not text.endswith(")"):
                continue
            inner = text[len(prefix) : -1].strip()
            if inner.isidentifier():
                return inner
        return ""

    @staticmethod
    def module_assignment_strings_source(source: str, name: str) -> t.StrSequence:
        """Collect strings from a literal module-level assignment."""
        value_source = (
            FlextInfraUtilitiesRopeAnalysisSourceScan._assignment_value_source(
                source, name
            )
        )
        values = (
            FlextInfraUtilitiesRopeAnalysisSourceScan._literal_string_sequence_source(
                value_source
            )
        )
        if values:
            return values
        # Generated roots use ``__all__ = tuple(_PUBLIC_EXPORTS)``; follow the
        # bound name so docs validate matches the live lazy-init ABI.
        nested_name = (
            FlextInfraUtilitiesRopeAnalysisSourceScan._sequence_constructor_ref_source(
                value_source
            )
        )
        if not nested_name or nested_name == name:
            return ()
        return (
            FlextInfraUtilitiesRopeAnalysisSourceScan.module_assignment_strings_source(
                source, nested_name
            )
        )

    @staticmethod
    def module_mapping_assignment_source(
        source: str, name: str
    ) -> t.Pair[t.VariadicTuple[t.Pair[str, t.StrSequence]], t.StrSequence]:
        """Collect mapping entries and referenced names from an assignment."""
        value_source = (
            FlextInfraUtilitiesRopeAnalysisSourceScan._assignment_value_source(
                source, name
            )
        )
        return FlextInfraUtilitiesRopeAnalysisSourceScan._mapping_entries_refs_source(
            value_source
        )

    @staticmethod
    def mapping_entries_refs(
        node: t.Infra.RopeAstNode | None,
    ) -> t.Pair[t.VariadicTuple[t.Pair[str, t.StrSequence]], t.StrSequence]:
        """Return literal mapping entries plus variable references."""
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
            and FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(func)
            else ""
        )
        args = getattr(node, "args", ()) or ()
        if function_name in {"MappingProxyType", "build_lazy_import_map"} and args:
            first_arg = args[0]
            if FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(first_arg):
                return FlextInfraUtilitiesRopeAnalysisSourceScan.mapping_entries_refs(
                    first_arg
                )
        if function_name != "merge_lazy_imports":
            return ((), ())
        entries: list[t.Pair[str, t.StrSequence]] = []
        refs: list[str] = []
        for argument in args:
            if not FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(argument):
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
        """Return string-sequence dict entries and unpack references."""
        keys = getattr(node, "keys", ()) or ()
        values = getattr(node, "values", ()) or ()
        entries: list[t.Pair[str, t.StrSequence]] = []
        refs: list[str] = []
        for key_node, value_node in zip(keys, values, strict=False):
            if key_node is None:
                if FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(value_node):
                    ref_name = FlextInfraUtilitiesRopeAnalysisAstHelpers.name_of(
                        value_node
                    )
                    if ref_name:
                        refs.append(ref_name)
                continue
            if not FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(key_node):
                continue
            key_value = getattr(key_node, "value", None)
            if not isinstance(key_value, str):
                continue
            if FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(value_node):
                value_strings = (
                    FlextInfraUtilitiesRopeAnalysisSourceScan.literal_string_sequence(
                        value_node
                    )
                )
            else:
                value_strings = ()
            if value_strings:
                entries.append((key_value, value_strings))
        return (tuple(entries), tuple(dict.fromkeys(refs)))

    @staticmethod
    def relative_import_module_name(
        *, current_module: str, imported_module: str, level: int, package_module: bool
    ) -> str:
        """Resolve a parsed ``from`` import module into an absolute module name."""
        if level == 0:
            return imported_module
        current_parts = current_module.split(".")
        base_count = len(current_parts) - level + (1 if package_module else 0)
        base = ".".join(current_parts[: max(base_count, 0)])
        return ".".join(part for part in (base, imported_module) if part)

    @staticmethod
    def imported_symbol_binding_source(
        source: str, *, current_module: str, symbol_name: str, package_module: bool
    ) -> t.Pair[str, str]:
        """Return ``(module, original_name)`` for one imported symbol binding."""
        for (
            module_source,
            level,
            original_name,
            bound_name,
        ) in FlextInfraUtilitiesRopeAnalysisSourceScan._from_import_bindings_source(
            source
        ):
            if bound_name != symbol_name:
                continue
            module_name = (
                FlextInfraUtilitiesRopeAnalysisSourceScan.relative_import_module_name(
                    current_module=current_module,
                    imported_module=module_source,
                    level=level,
                    package_module=package_module,
                )
            )
            return (module_name, original_name or symbol_name)
        return ("", "")

    @staticmethod
    def class_bases_source(source: str, class_name: str) -> t.StrSequence:
        """Return declared base names for one class in source."""
        class_source = FlextInfraUtilitiesRopeAnalysisSourceScan._class_header_source(
            source, class_name
        )
        if not class_source:
            return ()
        open_index = class_source.find("(")
        close_index = class_source.rfind(")")
        if open_index < 0 or close_index <= open_index:
            return ()
        bases_source = class_source[open_index + 1 : close_index]
        return tuple(
            base_name
            for base_name in (
                FlextInfraUtilitiesRopeAnalysisSourceScan._symbol_name_source(item)
                for item in FlextInfraUtilitiesRopeAnalysisSourceScan._split_top_level_commas(
                    bases_source
                )
            )
            if base_name
        )

    @staticmethod
    def class_declared_source(source: str, class_name: str) -> bool:
        """Return whether one class is declared in source."""
        return bool(
            FlextInfraUtilitiesRopeAnalysisSourceScan._class_header_source(
                source, class_name
            )
        )

    @staticmethod
    def lazy_public_exports_source(source: str) -> t.Pair[t.StrSequence, str]:
        """Return lazy-loader public exports or the local symbol holding them."""
        call_args = FlextInfraUtilitiesRopeAnalysisSourceScan._call_args_source(
            source, "install_lazy_exports"
        )
        public_exports = (
            FlextInfraUtilitiesRopeAnalysisSourceScan._keyword_value_source(
                call_args, "public_exports"
            )
        )
        if public_exports:
            values = FlextInfraUtilitiesRopeAnalysisSourceScan._literal_string_sequence_source(
                public_exports
            )
            if values:
                return (values, "")
            return (
                (),
                FlextInfraUtilitiesRopeAnalysisSourceScan._symbol_name_source(
                    public_exports
                ),
            )
        return ((), "")

    @staticmethod
    def lazy_imports_name_source(source: str) -> str:
        """Return the local symbol passed as the lazy import map."""
        call_args = FlextInfraUtilitiesRopeAnalysisSourceScan._call_args_source(
            source, "install_lazy_exports"
        )
        if (
            len(call_args)
            > FlextInfraUtilitiesRopeAnalysisSourceScan._INSTALL_LAZY_IMPORTS_ARG_INDEX
        ):
            return FlextInfraUtilitiesRopeAnalysisSourceScan._symbol_name_source(
                call_args[
                    FlextInfraUtilitiesRopeAnalysisSourceScan._INSTALL_LAZY_IMPORTS_ARG_INDEX
                ]
            )
        keyword_value = FlextInfraUtilitiesRopeAnalysisSourceScan._keyword_value_source(
            call_args, "lazy_imports"
        )
        if keyword_value:
            return FlextInfraUtilitiesRopeAnalysisSourceScan._symbol_name_source(
                keyword_value
            )
        return ""

    @staticmethod
    def _assignment_value_source(source: str, name: str) -> str:
        """Return the source value assigned to one top-level symbol.

        Parses the module AST so assignments appearing inside string literals
        (for example source templates embedded in tests) are never mistaken for
        real top-level bindings.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return ""
        for node in tree.body:
            value: ast.expr | None
            if isinstance(node, ast.Assign):
                targets: list[ast.expr] = list(node.targets)
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
                value = node.value
            else:
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == name for target in targets
            ):
                continue
            if value is None:
                return ""
            return ast.get_source_segment(source, value) or ""
        return ""

    @staticmethod
    def _collect_statement(lines: t.StrSequence, start_index: int) -> str:
        """Collect a balanced Python statement starting at ``start_index``."""
        collected: list[str] = []
        depth = 0
        for line in lines[start_index:]:
            collected.append(line)
            depth += FlextInfraUtilitiesRopeAnalysisSourceScan._bracket_depth_delta(
                line
            )
            if depth <= 0:
                break
        return "\n".join(collected)

    @staticmethod
    def _unquoted_characters(source: str, start: int = 0) -> Iterator[t.Pair[int, str]]:
        """Yield ``(index, character)`` for every character outside a string literal.

        Single owner of the quote/escape state machine every top-level source
        scanner in this module needs; each caller keeps only its own bracket
        depth bookkeeping.
        """
        quote = ""
        escaped = False
        for index in range(start, len(source)):
            char = source[index]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                continue
            if char in {"'", '"'}:
                quote = char
                continue
            yield index, char

    @staticmethod
    def _bracket_depth_delta(source: str) -> int:
        """Return bracket nesting delta for one source line."""
        depth = 0
        for (
            _index,
            char,
        ) in FlextInfraUtilitiesRopeAnalysisSourceScan._unquoted_characters(source):
            if char == "#":
                break
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
        return depth

    @staticmethod
    def _split_top_level_commas(source: str) -> t.StrSequence:
        """Split one source fragment on commas outside nested delimiters."""
        parts: list[str] = []
        start = 0
        depth = 0
        for (
            index,
            char,
        ) in FlextInfraUtilitiesRopeAnalysisSourceScan._unquoted_characters(source):
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            elif char == "," and depth == 0:
                item = source[start:index].strip()
                if item:
                    parts.append(item)
                start = index + 1
        tail = source[start:].strip()
        if tail:
            parts.append(tail)
        return tuple(parts)

    @staticmethod
    def _top_level_partition(source: str, separator: str) -> t.Triple[str, str, str]:
        """Partition one source fragment at a top-level separator."""
        depth = 0
        for (
            index,
            char,
        ) in FlextInfraUtilitiesRopeAnalysisSourceScan._unquoted_characters(source):
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            elif char == separator and depth == 0:
                return (source[:index], separator, source[index + 1 :])
        return (source, "", "")

    @staticmethod
    def _literal_string_source(source: str) -> str:
        """Return the value of a simple string literal source fragment."""
        text = source.strip()
        while text and text[0].isalpha() and len(text) > 1 and text[1] in {"'", '"'}:
            text = text[1:]
        if (
            len(text)
            < FlextInfraUtilitiesRopeAnalysisSourceScan._STRING_LITERAL_MIN_LENGTH
            or text[0] not in {"'", '"'}
        ):
            return ""
        quote = text[0]
        triple_quote = (
            quote * FlextInfraUtilitiesRopeAnalysisSourceScan._TRIPLE_QUOTE_LENGTH
        )
        if text.startswith(triple_quote):
            end = text.find(
                triple_quote,
                FlextInfraUtilitiesRopeAnalysisSourceScan._TRIPLE_QUOTE_LENGTH,
            )
            return (
                text[
                    FlextInfraUtilitiesRopeAnalysisSourceScan._TRIPLE_QUOTE_LENGTH : end
                ]
                if end >= FlextInfraUtilitiesRopeAnalysisSourceScan._TRIPLE_QUOTE_LENGTH
                else ""
            )
        end = 1
        escaped = False
        while end < len(text):
            char = text[end]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                break
            end += 1
        return text[1:end]

    @staticmethod
    def _literal_string_sequence_source(source: str) -> t.StrSequence:
        """Return string entries from a literal sequence source fragment."""
        text = source.strip()
        if not text or text[0] not in "[{(":
            return ()
        close = {"[": "]", "{": "}", "(": ")"}[text[0]]
        if not text.endswith(close):
            return ()
        inner = text[1:-1]
        values: list[str] = []
        for item in FlextInfraUtilitiesRopeAnalysisSourceScan._split_top_level_commas(
            inner
        ):
            value = FlextInfraUtilitiesRopeAnalysisSourceScan._literal_string_source(
                item
            )
            if not value:
                return ()
            values.append(value)
        return tuple(values)

    @staticmethod
    def _call_args_source(source: str, function_name: str) -> t.StrSequence:
        """Return top-level argument sources for the first matching call."""
        search_from = 0
        while True:
            name_index = source.find(function_name, search_from)
            if name_index < 0:
                return ()
            open_index = source.find("(", name_index + len(function_name))
            if open_index < 0:
                return ()
            between = source[name_index + len(function_name) : open_index].strip()
            if between:
                search_from = name_index + len(function_name)
                continue
            close_index = (
                FlextInfraUtilitiesRopeAnalysisSourceScan._matching_close_index(
                    source, open_index
                )
            )
            if close_index < 0:
                return ()
            return FlextInfraUtilitiesRopeAnalysisSourceScan._split_top_level_commas(
                source[open_index + 1 : close_index]
            )

    @staticmethod
    def _matching_close_index(source: str, open_index: int) -> int:
        """Return the index of the closing delimiter matching ``open_index``."""
        open_char = source[open_index]
        close_char = {"(": ")", "[": "]", "{": "}"}[open_char]
        depth = 0
        for (
            index,
            char,
        ) in FlextInfraUtilitiesRopeAnalysisSourceScan._unquoted_characters(
            source, open_index
        ):
            if char == open_char:
                depth += 1
            elif char == close_char:
                depth -= 1
                if depth == 0:
                    return index
        return -1

    @staticmethod
    def _keyword_value_source(args: t.StrSequence, keyword: str) -> str:
        """Return a keyword argument value source from split call args."""
        prefix = f"{keyword}="
        # NOTE (multi-agent, flext-f8vk / kimi): args is t.StrSequence
        # (SequenceOf[str]); the old isinstance guard was dead code.
        for arg in args:
            text = arg.strip()
            if text.startswith(prefix):
                value: str = t.Infra.STR_ADAPTER.validate_python(
                    text[len(prefix) :].strip()
                )
                return value
        return ""

    @staticmethod
    def _mapping_entries_refs_source(
        source: str,
    ) -> t.Pair[t.VariadicTuple[t.Pair[str, t.StrSequence]], t.StrSequence]:
        """Return lazy-map entries and referenced mapping symbols from source."""
        text = source.strip()
        if not text:
            return ((), ())
        if FlextInfraUtilitiesRopeAnalysisSourceScan._is_symbol_source(text):
            return ((), (text,))
        call_name = FlextInfraUtilitiesRopeAnalysisSourceScan._call_name_source(text)
        if call_name in {"MappingProxyType", "build_lazy_import_map"}:
            args = FlextInfraUtilitiesRopeAnalysisSourceScan._call_args_source(
                text, call_name
            )
            return (
                FlextInfraUtilitiesRopeAnalysisSourceScan._mapping_entries_refs_source(
                    args[0]
                )
                if args
                else ((), ())
            )
        if call_name == "merge_lazy_imports":
            entries: list[t.Pair[str, t.StrSequence]] = []
            refs: list[str] = []
            for arg in FlextInfraUtilitiesRopeAnalysisSourceScan._call_args_source(
                text, call_name
            ):
                next_entries, next_refs = (
                    FlextInfraUtilitiesRopeAnalysisSourceScan._mapping_entries_refs_source(
                        arg
                    )
                )
                entries.extend(next_entries)
                refs.extend(next_refs)
            return (tuple(entries), tuple(dict.fromkeys(refs)))
        if not text.startswith("{") or not text.endswith("}"):
            return ((), ())
        entries = []
        refs = []
        for item in FlextInfraUtilitiesRopeAnalysisSourceScan._split_top_level_commas(
            text[1:-1]
        ):
            stripped = item.strip()
            if stripped.startswith("**"):
                ref_name = (
                    FlextInfraUtilitiesRopeAnalysisSourceScan._symbol_name_source(
                        stripped[2:]
                    )
                )
                if ref_name:
                    refs.append(ref_name)
                continue
            key_source, separator, value_source = (
                FlextInfraUtilitiesRopeAnalysisSourceScan._top_level_partition(
                    stripped, ":"
                )
            )
            if not separator:
                continue
            key = FlextInfraUtilitiesRopeAnalysisSourceScan._literal_string_source(
                key_source
            )
            values = FlextInfraUtilitiesRopeAnalysisSourceScan._literal_string_sequence_source(
                value_source
            )
            if key and values:
                entries.append((key, values))
        return (tuple(entries), tuple(dict.fromkeys(refs)))

    @staticmethod
    def _call_name_source(source: str) -> str:
        """Return the final symbol name for a call source fragment."""
        text = source.strip()
        open_index = text.find("(")
        if open_index < 0:
            return ""
        return FlextInfraUtilitiesRopeAnalysisSourceScan._symbol_name_source(
            text[:open_index]
        )

    @staticmethod
    def _is_symbol_source(source: str) -> bool:
        """Return whether source is a simple dotted or underscored symbol."""
        text = source.strip()
        return bool(text) and all(char.isalnum() or char in {"_", "."} for char in text)

    @staticmethod
    def _symbol_name_source(source: str) -> str:
        """Return the final identifier from one symbol source fragment."""
        text = source.strip()
        if not FlextInfraUtilitiesRopeAnalysisSourceScan._is_symbol_source(text):
            return ""
        return text.rsplit(".", maxsplit=1)[-1]

    @staticmethod
    def _from_import_bindings_source(
        source: str,
    ) -> t.VariadicTuple[t.Quad[str, int, str, str]]:
        """Return ``(module, level, original, bound)`` for ``from`` imports."""
        lines = source.splitlines()
        bindings: list[t.Quad[str, int, str, str]] = []
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.startswith("from ") or " import " not in stripped:
                continue
            statement = FlextInfraUtilitiesRopeAnalysisSourceScan._collect_statement(
                lines, index
            ).strip()
            import_index = statement.find(" import ")
            module_source = statement[5:import_index].strip()
            level = len(module_source) - len(module_source.lstrip("."))
            module_name = module_source[level:]
            aliases_source = statement[import_index + len(" import ") :].strip()
            if aliases_source.startswith("(") and aliases_source.endswith(")"):
                aliases_source = aliases_source[1:-1]
            for (
                alias_source
            ) in FlextInfraUtilitiesRopeAnalysisSourceScan._split_top_level_commas(
                aliases_source
            ):
                original, bound = (
                    FlextInfraUtilitiesRopeAnalysisSourceScan._import_alias_names(
                        alias_source
                    )
                )
                if original and bound:
                    bindings.append((module_name, level, original, bound))
        return tuple(bindings)

    @staticmethod
    def _import_alias_names(source: str) -> t.Pair[str, str]:
        """Return ``(original, bound)`` names for one import alias source."""
        parts = source.strip().split()
        if (
            len(parts)
            == FlextInfraUtilitiesRopeAnalysisSourceScan._IMPORT_ALIAS_AS_PARTS
            and parts[1] == "as"
        ):
            return (parts[0], parts[2])
        if len(parts) == 1:
            return (parts[0], parts[0])
        return ("", "")

    @staticmethod
    def _class_header_source(source: str, class_name: str) -> str:
        """Return the collected class header source for one top-level class."""
        lines = source.splitlines()
        prefix = f"class {class_name}"
        for index, line in enumerate(lines):
            if line[: len(line) - len(line.lstrip())]:
                continue
            stripped = line.strip()
            if not stripped.startswith(prefix):
                continue
            tail = stripped[len(prefix) :]
            if tail and tail[0] not in {"(", ":"}:
                continue
            statement = FlextInfraUtilitiesRopeAnalysisSourceScan._collect_statement(
                lines, index
            )
            return statement.rsplit(":", maxsplit=1)[0]
        return ""

    @staticmethod
    def export_target_modules_source(
        source: str, package_name: str, exports: t.StrSequence
    ) -> MutableMapping[str, str]:
        """Map exports → defining module via rope's parsed-source import table."""
        export_names = {name for name in exports if name}
        target_map: MutableMapping[str, str] = dict.fromkeys(export_names, package_name)
        pymodule = FlextInfraUtilitiesRopeAnalysisAstHelpers.parse_string_module(source)
        module_ast = pymodule.get_ast()
        for node in FlextInfraUtilitiesRopeAnalysisAstHelpers.walk_ast_nodes(
            module_ast
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
