"""TYPE_CHECKING render helpers for lazy-init generation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from flext_infra import c
from flext_infra.codegen._codegen_generation_imports import (
    FlextInfraCodegenGenerationImportsMixin,
)

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraCodegenGenerationTypeCheckingMixin(
    FlextInfraCodegenGenerationImportsMixin,
):
    """TYPE_CHECKING block generation helper methods."""

    @staticmethod
    def _collapse_to_children(
        groups: t.MappingKV[str, t.StrPairSequence],
        child_packages: t.StrSequence | None,
    ) -> t.MappingKV[str, t.MutableSequenceOf[t.StrPair]]:
        """Collapse child module imports into configured child packages.

        Returns:
            The resulting ``t.MappingKV[str, t.MutableSequenceOf[t.StrPair]]``.

        """
        sorted_children: list[str] = sorted(
            set(child_packages or []),
            key=len,
            reverse=True,
        )
        collapsed: MutableMapping[str, list[t.StrPair]] = defaultdict(list)
        for mod, items in groups.items():
            target = mod
            for child_package in sorted_children:
                if mod.startswith(child_package + ".") or mod == child_package:
                    target = child_package
                    break
            collapsed[target].extend(items)
        return collapsed

    @staticmethod
    def _has_flext_types(collapsed: t.MappingKV[str, t.StrPairSequence]) -> bool:
        """Return whether a collapsed import map already imports FlextTypes.

        Returns:
            Whether a collapsed import map already imports FlextTypes.

        """
        return any(
            export_name == "FlextTypes"
            for items in collapsed.values()
            for export_name, _ in items
        )

    @staticmethod
    def _type_checking_sort_key(mod: str, root_names: frozenset[str]) -> t.StrPair:
        """Rank an import by ruff isort section, then by module path.

        ruff/isort partitions imports into sections — third-party, then
        first-party (this package's own root), then local (relative) — sorted
        alphabetically within each section and separated by a single blank
        line (``section_whitelines``). The legacy rank lumped every absolute
        import into one alphabetical run, so a third-party import (e.g.
        ``flext_tests``) sorted ahead of this package's own first-party import,
        violating I001 in the generated ``tests`` initializers. Sections are
        derived from the emitted module's owner and the package root so the
        generated order mirrors each project's ruff isort config.

        Returns:
            The resulting ``t.StrPair``.

        """
        if mod.startswith("."):
            return ("2", mod.lower())  # local-folder section
        own_top = mod.split(".", maxsplit=1)[0]
        return ("1" if own_top in root_names else "0", mod.lower())

    @staticmethod
    def _is_root_module_alias_group(mod: str, items: t.StrPairSequence) -> bool:
        """Return whether ``mod`` is one direct root child reexporting itself.

        Returns:
            Whether ``mod`` is one direct root child reexporting itself.

        """
        return (
            mod.count(".") == 1
            and bool(items)
            and all(
                not attr_name and export_name == mod.rsplit(".", maxsplit=1)[-1]
                for export_name, attr_name in items
            )
        )

    @staticmethod
    def _merge_root_alias_groups(
        collapsed: t.MappingKV[str, t.MutableSequenceOf[t.StrPair]],
    ) -> MutableMapping[str, t.StrPairSequence]:
        """Fold direct root-child module aliases into one root-relative group.

        Ruff renders consecutive ``from . import <child> as <child>`` statements
        as one root-relative import; separate per-child groups emitted one line
        each, so every generation diverged from the formatter's canonical form
        and only a post-generation autofix converged the published initializer.

        Returns:
            The resulting ``MutableMapping[str, t.StrPairSequence]``.

        """
        merged: MutableMapping[str, t.StrPairSequence] = {}
        root_items: t.StrPairSequence = ()
        for mod, items in collapsed.items():
            if FlextInfraCodegenGenerationTypeCheckingMixin._is_root_module_alias_group(
                mod,
                items,
            ):
                root_items = (*root_items, *items)
                continue
            merged[mod] = items
        if root_items:
            merged["."] = (*merged.get(".", ()), *root_items)
        return merged

    @staticmethod
    def _type_checking_sort_owner(mod: str, items: t.StrPairSequence) -> str:
        """Return the module that owns the emitted import for sorting.

        Returns:
            The module that owns the emitted import for sorting.

        """
        module_basename = mod.rsplit(".", maxsplit=1)[-1]
        if (
            "." in mod
            and items
            and all(
                not attr_name and export_name == module_basename
                for export_name, attr_name in items
            )
        ):
            # Module aliases emit from their parent package.
            return mod.rsplit(".", maxsplit=1)[0] or "."
        return mod

    @staticmethod
    def _should_skip_type_checking_module_export(
        mod: str,
        export_name: str,
        attr_name: str,
        root_name: str,
    ) -> bool:
        """Return whether a symbol import is a redundant root self-import.

        Returns:
            Whether a symbol import is a redundant root self-import.

        """
        if export_name in c.Infra.ALIAS_NAMES or not export_name:
            return False
        if export_name in {"cli", "main", "infra"}:
            return False
        if export_name != export_name.lower():
            return False
        if not attr_name:
            # Literal __all__ requires every module alias binding.
            return False
        # A lowercase ``from mod import name`` (package-name alias like ``grpc``
        # or a lowercase module-level function) is a real symbol
        # that must stay statically visible; only skip a redundant self-import
        # from the root package itself.
        return mod == root_name and attr_name == export_name

    @staticmethod
    def _emit_type_checking_module(
        mod: str,
        rendered_mod: str,
        items: t.StrPairSequence,
        root_name: str,
        lines: t.MutableSequenceOf[str],
    ) -> None:
        """Emit one TYPE_CHECKING module import group.

        ``mod`` is the planned (possibly package-relative) owner that decides
        module-alias exports; ``rendered_mod`` is its absolute import form.
        """
        alias_exports: t.MutableSequenceOf[str] = []
        parts: t.MutableSequenceOf[str] = []
        module_basename = mod.rsplit(".", maxsplit=1)[-1]
        selected_items = tuple(
            item
            for item in sorted(
                items,
                key=FlextInfraCodegenGenerationTypeCheckingMixin._import_item_sort_key,
            )
            if not (
                FlextInfraCodegenGenerationTypeCheckingMixin._should_skip_type_checking_module_export
            )(
                mod,
                item[0],
                item[1],
                root_name,
            )
        )
        for export_name, attr_name in selected_items:
            if not attr_name:
                if export_name == module_basename:
                    alias_exports.append(export_name)
                else:
                    parts.append(
                        FlextInfraCodegenGenerationTypeCheckingMixin._format_import_part(
                            export_name,
                            export_name,
                        ),
                    )
                continue
            parts.append(
                FlextInfraCodegenGenerationTypeCheckingMixin._format_import_part(
                    attr_name,
                    export_name,
                ),
            )
        for export_name in tuple(dict.fromkeys(alias_exports)):
            lines.extend(
                FlextInfraCodegenGenerationTypeCheckingMixin._format_type_checking_module_alias_import(
                    "    ",
                    rendered_mod,
                    export_name,
                ),
            )
        deduped_parts = tuple(dict.fromkeys(parts))
        if deduped_parts:
            lines.extend(
                FlextInfraCodegenGenerationTypeCheckingMixin._format_import(
                    "    ",
                    rendered_mod,
                    deduped_parts,
                ),
            )

    @classmethod
    def generate_type_checking(
        cls,
        groups: t.MappingKV[str, t.StrPairSequence],
        *,
        include_flext_types: bool = True,
        child_packages: t.StrSequence | None = None,
        local_package_root: str | None = None,
        root_names: frozenset[str] | None = None,
    ) -> t.StrSequence:
        """Generate a TYPE_CHECKING import block.

        Returns:
            The resulting ``t.StrSequence``.

        """
        if not groups and not include_flext_types:
            return ()
        if not groups:
            return ("if TYPE_CHECKING:", "    from flext_core import FlextTypes")
        normalized_groups: MutableMapping[str, t.StrPairSequence] = {}
        for mod, items in groups.items():
            resolved = cls._normalize_type_checking_module_path(
                mod,
                local_package_root,
            )
            cls._reject_noncanonical_type_checking_import(
                resolved,
                local_package_root,
                items,
            )
            normalized_groups[resolved] = (*normalized_groups.get(resolved, ()), *items)
        collapsed = cls._collapse_to_children(normalized_groups, child_packages)
        merged_groups = cls._merge_root_alias_groups(collapsed)
        root_name = "" if not local_package_root else local_package_root.split(".")[0]
        # Derive the set of first-party roots for isort sectioning. When the
        # caller provides an explicit root_names (e.g. test facades need both
        # "tests" and the project package), use it; otherwise fall back to the
        # single root_name so non-test packages are unaffected.
        effective_root_names = (
            root_names if root_names is not None else frozenset({root_name})
        )
        lines: t.MutableSequenceOf[str] = ["if TYPE_CHECKING:"]
        flext_types_emitted = include_flext_types and not cls._has_flext_types(
            collapsed,
        )
        if flext_types_emitted:
            lines.append("    from flext_core import FlextTypes")

        package = local_package_root or ""
        rendered_mods = {
            mod: cls._absolute_import_module(package, mod) for mod in merged_groups
        }

        def type_checking_module_key(mod: str) -> t.StrPair:
            owner = cls._type_checking_sort_owner(
                rendered_mods[mod],
                () if mod == "." else merged_groups[mod],
            )
            return cls._type_checking_sort_key(owner, effective_root_names)

        sorted_mods = sorted(merged_groups, key=type_checking_module_key)
        # ``from flext_core import FlextTypes`` (when emitted above) is the
        # leading absolute import; seed the previous section so the first loop
        # group only separates on a real ruff isort section transition rather
        # than against an empty prior state, and so the local-section blank that
        # follows the absolutes is preserved.
        previous_section: str | None = (
            cls._type_checking_sort_key("flext_core", effective_root_names)[0]
            if flext_types_emitted
            else None
        )
        for mod in sorted_mods:
            current_section = type_checking_module_key(mod)[0]
            if previous_section is not None and current_section != previous_section:
                lines.append("")
            cls._emit_type_checking_module(
                mod,
                rendered_mods[mod],
                merged_groups[mod],
                root_name,
                lines,
            )
            previous_section = current_section
        return () if len(lines) == 1 else lines


__all__: list[str] = ["FlextInfraCodegenGenerationTypeCheckingMixin"]
