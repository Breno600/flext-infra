"""Canonical FLEXT import-form enforcement engine.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import operator
from collections import defaultdict
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path

from flext_infra import c, t


@dataclass(frozen=True)
class _DemotionScan:
    """Immutable per-pass context for one lazy demotion scan."""

    tree: ast.Module
    parents: t.MappingKV[int, ast.AST]
    frozen: set[int]
    package: str
    module_rank: int
    file_path: Path
    family_exports: t.MappingKV[str, t.Infra.StrSet]


class FlextInfraImportNormalization:
    """Rewrite one module's imports into the canonical FLEXT forms.

    The four operator rules this engine owns, in one idempotent pass:

    1. Concrete objects (classes/functions) import lazily, inside the
       outermost function that uses them. Class bases, Pydantic annotations,
       decorators and signature defaults are structural module-definition
       uses and stay eager.
    2. Facade letters follow the layer order (settings, config, c, t, p, m,
       u, siblings, base, services, api, cli): a module-level letter binding
       at or after the module's own layer is demoted to the point of use when
       every use sits inside a function body.
    3. Letters of one package bind in ONE root-combined statement
       (``from pkg import c, m, p, t, u``); facade-file, alias-split and
       relative letter forms rewrite into it.
    4. Objects import through the family ``__init__``
       (``from pkg._models import X``); leaf-module paths flatten when the
       family init publishes the name (its ``TYPE_CHECKING`` imports, lazy
       export map and ``__all__`` are the export SSOT); internal family
       wiring the init does not publish stays leaf.

    ``try/except ImportError`` import guards are removed and their names
    re-bound at the point of use; no half-initialized ``= None`` fallback
    survives. A guarded name the module still uses at definition time falls
    back to a plain module-level import, never to a silent ``None``.

    The layer-order ranking lives in the constants family (``c.Infra.*``):
    ``LETTER_ORDER``, ``LETTER_RENDER_ORDER``, ``FAMILY_LETTER``,
    ``FAMILY_RANK``, ``FACADE_RANK``, ``MAX_PASSES``, ``FAMILY_PATH_DEPTH``,
    ``LEAF_PATH_DEPTH`` and ``DEFAULT_LAYER_RANK``.
    """

    @classmethod
    def apply_files(cls, project_root: Path, files: t.SequenceOf[Path]) -> bool:
        """Normalize every given file; return whether any source changed.

        Returns:
            Whether at least one file changed.

        """
        changed = False
        for file_path in files:
            try:
                source = file_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            except OSError:
                continue
            normalized = cls.normalize_source(
                project_root=project_root,
                file_path=file_path,
                source=source,
            )
            if normalized is None or normalized == source:
                continue
            file_path.write_text(normalized, encoding=c.Cli.ENCODING_DEFAULT)
            changed = True
        return changed

    @classmethod
    def normalize_source(
        cls,
        *,
        project_root: Path,
        file_path: Path,
        source: str,
    ) -> str | None:
        """Return the canonical form of one module, or ``None`` when out of scope.

        Returns:
            The resulting ``str | None``.

        """
        located = cls._locate(project_root, file_path)
        if located is None:
            return None
        package, module_name = located
        current = source
        for _ in range(c.Infra.MAX_PASSES):
            updated = cls._one_pass(
                project_root=project_root,
                file_path=file_path,
                package=package,
                module_name=module_name,
                source=current,
            )
            if updated is None or updated == current:
                break
            current = updated
        return current if current != source else None

    # -- one normalization pass ----------------------------------------------------

    @classmethod
    def _one_pass(
        cls,
        *,
        project_root: Path,
        file_path: Path,
        package: str,
        module_name: str,
        source: str,
    ) -> str | None:
        """Run one convergence pass; each rewrite category applies alone.

        A category whose own edits collide is skipped; the outer pass loop
        re-parses the converged text and retries it on the next pass.

        Returns:
            The resulting ``str | None``.

        """
        # One rewrite category per pass: every category's edits are computed
        # against the text they mutate, so categories never share a pass.
        tree = cls._parse(source)
        if tree is None:
            return None
        builders = (
            lambda: cls._relative_import_edits(
                tree,
                source,
                package,
                module_name,
                file_path,
            ),
            lambda: cls._letter_merge_edits(tree, source, package),
            lambda: cls._flatten_edits(
                tree,
                source,
                package,
                file_path,
                cls._family_exports(project_root, package),
            ),
            lambda: cls._lazy_demotion_edits(
                tree,
                source,
                package,
                file_path,
                cls._family_exports(project_root, package),
            ),
            lambda: cls._foundation_routing_edits(tree, source, package, file_path),
            lambda: cls._self_family_unflatten_edits(
                tree,
                source,
                package,
                file_path,
                project_root,
            ),
        )
        for build in builders:
            applied = cls._apply_edits(source, build())
            if applied is None or applied == source:
                continue
            return applied
        return None

    # -- rule 3: absolute imports ---------------------------------------------------

    @classmethod
    def _relative_import_edits(
        cls,
        tree: ast.Module,
        source: str,
        package: str,
        module_name: str,
        file_path: Path,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Rewrite relative imports of the own package to absolute form.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        lines = source.splitlines()
        parts = module_name.split(".")
        current_parts = parts if file_path.name == "__init__.py" else parts[:-1]
        for node in cls._iter_imports(tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            base = current_parts[: len(current_parts) - (node.level - 1)]
            target = ".".join([*base, node.module or ""]).strip(".")
            if not target.startswith(f"{package}.") and target != package:
                continue
            indent = cls._line_indent(lines[node.lineno - 1])
            clauses = ", ".join(
                alias.name
                if alias.asname is None
                else f"{alias.name} as {alias.asname}"
                for alias in node.names
            )
            edits.append(
                (
                    node.lineno,
                    cls._end_line(node),
                    (f"{indent}from {target} import {clauses}",),
                ),
            )
        return edits

    # -- rule 3: root-combined letters -----------------------------------------------

    @classmethod
    def _letter_merge_edits(
        cls,
        tree: ast.Module,
        source: str,
        package: str,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Merge every same-block letter import into one root-combined line.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        parents = cls._parent_map(tree)
        groups: MutableMapping[
            int,
            list[tuple[ast.ImportFrom, list[tuple[str, str | None]]]],
        ] = defaultdict(list)
        for node in cls._iter_imports(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not cls._at_module_level(node, parents):
                continue
            merged = cls._letter_aliases(node, package)
            if merged is None:
                continue
            block = cls._owning_block(node, parents)
            groups[id(block)].append((node, merged))
        if not groups:
            return ()
        lines = source.splitlines()
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        for entries in groups.values():
            entries.sort(key=lambda item: item[0].lineno)
            letters: t.Infra.StrSet = {
                effective
                for _node, aliases in entries
                for name, bound in aliases
                if (effective := bound if bound is not None else name)
                in c.Infra.LETTER_ORDER
            }
            if not letters:
                continue
            ordered = [
                letter for letter in c.Infra.LETTER_RENDER_ORDER if letter in letters
            ]
            first = entries[0][0]
            indent = cls._line_indent(lines[first.lineno - 1])
            merged_line = f"{indent}from {package} import {', '.join(ordered)}"
            edits.append((first.lineno, cls._end_line(first), (merged_line,)))
            for node, _aliases in entries[1:]:
                edits.append((node.lineno, cls._end_line(node), ()))
        return edits

    @classmethod
    def _letter_aliases(
        cls,
        node: ast.ImportFrom,
        package: str,
    ) -> list[tuple[str, str | None]] | None:
        """Return the aliases when one statement binds only facade letters.

        The three accepted shapes are the root form (``from pkg import u``),
        the facade-file form (``from pkg.typings import t``) and the
        alias-split form (``from pkg import typings as t``); anything else is
        not a letter statement.

        Returns:
            The resulting ``list[tuple[str, str | None]] | None``.

        """
        if node.module is None or node.level:
            return None
        names = node.module.split(".")
        if len(names) == 1 and names[0] == package:
            root_form = True
        elif (
            len(names) == c.Infra.FAMILY_PATH_DEPTH
            and names[0] == package
            and names[1].lstrip("_") in c.Infra.FAMILY_LETTER
        ):
            root_form = False
        else:
            return None
        aliases: list[tuple[str, str | None]] = []
        for alias in node.names:
            if alias.asname is None:
                # Root or facade-file form: the imported name IS the letter.
                if alias.name in c.Infra.LETTER_ORDER:
                    aliases.append((alias.name, None))
                    continue
                return None
            if (
                root_form
                and alias.name in c.Infra.FAMILY_LETTER
                and alias.asname in c.Infra.LETTER_ORDER
            ):
                aliases.append((alias.name, alias.asname))
                continue
            return None
        return aliases or None

    # -- rule 4: flattened family paths -----------------------------------------------

    @staticmethod
    def _partition_clauses(
        aliases: t.SequenceOf[ast.alias],
        exported: t.Infra.StrSet,
    ) -> tuple[list[str], list[str]]:
        """Split one statement's aliases into family-exported and kept clauses.

        Returns:
            The resulting ``tuple[list[str], list[str]]``: the clauses that
            move onto the family init, then the clauses that stay leaf.

        """
        moved: list[str] = []
        kept: list[str] = []
        for alias in aliases:
            clause = (
                alias.name
                if alias.asname is None
                else f"{alias.name} as {alias.asname}"
            )
            if alias.name in exported:
                moved.append(clause)
            else:
                kept.append(clause)
        return moved, kept

    @classmethod
    def _flatten_import_edit(
        cls,
        node: ast.stmt,
        package: str,
        file_path: Path,
        family_exports: t.MappingKV[str, t.Infra.StrSet],
        lines: t.StrSequence,
    ) -> tuple[int, int, t.StrSequence] | None:
        """Return the flatten edit for one import, or ``None`` when it stays.

        Returns:
            The resulting ``tuple[int, int, t.StrSequence] | None``.

        """
        if not isinstance(node, ast.ImportFrom) or node.level or node.module is None:
            return None
        names = node.module.split(".")
        # No member of the family may bind a sibling name through the
        # family init: the init is still assembling while its own modules
        # load, so the flattened form closes a self-family import cycle
        # (its own deep imports are the publication form itself).
        is_family_leaf = (
            len(names) >= c.Infra.LEAF_PATH_DEPTH
            and names[0] == package
            and names[1].lstrip("_") in c.Infra.FAMILY_LETTER
            and not cls._inside_family(file_path, names[1])
        )
        exported = family_exports.get(names[1].lstrip("_")) if is_family_leaf else None
        if not exported:
            return None
        moved_clauses, kept_clauses = cls._partition_clauses(node.names, exported)
        if not moved_clauses:
            return None
        indent = cls._line_indent(lines[node.lineno - 1])
        replacement: list[str] = []
        if kept_clauses:
            replacement.append(
                f"{indent}from {node.module} import {', '.join(kept_clauses)}",
            )
        replacement.append(
            f"{indent}from {names[0]}.{names[1]} import {', '.join(moved_clauses)}",
        )
        return (node.lineno, cls._end_line(node), tuple(replacement))

    @classmethod
    def _flatten_edits(
        cls,
        tree: ast.Module,
        source: str,
        package: str,
        file_path: Path,
        family_exports: t.MappingKV[str, t.Infra.StrSet],
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Flatten leaf-family object imports onto the family ``__init__``.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        lines = source.splitlines()
        for node in cls._iter_imports(tree):
            edit = cls._flatten_import_edit(
                node,
                package,
                file_path,
                family_exports,
                lines,
            )
            if edit is not None:
                edits.append(edit)
        return edits

    @classmethod
    def _family_exports(
        cls,
        project_root: Path,
        package: str,
    ) -> t.MappingKV[str, t.Infra.StrSet]:
        """Read each family init's published names from its own source.

        Returns:
            The resulting ``t.MappingKV[str, t.Infra.StrSet]``.

        """
        exports: MutableMapping[str, t.Infra.StrSet] = {}
        base = project_root / "src" if (project_root / "src").is_dir() else project_root
        pkg_dir = base / package
        if not pkg_dir.is_dir():
            return exports
        for family in c.Infra.FAMILY_LETTER:
            for candidate in (pkg_dir / f"_{family}", pkg_dir / family):
                init = candidate / "__init__.py"
                if not init.is_file():
                    continue
                try:
                    exports[family] = cls._published_names(init)
                except SyntaxError:
                    continue
                break
        return exports

    @classmethod
    def _published_names(cls, init_path: Path) -> t.Infra.StrSet:
        """Return the names one family init publishes.

        Returns:
            The resulting ``t.Infra.StrSet``.

        """
        tree = ast.parse(init_path.read_text(encoding=c.Cli.ENCODING_DEFAULT))
        names: t.Infra.StrSet = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names.update(alias.asname or alias.name for alias in node.names)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                names.add(node.value)
            if isinstance(node, ast.Assign):
                targets = [
                    target.id for target in node.targets if isinstance(target, ast.Name)
                ]
                if "__all__" in targets and isinstance(
                    node.value,
                    (ast.List, ast.Tuple),
                ):
                    names.update(
                        element.value
                        for element in node.value.elts
                        if isinstance(element, ast.Constant)
                        and isinstance(element.value, str)
                    )
        return names

    @staticmethod
    def module_name_of(leaf: str) -> str:
        """Return the owning module name of a leaf for comparison.

        Returns:
            The resulting ``str``.

        """
        return leaf

    @staticmethod
    def _inside_family(file_path: Path, family_dir: str) -> bool:
        """Return whether one file lives inside the family's own tree.

        Returns:
            Whether one file lives inside the family's own tree.

        """
        return family_dir in file_path.parts

    @staticmethod
    def _partition_sibling_clauses(
        node: ast.ImportFrom,
        leaf_by_name: t.MappingKV[str, str],
    ) -> tuple[list[str], MutableMapping[str, list[str]]]:
        """Split one sibling binding into kept clauses and per-leaf moves.

        Returns:
            The resulting ``tuple[list[str], MutableMapping[str, list[str]]]``:
            the clauses that stay on the family init, then the clauses each
            defining leaf module re-owns.

        """
        kept_clauses: list[str] = []
        moved: MutableMapping[str, list[str]] = defaultdict(list)
        for alias in node.names:
            clause = (
                alias.name
                if alias.asname is None
                else f"{alias.name} as {alias.asname}"
            )
            leaf = leaf_by_name.get(alias.name)
            # A leaf equal to this file's own module means the name is
            # defined or re-exported right here: no rewrite can own it.
            if leaf is None or FlextInfraImportNormalization.module_name_of(leaf):
                kept_clauses.append(clause)
            else:
                moved[leaf].append(clause)
        return kept_clauses, moved

    @classmethod
    def _self_family_import_edit(
        cls,
        node: ast.stmt,
        sibling_module: str,
        leaf_by_name: t.MappingKV[str, str],
        parents: t.MappingKV[int, ast.AST],
        lines: t.StrSequence,
    ) -> tuple[int, int, t.StrSequence] | None:
        """Return the unflatten edit for one import, or ``None`` when it stays.

        Returns:
            The resulting ``tuple[int, int, t.StrSequence] | None``.

        """
        if not isinstance(node, ast.ImportFrom) or node.level or node.module is None:
            return None
        if not cls._at_module_level(node, parents):
            return None
        if node.module != sibling_module:
            return None
        kept_clauses, moved = cls._partition_sibling_clauses(node, leaf_by_name)
        if not moved:
            return None
        indent = cls._line_indent(lines[node.lineno - 1])
        replacement: list[str] = []
        if kept_clauses:
            replacement.append(
                f"{indent}from {node.module} import {', '.join(kept_clauses)}",
            )
        for leaf, clauses in sorted(moved.items()):
            replacement.append(f"{indent}from {leaf} import {', '.join(clauses)}")
        return (node.lineno, cls._end_line(node), tuple(replacement))

    @classmethod
    def _self_family_unflatten_edits(
        cls,
        tree: ast.Module,
        source: str,
        package: str,
        file_path: Path,
        project_root: Path,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Point a family member's sibling imports at their defining modules.

        A module inside ``pkg.<family>/`` binding a sibling name through
        ``from pkg.<family> import X`` closes the family init into a cycle
        while it assembles; the leaf module the family init's own
        ``TYPE_CHECKING`` import names is the cycle-free owner of the
        binding.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        family_dir = next(
            (
                part
                for part in file_path.parts
                if part.lstrip("_") in c.Infra.FAMILY_LETTER
            ),
            None,
        )
        if family_dir is None:
            return ()
        leaf_by_name = cls._family_leaf_map(project_root, package, family_dir)
        if not leaf_by_name:
            return ()
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        lines = source.splitlines()
        parents = cls._parent_map(tree)
        sibling_module = f"{package}.{family_dir}"
        for node in cls._iter_imports(tree):
            edit = cls._self_family_import_edit(
                node,
                sibling_module,
                leaf_by_name,
                parents,
                lines,
            )
            if edit is not None:
                edits.append(edit)
        return edits

    @classmethod
    def _family_leaf_map(
        cls,
        project_root: Path,
        package: str,
        family_dir: str,
    ) -> t.MappingKV[str, str]:
        """Read one family init's name -> defining-module map.

        Returns:
            The resulting ``t.MappingKV[str, str]``.

        """
        base = project_root / "src" if (project_root / "src").is_dir() else project_root
        init = base / package / family_dir / "__init__.py"
        if not init.is_file():
            return {}
        try:
            tree = ast.parse(init.read_text(encoding=c.Cli.ENCODING_DEFAULT))
        except (OSError, SyntaxError):
            return {}
        mapping: MutableMapping[str, str] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if not node.module.startswith(f"{package}.{family_dir}"):
                continue
            for alias in node.names:
                mapping[alias.asname or alias.name] = node.module
        return mapping

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
        scan = _DemotionScan(
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
            if not cls._demotion_scope(node, package, scan.parents):
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

    @staticmethod
    def _demotion_scope(
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
        if FlextInfraImportNormalization._inside_type_checking(node, parents):
            return False
        return FlextInfraImportNormalization._at_module_level(node, parents)

    @classmethod
    def _collect_demotion_edits(
        cls,
        scan: _DemotionScan,
        node: ast.stmt,
        insertions: MutableMapping[int, MutableMapping[str, t.Infra.StrSet]],
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]],
    ) -> None:
        """Record one subject import's demotion plan into insertions/edits."""
        if not isinstance(node, ast.ImportFrom):
            return
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
        scan: _DemotionScan,
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
        if node.module is None:
            return False, bound
        reverse_edge = cls._source_is_later_layer(
            node.module,
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
            node.module,
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

    @staticmethod
    def _insertion_edits(
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
            indent = FlextInfraImportNormalization._function_body_indent(
                lines,
                anchor,
            )
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
            and bound in c.Infra.LETTER_ORDER
            and c.Infra.LETTER_ORDER[bound] >= module_rank
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
                if part.lstrip("_") in c.Infra.FAMILY_LETTER
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
        if len(names) == c.Infra.FAMILY_PATH_DEPTH:
            rank = c.Infra.FAMILY_RANK.get(tail.lstrip("_"))
            if rank is not None:
                return rank > module_rank
        if tail in {"api", "cli"}:
            return c.Infra.FACADE_RANK[tail] > module_rank
        if "services" in names or tail == "base":
            return (9 if "services" in names else 8) > module_rank
        return module_rank < c.Infra.DEFAULT_LAYER_RANK

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

    @staticmethod
    def _use_sites(tree: ast.Module, name: str) -> list[ast.Name]:
        """Return every load of one binding in the module.

        Returns:
            The resulting ``list[ast.Name]``.

        """
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and node.id == name
            and isinstance(node.ctx, ast.Load)
        ]

    @classmethod
    def _demotable(
        cls,
        site: ast.Name,
        parents: t.MappingKV[int, ast.AST],
        frozen: set[int],
    ) -> bool:
        """Return whether one use site can move inside its using function.

        Returns:
            Whether one use site can move inside its using function.

        """
        if id(site) in frozen:
            return False
        node: ast.AST | None = site
        while node is not None:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                return True
            node = parents.get(id(node))
        return False

    @staticmethod
    def _freeze_function_decorators(
        frozen: set[int],
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        """Freeze one function's decorators, defaults, and annotations."""
        for decorator in node.decorator_list:
            frozen.update(id(sub) for sub in ast.walk(decorator))
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                frozen.update(id(sub) for sub in ast.walk(default))
        if node.returns is not None:
            frozen.update(id(sub) for sub in ast.walk(node.returns))
        for argument in (
            *node.args.args,
            *node.args.posonlyargs,
            *node.args.kwonlyargs,
        ):
            if argument.annotation is not None:
                frozen.update(id(sub) for sub in ast.walk(argument.annotation))

    @classmethod
    def _frozen_node_ids(cls, tree: ast.Module) -> set[int]:
        """Mark every subtree that must stay at module definition time.

        Class bases and keywords, decorators, signature defaults and
        annotations all evaluate when their statement executes, so a name
        used there can never move inside a function body.

        Returns:
            The resulting ``set[int]`` of frozen ``id()`` node identifiers.

        """
        frozen: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    frozen.update(id(sub) for sub in ast.walk(base))
                for keyword in node.keywords:
                    frozen.update(id(sub) for sub in ast.walk(keyword.value))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cls._freeze_function_decorators(frozen, node)
        return frozen

    @classmethod
    def _function_anchors(
        cls,
        sites: t.SequenceOf[ast.Name],
        parents: t.MappingKV[int, ast.AST],
    ) -> list[int]:
        """Return the body-insertion line of each site's outermost function.

        Returns:
            The resulting ``list[int]``.

        """
        anchors: set[int] = set()
        for site in sites:
            outermost: ast.FunctionDef | ast.AsyncFunctionDef | None = None
            node: ast.AST | None = site
            while node is not None:
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    outermost = node
                node = parents.get(id(node))
            if outermost is not None:
                anchors.add(cls._body_insert_line(outermost))
        return sorted(anchors)

    @staticmethod
    def _body_insert_line(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        """Return the first body line after a docstring, when one exists.

        Returns:
            The resulting ``int``.

        """
        body = function_node.body
        lead = body[0]
        is_docstring = (
            isinstance(lead, ast.Expr)
            and isinstance(lead.value, ast.Constant)
            and isinstance(lead.value.value, str)
        )
        if is_docstring and len(body) > 1:
            return body[1].lineno
        if is_docstring:
            return (lead.end_lineno or lead.lineno) + 1
        return lead.lineno

    @classmethod
    def _function_body_indent(cls, lines: t.StrSequence, insert_line: int) -> str:
        """Return the body indent implied by one function insertion line.

        Returns:
            The resulting ``str``.

        """
        if insert_line <= len(lines):
            reference = lines[insert_line - 1]
            if reference.strip():
                return cls._line_indent(reference)
        for offset in range(1, 8):
            index = insert_line - 1 - offset
            if index >= 0 and lines[index].strip():
                return f"{cls._line_indent(lines[index])}    "
        return "    "

    @classmethod
    def _declared_family_rank(cls, file_path: Path) -> int | None:
        """Return the family rank one file's path declares, when it lives in one.

        Returns:
            The resulting ``int | None``.

        """
        for part in file_path.parts:
            rank = c.Infra.FAMILY_RANK.get(part.lstrip("_"))
            if rank is not None and (
                part.startswith("_") or part in c.Infra.FAMILY_RANK
            ):
                return rank
        return None

    @classmethod
    def _module_layer_rank(cls, file_path: Path) -> int:
        """Return the module's own layer rank over the declared order.

        Returns:
            The resulting ``int``.

        """
        family_rank = cls._declared_family_rank(file_path)
        if family_rank is not None:
            return family_rank
        name = file_path.name
        settings_here = "_settings" in file_path.parts
        config_here = "_config" in file_path.parts
        layers: t.SequenceOf[tuple[bool, int]] = (
            (name in {"settings.py", "_settings.py"} or settings_here, 0),
            (name in {"config.py", "_config.py"} or config_here, 1),
            (name == "base.py", 8),
            ("services" in file_path.parts, 9),
            (name == "api.py", 10),
            (name == "cli.py", 11),
        )
        return next(
            (rank for matched, rank in layers if matched),
            c.Infra.DEFAULT_LAYER_RANK,
        )

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
        if len(names) < c.Infra.LEAF_PATH_DEPTH or names[0] != package:
            return module
        family = names[1].lstrip("_")
        if family not in c.Infra.FAMILY_LETTER:
            return module
        if bound in family_exports.get(family, set()):
            return f"{names[0]}.{names[1]}"
        return module

    # -- rule 2: foundation routing for the settings/config layers -------------

    @classmethod
    def _foundation_routing_edits(
        cls,
        tree: ast.Module,
        source: str,
        package: str,
        file_path: Path,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Route a settings/config layer's eager own letters to the foundation.

        The settings and config layers are strictly first in the declared
        order: nothing project-owned is earlier, so an own-package letter may
        never bind eagerly there. A letter the module-level structure still
        needs routes to ``from flext_core import <letter>`` when the
        foundation publishes it (its letters are the fleet's shared base);
        the flext-core package itself has no foundation above it and keeps
        its own letters lazy.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        if package == "flext_core" or cls._module_layer_rank(file_path) > 1:
            return ()
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        lines = source.splitlines()
        parents = cls._parent_map(tree)
        for node in cls._iter_imports(tree):
            if (
                not isinstance(node, ast.ImportFrom)
                or node.level
                or node.module != package
            ):
                continue
            if not cls._at_module_level(node, parents):
                continue
            letters = [
                alias.asname or alias.name
                for alias in node.names
                if alias.asname is None and alias.name in c.Infra.LETTER_ORDER
            ]
            if not letters or len(letters) != len(node.names):
                continue
            indent = cls._line_indent(lines[node.lineno - 1])
            ordered = sorted(letters, key=lambda letter: c.Infra.LETTER_ORDER[letter])
            edits.append(
                (
                    node.lineno,
                    cls._end_line(node),
                    (f"{indent}from flext_core import {', '.join(ordered)}",),
                ),
            )
        return edits

    # -- shared helpers -------------------------------------------------

    @staticmethod
    def _parse(source: str) -> ast.Module | None:
        """Parse one source text, tolerating syntax the engine cannot own.

        Returns:
            The resulting ``ast.Module | None``.

        """
        try:
            return ast.parse(source)
        except SyntaxError:
            return None

    @staticmethod
    def _iter_imports(tree: ast.Module) -> t.SequenceOf[ast.stmt]:
        """Return every import statement anywhere in the module.

        Returns:
            The resulting ``t.SequenceOf[ast.stmt]``.

        """
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]

    @staticmethod
    def _parent_map(tree: ast.Module) -> t.MappingKV[int, ast.AST]:
        """Map every node id to its parent node.

        Returns:
            The resulting ``t.MappingKV[int, ast.AST]``.

        """
        parents: MutableMapping[int, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[id(child)] = node
        return parents

    @classmethod
    def _owning_block(
        cls,
        node: ast.AST,
        parents: t.MappingKV[int, ast.AST],
    ) -> ast.AST:
        """Return the module or ``if`` block that owns one import statement.

        Returns:
            The resulting ``ast.AST``.

        """
        current: ast.AST | None = node
        while current is not None:
            parent = parents.get(id(current))
            if isinstance(parent, ast.Module | ast.If):
                return parent
            current = parent
        return node

    @classmethod
    def _at_module_level(
        cls,
        node: ast.AST,
        parents: t.MappingKV[int, ast.AST],
    ) -> bool:
        """Return whether one import statement executes at module import time.

        Only statements whose scope chain reaches the module (optionally
        through ``if`` blocks) run at import time; a class-body or
        function-body import owns a narrower scope and is never merged or
        demoted across it.

        Returns:
            Whether one import statement executes at module import time.

        """
        current: ast.AST | None = node
        while current is not None:
            if isinstance(
                current,
                ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef,
            ):
                return False
            current = parents.get(id(current))
        return True

    @classmethod
    def _inside_type_checking(
        cls,
        node: ast.AST,
        parents: t.MappingKV[int, ast.AST],
    ) -> bool:
        """Return whether the statement sits under an ``if TYPE_CHECKING:``.

        Returns:
            Whether the statement sits under an ``if TYPE_CHECKING:``.

        """
        current: ast.AST | None = node
        while current is not None:
            if isinstance(current, ast.If):
                names = " ".join(
                    getattr(sub, "id", "")
                    for sub in ast.walk(current.test)
                    if isinstance(sub, ast.Name)
                )
                if "TYPE_CHECKING" in names:
                    return True
            current = parents.get(id(current))
        return False

    @staticmethod
    def _end_line(node: ast.stmt) -> int:
        """Return one statement's inclusive end line.

        Returns:
            The resulting ``int``.

        """
        return getattr(node, "end_lineno", None) or getattr(node, "lineno", 1)

    @staticmethod
    def _line_indent(line: str) -> str:
        """Return one line's leading whitespace.

        Returns:
            The resulting ``str``.

        """
        return line[: len(line) - len(line.lstrip())]

    @classmethod
    def _apply_edits(
        cls,
        source: str,
        edits: t.SequenceOf[tuple[int, int, t.StrSequence]],
    ) -> str | None:
        """Apply non-overlapping line edits; ``None`` when they collide.

        A span ``(n, n - 1)`` inserts BEFORE line ``n``; a span ``(a, b)``
        with ``b >= a`` replaces lines ``a..b``; a span with an empty
        replacement deletes its lines.

        Returns:
            The resulting ``str | None``.

        """
        lines = source.splitlines()
        ordered = sorted(edits, key=operator.itemgetter(0, 1), reverse=True)
        last_start: int | None = None
        for start, end, replacement in ordered:
            if last_start is not None and end >= last_start:
                return None
            last_start = start
            if not replacement:
                if end >= start:
                    lines[start - 1 : end] = ()
                continue
            if end < start:
                lines[start - 1 : start - 1] = list(replacement)
                continue
            lines[start - 1 : end] = list(replacement)
        return "\n".join(lines).rstrip() + "\n"

    @classmethod
    def _locate(cls, project_root: Path, file_path: Path) -> tuple[str, str] | None:
        """Return the (package, dotted module) of one source file.

        Returns:
            The resulting ``tuple[str, str] | None``.

        """
        base = project_root / "src"
        if not base.is_dir():
            return None
        try:
            relative = file_path.resolve().relative_to(base.resolve())
        except ValueError:
            return None
        parts = relative.with_suffix("").parts
        if not parts or parts[-1] == "__init__":
            parts = parts[:-1]
        if len(parts) < 1 or not (base / parts[0] / "__init__.py").is_file():
            return None
        return parts[0], ".".join(parts)


__all__: list[str] = ["FlextInfraImportNormalization"]
