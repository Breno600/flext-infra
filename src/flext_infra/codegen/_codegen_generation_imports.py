"""Import rendering helpers for lazy-init generation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from flext_infra import config
from flext_infra.codegen._codegen_generation_paths import (
    FlextInfraCodegenGenerationPathsMixin,
)

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraCodegenGenerationImportsMixin(FlextInfraCodegenGenerationPathsMixin):
    """Import grouping and rendering helper methods."""

    @staticmethod
    def _format_import_part(imported_name: str, export_name: str) -> str:
        """Format one imported symbol, preserving aliases only when names differ.

        Returns:
            The resulting ``str``.

        """
        if imported_name == export_name:
            return imported_name
        return f"{imported_name} as {export_name}"

    @staticmethod
    def _format_import(indent: str, mod: str, parts: t.StrSequence) -> t.StrSequence:
        """Emit one Ruff-canonical import statement within the configured width.

        Returns:
            The resulting ``t.StrSequence``.

        """
        compact = f"{indent}from {mod} import {', '.join(parts)}"
        if len(compact) <= config.Infra.tooling.tools.ruff.line_length:
            return (compact,)
        nested_indent = f"{indent}    "
        # One symbol per wrapped line is the only form Ruff's isort accepts
        # (I001); a generated facade that outgrows a LOC cap is the cap
        # owner's finding, never a reason to render an invalid import block.
        return (
            f"{indent}from {mod} import (",
            *(f"{nested_indent}{part}," for part in parts),
            f"{indent})",
        )

    @staticmethod
    def _format_module_alias_import(
        indent: str,
        mod: str,
        export_name: str,
    ) -> t.StrSequence:
        """Format a module alias import as a from-import of its parent package.

        Returns:
            The resulting ``t.StrSequence``.

        """
        if "." in mod and mod != ".":
            parent_mod, _, child_name = mod.rpartition(".")
            compact = (
                f"{indent}from {parent_mod or '.'} import {child_name} as {export_name}"
            )
            line_length = config.Infra.tooling.tools.ruff.line_length
            if len(compact) <= line_length:
                return (compact,)
            nested_indent = f"{indent}    "
            # One symbol per wrapped line is the only form Ruff's isort accepts
            # (I001); the width contract matches _format_import so the render
            # stays inside the configured budget (flext-xjoph).
            return (
                f"{indent}from {parent_mod or '.'} import (",
                f"{nested_indent}{child_name} as {export_name},",
                f"{indent})",
            )
        return (f"{indent}import {mod} as {export_name}",)

    @staticmethod
    def _format_type_checking_module_alias_import(
        indent: str,
        mod: str,
        export_name: str,
    ) -> t.StrSequence:
        """Format one explicit static reexport.

        Returns:
            The resulting ``t.StrSequence``.

        """
        return FlextInfraCodegenGenerationImportsMixin._format_module_alias_import(
            indent,
            mod,
            export_name,
        )

    @staticmethod
    def _group_imports(
        import_map: t.LazyAliasMap,
    ) -> t.MappingKV[str, t.MutableSequenceOf[t.StrPair]]:
        """Group import map entries by module.

        Returns:
            The resulting ``t.MappingKV[str, t.MutableSequenceOf[t.StrPair]]``.

        """
        groups: MutableMapping[str, list[t.StrPair]] = defaultdict(list)
        for export_name in sorted(import_map):
            mod, attr = import_map[export_name]
            groups[mod].append((export_name, attr))
        return groups

    @staticmethod
    def _import_item_sort_key(item: t.StrPair) -> t.Pair[t.Pair[int, str], bool]:
        """Order an imported symbol like Ruff isort (``order-by-type``).

        Constants (all upper case) precede CamelCase classes, which precede
        lower-case names; the name is the secondary key and the alias status
        the tertiary one. Plain lexicographic ordering fights ``ruff format``
        isort on the same generated block, producing a gen/fmt flip-flop.

        Returns:
            The resulting ``t.Pair[t.Pair[int, str], bool]``.

        """
        export_name, imported_name = item
        imported = imported_name or export_name
        category = 0 if imported.isupper() else 1 if imported[:1].isupper() else 2
        # Ruff isort orders names inside a type group case-insensitively
        # (``TEST_FACADE_BASES`` < ``TESTS_ROOT``): raw ASCII puts ``S`` (83)
        # before ``_`` (95) and flips the pair, producing a gen/fmt flip-flop.
        return (category, imported.casefold()), export_name != imported_name


__all__: list[str] = ["FlextInfraCodegenGenerationImportsMixin"]
