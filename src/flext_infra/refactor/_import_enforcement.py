"""Canonical FLEXT import-form enforcement engine.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import operator
from collections import defaultdict
from collections.abc import MutableMapping
from pathlib import Path
from typing import ClassVar

from flext_infra import c, t


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
    """

    LETTER_ORDER: ClassVar[t.MappingKV[str, int]] = {
        "c": 2,
        "t": 3,
        "p": 4,
        "m": 5,
        "u": 6,
    }
    LETTER_RENDER_ORDER: ClassVar[t.StrSequence] = ("c", "m", "p", "t", "u")
    FAMILY_LETTER: ClassVar[t.MappingKV[str, str]] = {
        "constants": "c",
        "typings": "t",
        "protocols": "p",
        "models": "m",
        "utilities": "u",
    }
    FAMILY_RANK: ClassVar[t.MappingKV[str, int]] = {
        "constants": 2,
        "typings": 3,
        "protocols": 4,
        "models": 5,
        "utilities": 6,
    }
    FACADE_RANK: ClassVar[t.MappingKV[str, int]] = {"api": 10, "cli": 11}
    MAX_PASSES: ClassVar[int] = 24

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
        for _ in range(cls.MAX_PASSES):
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
                in cls.LETTER_ORDER
            }
            if not letters:
                continue
            ordered = [
                letter for letter in cls.LETTER_RENDER_ORDER if letter in letters
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
            len(names) == 2
            and names[0] == package
            and names[1].lstrip("_") in cls.FAMILY_LETTER
        ):
            root_form = False
        else:
            return None
        aliases: list[tuple[str, str | None]] = []
        for alias in node.names:
            if alias.asname is None:
                # Root or facade-file form: the imported name IS the letter.
                if alias.name in cls.LETTER_ORDER:
                    aliases.append((alias.name, None))
                    continue
                return None
            if (
                root_form
                and alias.name in cls.FAMILY_LETTER
                and alias.asname in cls.LETTER_ORDER
            ):
                aliases.append((alias.name, alias.asname))
                continue
            return None
        return aliases or None

    # -- rule 4: flattened family paths -----------------------------------------------

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
            if (
                not isinstance(node, ast.ImportFrom)
                or node.level
                or node.module is None
            ):
                continue
            names = node.module.split(".")
            if len(names) < 3 or names[0] != package:
                continue
            family = names[1].lstrip("_")
            if family not in cls.FAMILY_LETTER:
                continue
            # No member of the family may bind a sibling name through the
            # family init: the init is still assembling while its own modules
            # load, so the flattened form closes a self-family import cycle
            # (its own deep imports are the publication form itself).
            if cls._inside_family(file_path, names[1]):
                continue
            exported = family_exports.get(family)
            if not exported:
                continue
            kept_clauses: list[str] = []
            moved_clauses: list[str] = []
            for alias in node.names:
                clause = (
                    alias.name
                    if alias.asname is None
                    else f"{alias.name} as {alias.asname}"
                )
                if alias.name in exported:
                    moved_clauses.append(clause)
                else:
                    kept_clauses.append(clause)
            if not moved_clauses:
                continue
            indent = cls._line_indent(lines[node.lineno - 1])
            replacement: list[str] = []
            if kept_clauses:
                replacement.append(
                    f"{indent}from {node.module} import {', '.join(kept_clauses)}",
                )
            replacement.append(
                f"{indent}from {names[0]}.{names[1]} import {', '.join(moved_clauses)}",
            )
            edits.append((node.lineno, cls._end_line(node), tuple(replacement)))
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
        for family in cls.FAMILY_LETTER:
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
    def module_name_of(file_path: Path, leaf: str) -> str:
        """Return the owning module name of a file for leaf comparison.

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
            (part for part in file_path.parts if part.lstrip("_") in cls.FAMILY_LETTER),
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
        for node in cls._iter_imports(tree):
            if (
                not isinstance(node, ast.ImportFrom)
                or node.level
                or node.module is None
            ):
                continue
            if not cls._at_module_level(node, parents):
                continue
            names = node.module.split(".")
            if len(names) != 2 or names[0] != package:
                continue
            if names[1] != family_dir:
                continue
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
                if leaf is None or cls.module_name_of(file_path, leaf):
                    kept_clauses.append(clause)
                else:
                    moved[leaf].append(clause)
            if not moved:
                continue
            indent = cls._line_indent(lines[node.lineno - 1])
            replacement: list[str] = []
            if kept_clauses:
                replacement.append(
                    f"{indent}from {node.module} import {', '.join(kept_clauses)}",
                )
            for leaf, clauses in sorted(moved.items()):
                replacement.append(f"{indent}from {leaf} import {', '.join(clauses)}")
            edits.append((node.lineno, cls._end_line(node), tuple(replacement)))
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
        parents = cls._parent_map(tree)
        frozen = cls._frozen_node_ids(tree)
        module_rank = cls._module_layer_rank(file_path)
        insertions: MutableMapping[
            int,
            MutableMapping[str, t.Infra.StrSet],
        ] = defaultdict(lambda: defaultdict(set))
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        for node in cls._iter_imports(tree):
            if not isinstance(node, ast.ImportFrom) or node.level:
                continue
            if node.module is None:
                continue
            top_module = node.module.split(".", maxsplit=1)[0]
            if top_module != package and not top_module.startswith("flext_"):
                continue
            if cls._inside_type_checking(node, parents):
                continue
            if not cls._at_module_level(node, parents):
                continue
            demotable: list[tuple[str, str]] = []
            kept: list[str] = []
            for alias in node.names:
                bound = alias.asname or alias.name
                reverse_edge = cls._source_is_later_layer(
                    node.module or "",
                    package,
                    module_rank,
                    file_path,
                )
                if not cls._demotion_candidate(
                    alias,
                    bound,
                    package,
                    module_rank,
                    reverse_edge,
                ):
                    kept.append(bound)
                    continue
                sites = cls._use_sites(tree, bound)
                if not sites:
                    if reverse_edge or cls._is_late_letter(
                        alias,
                        bound,
                        package,
                        module_rank,
                    ):
                        # An unused late letter at module level is never a
                        # typing reference: binding it eagerly only risks the
                        # self-facade cycle (u inside the utilities tree).
                        continue
                    kept.append(bound)
                    continue
                if not all(cls._demotable(site, parents, frozen) for site in sites):
                    kept.append(bound)
                    continue
                demotable.append((alias.name, bound))
                target_module = cls._canonical_lazy_module(
                    node.module,
                    alias.name,
                    package,
                    family_exports,
                )
                for anchor in cls._function_anchors(sites, parents):
                    insertions[anchor][target_module].add(
                        alias.name
                        if alias.asname is None
                        else f"{alias.name} as {alias.asname}",
                    )
            if not demotable:
                continue
            if kept:
                clauses = ", ".join(
                    alias.name
                    if alias.asname is None
                    else f"{alias.name} as {alias.asname}"
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
            else:
                edits.append((node.lineno, cls._end_line(node), ()))
        edits.extend(cls._guard_cleanup_edits(tree, lines, parents, frozen, insertions))
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
        package: str,
        module_rank: int,
    ) -> bool:
        """Return whether one binding is an own-package letter at/after its layer.

        Returns:
            Whether one binding is an own-package letter at/after its layer.

        """
        return (
            alias.asname is None
            and bound in FlextInfraImportNormalization.LETTER_ORDER
            and FlextInfraImportNormalization.LETTER_ORDER[bound] >= module_rank
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
            (part for part in file_path.parts if part.lstrip("_") in cls.FAMILY_LETTER),
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
        if len(names) == 2:
            rank = cls.FAMILY_RANK.get(tail.lstrip("_"))
            if rank is not None:
                return rank > module_rank
        if tail in {"api", "cli"}:
            return cls.FACADE_RANK[tail] > module_rank
        if "services" in names or tail == "base":
            return (9 if "services" in names else 8) > module_rank
        return module_rank < 7

    @classmethod
    def _demotion_candidate(
        cls,
        alias: ast.alias,
        bound: str,
        package: str,
        module_rank: int,
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
        return cls._is_late_letter(alias, bound, package, module_rank)

    @classmethod
    def _guard_cleanup_edits(
        cls,
        tree: ast.Module,
        lines: t.StrSequence,
        parents: t.MappingKV[int, ast.AST],
        frozen: t.Infra.StrSet,
        insertions: MutableMapping[int, MutableMapping[str, t.Infra.StrSet]],
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Remove ``try/except ImportError`` import guards; rebind at use.

        A guarded name the module still uses at definition time falls back to
        a plain module-level import line at the guard's position.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        fallbacks: list[tuple[str, t.StrSequence]] = []
        for node in tree.body:
            if not isinstance(node, ast.Try):
                continue
            if not node.handlers or not all(
                isinstance(handler.type, ast.Name) and handler.type.id == "ImportError"
                for handler in node.handlers
            ):
                continue
            guarded: list[tuple[str, str]] = []
            for statement in node.body:
                if isinstance(statement, ast.ImportFrom) and statement.module:
                    guarded.extend(
                        (statement.module, alias.asname or alias.name)
                        for alias in statement.names
                    )
            if not guarded:
                continue
            fallback_by_module: MutableMapping[str, set[str]] = defaultdict(set)
            for module, bound in guarded:
                sites = cls._use_sites(tree, bound)
                if sites and all(
                    cls._demotable(site, parents, frozen) for site in sites
                ):
                    for anchor in cls._function_anchors(sites, parents):
                        insertions[anchor][module].add(bound)
                else:
                    fallback_by_module[module].add(bound)
            for module, names in fallback_by_module.items():
                fallbacks.append((module, tuple(sorted(names))))
            edits.append((node.lineno, cls._end_line(node), ()))
        for module, names in fallbacks:
            edits.append(cls._guard_fallback_edit(tree, lines, module, names))
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
        frozen: t.Infra.StrSet,
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

    @classmethod
    def _frozen_node_ids(cls, tree: ast.Module) -> t.Infra.StrSet:
        """Mark every subtree that must stay at module definition time.

        Class bases and keywords, decorators, signature defaults and
        annotations all evaluate when their statement executes, so a name
        used there can never move inside a function body.

        Returns:
            The resulting ``t.Infra.StrSet``.

        """
        frozen: t.Infra.StrSet = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    frozen.update(id(sub) for sub in ast.walk(base))
                for keyword in node.keywords:
                    frozen.update(id(sub) for sub in ast.walk(keyword.value))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
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
        anchors: t.Infra.StrSet = set()
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
    def _module_layer_rank(cls, file_path: Path) -> int:
        """Return the module's own layer rank over the declared order.

        Returns:
            The resulting ``int``.

        """
        for part in file_path.parts:
            rank = cls.FAMILY_RANK.get(part.lstrip("_"))
            if rank is not None and (part.startswith("_") or part in cls.FAMILY_RANK):
                return rank
        name = file_path.name
        if name in {"settings.py", "_settings.py"} or "_settings" in file_path.parts:
            return 0
        if name in {"config.py", "_config.py"} or "_config" in file_path.parts:
            return 1
        if name == "base.py":
            return 8
        if "services" in file_path.parts:
            return 9
        if name == "api.py":
            return 10
        if name == "cli.py":
            return 11
        return 7

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
        if len(names) < 3 or names[0] != package:
            return module
        family = names[1].lstrip("_")
        if family not in cls.FAMILY_LETTER:
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
                if alias.asname is None and alias.name in cls.LETTER_ORDER
            ]
            if not letters or len(letters) != len(node.names):
                continue
            indent = cls._line_indent(lines[node.lineno - 1])
            edits.append(
                (
                    node.lineno,
                    cls._end_line(node),
                    (
                        f"{indent}from flext_core import {', '.join(sorted(letters, key=cls.LETTER_ORDER.get))}",
                    ),
                ),
            )
        return edits

    # -- shared helpers ------------------------------------------------------------------

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
