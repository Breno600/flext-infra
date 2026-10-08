"""Lazy point-of-use placement and import-guard removal.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path

from flext_infra import c, t
from flext_infra.refactor._import_ast import FlextInfraImportNormalizationAstMixin


class FlextInfraImportNormalizationDemotionMixin(
    FlextInfraImportNormalizationAstMixin,
):
    """Own rules 1-2: demote function-only imports to their use sites."""

    @dataclass(frozen=True)
    class DemotionScan:
        """Immutable per-pass context for one lazy demotion scan."""

        tree: ast.Module
        parents: t.MappingKV[int, ast.AST]
        frozen: set[int]
        package: str
        module_rank: int
        file_path: Path
        family_exports: t.MappingKV[str, t.Infra.StrSet]

    # -- rules 1-2: lazy placement -----------------------------------------------------

    @classmethod
    def _lazy_demotion_edits(
        cls,
        tree: ast.Module,
        source: str,
        package: str,
        file_path: Path,
        family_exports: t.MappingKV[str, t.Infra.StrSet],
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Demote function-only module-level imports to their point of use.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        lines = source.splitlines()
        scan = cls.DemotionScan(
            tree=tree,
            parents=cls._parent_map(tree),
            frozen=cls._frozen_node_ids(tree),
            package=package,
            module_rank=cls._module_layer_rank(file_path),
            file_path=file_path,
            family_exports=family_exports,
        )
        insertions: MutableMapping[
            int,
            MutableMapping[str, t.Infra.StrSet],
        ] = defaultdict(lambda: defaultdict(set))
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        for node in cls._iter_imports(tree):
            if not isinstance(node, ast.ImportFrom) or not cls._demotion_scope(
                node,
                package,
                scan.parents,
            ):
                continue
            cls._collect_demotion_edits(scan, node, insertions, edits)
        guard_edits = cls._guard_cleanup_edits(
            tree,
            lines,
            scan.parents,
            scan.frozen,
            insertions,
        )
        edits.extend(guard_edits)
        edits.extend(cls._insertion_edits(insertions, lines))
        return edits

    @classmethod
    def _demotion_scope(
        cls,
        node: ast.stmt,
        package: str,
        parents: t.MappingKV[int, ast.AST],
    ) -> bool:
        """Return whether one import statement is a lazy-demotion subject.

        Returns:
            Whether one import statement is a lazy-demotion subject.

        """
        if not isinstance(node, ast.ImportFrom) or node.level:
            return False
        if node.module is None:
            return False
        top_module = node.module.split(".", maxsplit=1)[0]
        if top_module != package and not top_module.startswith("flext_"):
            return False
        if cls._inside_type_checking(node, parents):
            return False
        return cls._at_module_level(node, parents)

    @classmethod
    def _collect_demotion_edits(
        cls,
        scan: FlextInfraImportNormalizationDemotionMixin.DemotionScan,
        node: ast.ImportFrom,
        insertions: MutableMapping[int, MutableMapping[str, t.Infra.StrSet]],
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]],
    ) -> None:
        """Record one subject import's demotion plan into insertions/edits."""
        demotable: list[tuple[str, str | None]] = []
        kept: list[str] = []
        for alias in node.names:
            demotes, bound = cls._record_alias_plan(scan, node, alias, insertions)
            if not demotes:
                if bound is not None:
                    kept.append(bound)
                continue
            demotable.append((alias.name, bound))
        if not demotable:
            return
        cls._append_demotion_edit(node, kept, edits)

    @classmethod
    def _record_alias_plan(
        cls,
        scan: FlextInfraImportNormalizationDemotionMixin.DemotionScan,
        node: ast.ImportFrom,
        alias: ast.alias,
        insertions: MutableMapping[int, MutableMapping[str, t.Infra.StrSet]],
    ) -> tuple[bool, str | None]:
        """Decide one alias's placement, recording its insertion anchors.

        Returns:
            The resulting ``tuple[bool, str | None]``: whether the alias
            demotes to its use sites, then the bound name kept at module
            level (``None`` when the binding is dropped entirely).

        """
        bound = alias.asname or alias.name
        reverse_edge = cls._source_is_later_layer(
            node.module or "",
            scan.package,
            scan.module_rank,
            scan.file_path,
        )
        if not cls._demotion_candidate(
            alias,
            bound,
            scan.module_rank,
            reverse_edge=reverse_edge,
        ):
            return False, bound
        sites = cls._use_sites(scan.tree, bound)
        if not sites:
            if reverse_edge or cls._is_late_letter(alias, bound, scan.module_rank):
                # An unused late letter at module level is never a typing
                # reference: binding it eagerly only risks the self-facade
                # cycle (u inside the utilities tree).
                return False, None
            return False, bound
        if not all(cls._demotable(site, scan.parents, scan.frozen) for site in sites):
            return False, bound
        target_module = cls._canonical_lazy_module(
            node.module or "",
            alias.name,
            scan.package,
            scan.family_exports,
        )
        for anchor in cls._function_anchors(sites, scan.parents):
            insertions[anchor][target_module].add(
                alias.name
                if alias.asname is None
                else f"{alias.name} as {alias.asname}",
            )
        return True, bound

    @classmethod
    def _append_demotion_edit(
        cls,
        node: ast.ImportFrom,
        kept: t.SequenceOf[str],
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]],
    ) -> None:
        """Append the rewritten or deleted import line for one subject."""
        if not kept:
            edits.append((node.lineno, cls._end_line(node), ()))
            return
        clauses = ", ".join(
            alias.name if alias.asname is None else f"{alias.name} as {alias.asname}"
            for alias in node.names
            if (alias.asname or alias.name) in set(kept)
        )
        edits.append(
            (
                node.lineno,
                cls._end_line(node),
                (f"from {node.module} import {clauses}",),
            ),
        )

    @classmethod
    def _insertion_edits(
        cls,
        insertions: t.MappingKV[int, t.MappingKV[str, t.Infra.StrSet]],
        lines: t.StrSequence,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Turn one scan's recorded insertions into before-insert edits.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        edits: list[tuple[int, int, t.StrSequence]] = []
        for anchor, by_module in insertions.items():
            if not by_module:
                continue
            indent = cls._function_body_indent(lines, anchor)
            insert_lines = [
                f"{indent}from {module} import {', '.join(sorted(bounds))}"
                for module, bounds in sorted(by_module.items())
            ]  # bounds carry full `name as alias` clauses; sorted keeps determinism
            edits.append((anchor, anchor - 1, tuple(insert_lines)))
        return edits

    @staticmethod
    def _is_late_letter(
        alias: ast.alias,
        bound: str,
        module_rank: int,
    ) -> bool:
        """Return whether one binding is an own-package letter at/after its layer.

        Returns:
            Whether one binding is an own-package letter at/after its layer.

        """
        return (
            alias.asname is None
            and bound in c.Infra.IMPORT_NORMALIZATION_LETTER_ORDER
            and c.Infra.IMPORT_NORMALIZATION_LETTER_ORDER[bound] >= module_rank
        )

    @classmethod
    def _source_is_later_layer(
        cls,
        module: str,
        package: str,
        module_rank: int,
        file_path: Path,
    ) -> bool:
        """Return whether one import source sits after the module's own layer.

        Rule 2: imports point only to strictly earlier elements, so a binding
        from a later-layer module (the api or cli facade, another services
        module) is a reverse edge and belongs at the point of use.

        Returns:
            Whether one import source sits after the module's own layer.

        """
        names = module.split(".")
        if names[0] != package or len(names) == 1:
            return False
        importer_family = next(
            (
                part
                for part in file_path.parts
                if part.lstrip("_") in c.Infra.IMPORT_NORMALIZATION_FAMILY_LETTER
            ),
            None,
        )
        if (
            importer_family is not None
            and len(names) > 1
            and names[1] == importer_family
        ):
            # A family member importing a sibling of its own family is a
            # same-layer edge, never a reverse one.
            return False
        tail = names[-1]
        if len(names) == c.Infra.IMPORT_NORMALIZATION_FAMILY_PATH_DEPTH:
            rank = c.Infra.IMPORT_NORMALIZATION_FAMILY_RANK.get(tail.lstrip("_"))
            if rank is not None:
                return rank > module_rank
        if tail in {"api", "cli"}:
            return c.Infra.IMPORT_NORMALIZATION_FACADE_RANK[tail] > module_rank
        if "services" in names or tail == "base":
            return (9 if "services" in names else 8) > module_rank
        return module_rank < c.Infra.IMPORT_NORMALIZATION_DEFAULT_LAYER_RANK

    @classmethod
    def _demotion_candidate(
        cls,
        alias: ast.alias,
        bound: str,
        module_rank: int,
        *,
        reverse_edge: bool,
    ) -> bool:
        """Return whether one binding is a lazy-placement candidate at all.

        A concrete object (capitalized binding) is always a candidate; an
        own-package letter is one when its layer rank sits at or after the
        module's own layer (rule 2: imports point only to strictly earlier
        elements); any binding off a later-layer module is a reverse edge and
        belongs at the point of use.

        Returns:
            Whether one binding is a lazy-placement candidate at all.

        """
        if bound[:1].isupper() or reverse_edge:
            return True
        return cls._is_late_letter(alias, bound, module_rank)

    @staticmethod
    def _is_import_guard(node: ast.stmt) -> bool:
        """Return whether one statement is a bare ``try/except ImportError``.

        Returns:
            Whether one statement is a bare ``try/except ImportError``.

        """
        if not isinstance(node, ast.Try) or not node.handlers:
            return False
        return all(
            isinstance(handler.type, ast.Name) and handler.type.id == "ImportError"
            for handler in node.handlers
        )

    @staticmethod
    def _guarded_imports(node: ast.Try) -> list[tuple[str, str]]:
        """Return the ``(module, bound)`` pairs one import guard rebinds.

        Returns:
            The resulting ``list[tuple[str, str]]``.

        """
        return [
            (statement.module, alias.asname or alias.name)
            for statement in node.body
            if isinstance(statement, ast.ImportFrom) and statement.module
            for alias in statement.names
        ]

    @classmethod
    def _cleanup_import_guard(
        cls,
        tree: ast.Module,
        node: ast.Try,
        parents: t.MappingKV[int, ast.AST],
        frozen: set[int],
        insertions: MutableMapping[int, MutableMapping[str, t.Infra.StrSet]],
    ) -> tuple[
        tuple[int, int, t.StrSequence] | None,
        list[tuple[str, tuple[str, ...]]],
    ]:
        """Plan one guard's removal, routing each name to its placement.

        Returns:
            The resulting ``tuple[
                tuple[int, int, t.StrSequence] | None,
                list[tuple[str, tuple[str, ...]]],
            ]``: the guard-deletion edit (``None`` when the guard binds
            nothing), then each module whose names still need a plain
            module-level fallback import with its sorted names.

        """
        guarded = cls._guarded_imports(node)
        if not guarded:
            return None, []
        fallback_by_module: MutableMapping[str, set[str]] = defaultdict(set)
        for module, bound in guarded:
            sites = cls._use_sites(tree, bound)
            if sites and all(cls._demotable(site, parents, frozen) for site in sites):
                for anchor in cls._function_anchors(sites, parents):
                    insertions[anchor][module].add(bound)
            else:
                fallback_by_module[module].add(bound)
        return (node.lineno, cls._end_line(node), ()), [
            (module, tuple(sorted(names)))
            for module, names in fallback_by_module.items()
        ]

    @classmethod
    def _guard_cleanup_edits(
        cls,
        tree: ast.Module,
        lines: t.StrSequence,
        parents: t.MappingKV[int, ast.AST],
        frozen: set[int],
        insertions: MutableMapping[int, MutableMapping[str, t.Infra.StrSet]],
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Remove ``try/except ImportError`` import guards; rebind at use.

        A guarded name the module still uses at definition time falls back to
        a plain module-level import line at the guard's position.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        for node in tree.body:
            if not isinstance(node, ast.Try) or not cls._is_import_guard(node):
                continue
            removal, fallbacks = cls._cleanup_import_guard(
                tree,
                node,
                parents,
                frozen,
                insertions,
            )
            if removal is not None:
                edits.append(removal)
            edits.extend(
                cls._guard_fallback_edit(tree, lines, module, names)
                for module, names in fallbacks
            )
        return edits

    @classmethod
    def _guard_fallback_edit(
        cls,
        tree: ast.Module,
        lines: t.StrSequence,
        module: str,
        names: t.StrSequence,
    ) -> tuple[int, int, t.StrSequence]:
        """Return the plain import line replacing a guard with module-level use.

        Returns:
            The resulting ``tuple[int, int, t.StrSequence]``.

        """
        anchor = next(
            (node for node in tree.body if isinstance(node, ast.Try)),
            tree.body[0] if tree.body else None,
        )
        line = anchor.lineno if anchor is not None else 1
        indent = cls._line_indent(lines[line - 1])
        # Insert before the anchor by replacing the preceding boundary; the
        # edit engine inserts at (line, line - 1) spans as a before-insert.
        return (line, line - 1, (f"{indent}from {module} import {', '.join(names)}",))

    @classmethod
    def _canonical_lazy_module(
        cls,
        module: str,
        bound: str,
        package: str,
        family_exports: t.MappingKV[str, t.Infra.StrSet],
    ) -> str:
        """Flatten one lazy import's leaf path onto its family root.

        Returns:
            The resulting ``str``.

        """
        names = module.split(".")
        if (
            len(names) < c.Infra.IMPORT_NORMALIZATION_LEAF_PATH_DEPTH
            or names[0] != package
        ):
            return module
        family = names[1].lstrip("_")
        if family not in c.Infra.IMPORT_NORMALIZATION_FAMILY_LETTER:
            return module
        if bound in family_exports.get(family, set()):
            return f"{names[0]}.{names[1]}"
        return module


__all__: list[str] = ["FlextInfraImportNormalizationDemotionMixin"]
