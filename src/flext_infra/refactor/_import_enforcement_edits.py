"""Canonical-form rewrite categories (rules 3-4) for import normalization.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import c, t
from flext_infra.refactor._import_enforcement_ast import (
    FlextInfraImportNormalizationAstMixin,
)


class FlextInfraImportNormalizationEditsMixin(
    FlextInfraImportNormalizationAstMixin,
):
    """Absolute-form, root-combined, and family-flatten rewrite categories."""

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
            if leaf is None or FlextInfraImportNormalizationEditsMixin.module_name_of(
                leaf,
            ):
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
