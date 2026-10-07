"""Public-facade discovery for semantic private-import rewrites.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from importlib.util import find_spec, resolve_name
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c
from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysis

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

    from flext_infra import t


class FlextInfraUtilitiesPrivateImportFacades:
    """Derive public paths from live facade inheritance, never a registry."""

    @staticmethod
    def source_modules(
        sources: t.MappingKV[Path, str],
        statements: t.SequenceOf[str],
    ) -> MutableMapping[str, t.Pair[str, bool]]:
        """Index editable sources and referenced installed packages without imports.

        Installed files are discovery inputs only. Resolving a top-level spec
        never imports its package initializer or dependency business modules.

        Returns:
            The resulting ``MutableMapping[str, t.Pair[str, bool]]``.

        Raises:
            ValueError: If ambiguous source module identity; or if ambiguous installed
                module identity.

        """
        modules: MutableMapping[str, t.Pair[str, bool]] = {}
        for path, source in sorted(sources.items()):
            indices = [
                index
                for index, part in enumerate(path.parts)
                if part == c.Infra.DEFAULT_SRC_DIR
            ]
            if not indices:
                continue
            parts = path.parts[indices[-1] + 1 :]
            module = ".".join(
                parts[:-1]
                if path.name == c.Infra.INIT_PY
                else (*parts[:-1], path.stem),
            )
            if not module:
                continue
            if module in modules:
                msg = f"ambiguous source module identity: {module}"
                raise ValueError(msg)
            modules[module] = (source, path.name == c.Infra.INIT_PY)
        supplied = {module.split(".")[0] for module in modules}
        referenced = {
            node.module.split(".")[0]
            for statement in statements
            for node in ast.walk(ast.parse(statement))
            if isinstance(node, ast.ImportFrom) and not node.level and node.module
        }
        for package in sorted(referenced - supplied):
            spec = find_spec(package)
            if spec is None or spec.submodule_search_locations is None:
                continue
            for location in spec.submodule_search_locations:
                package_root = Path(location)
                for path in sorted(package_root.rglob("*.py")):
                    parts = path.relative_to(package_root).parts
                    suffix = (
                        parts[:-1]
                        if path.name == c.Infra.INIT_PY
                        else (*parts[:-1], path.stem)
                    )
                    module = ".".join((package, *suffix))
                    if module in modules:
                        msg = f"ambiguous installed module identity: {module}"
                        raise ValueError(msg)
                    modules[module] = (
                        path.read_text(encoding="utf-8"),
                        path.name == c.Infra.INIT_PY,
                    )
        return modules

    @staticmethod
    def reachable_sources(
        sources: t.MappingKV[str, t.Pair[str, bool]],
        statements: t.SequenceOf[str],
    ) -> t.MappingKV[str, t.Pair[str, bool]]:
        """Keep the importers that can expose a requested private module.

        An installed distribution can contain unrelated modules with invalid
        imports. Their declarations have no bearing on a cutover whose target
        is reachable through a different public facade.

        Returns:
            The resulting ``t.MappingKV[str, t.Pair[str, bool]]``.

        """
        reverse: MutableMapping[str, set[str]] = {}
        for module, (source, is_package) in sources.items():
            package = module if is_package else module.rpartition(".")[0]
            for node in ast.walk(ast.parse(source, filename=module)):
                for imported in (
                    FlextInfraUtilitiesPrivateImportFacades._statement_imported_modules(
                        node,
                        package,
                        sources,
                    )
                ):
                    FlextInfraUtilitiesPrivateImportFacades._register_importer(
                        reverse,
                        sources,
                        imported,
                        module,
                    )
        reachable = FlextInfraUtilitiesPrivateImportFacades._transitive_reachable(
            reverse,
            {
                node.module
                for statement in statements
                for node in ast.walk(ast.parse(statement))
                if isinstance(node, ast.ImportFrom) and not node.level and node.module
            },
        )
        return {
            module: source for module, source in sources.items() if module in reachable
        }

    @staticmethod
    def _statement_imported_modules(
        node: ast.AST,
        package: str,
        sources: t.MappingKV[str, t.Pair[str, bool]],
    ) -> t.VariadicTuple[str]:
        """Return the absolute modules one import statement connects to.

        Returns:
            The resulting ``t.VariadicTuple[str]``.

        """
        imported_modules: set[str] = set()
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level > len(package.split(".")):
                # This import has no absolute module identity. It cannot
                # connect the module to any requested private owner.
                return ()
            imported = (
                resolve_name("." * node.level + (node.module or ""), package)
                if node.level
                else node.module or ""
            )
            imported_modules.add(imported)
            imported_modules.update(
                f"{imported}.{alias.name}"
                for alias in node.names
                if f"{imported}.{alias.name}" in sources
            )
        return tuple(imported_modules)

    @staticmethod
    def _register_importer(
        reverse: t.MutableMappingKV[str, set[str]],
        sources: t.MappingKV[str, t.Pair[str, bool]],
        imported: str,
        module: str,
    ) -> None:
        """Record one importer edge and every package ancestor it exposes.

        Importing a package's child can expose a name exported by the parent
        package: keep that importer reachable when the requested private import
        names the package itself.
        """
        reverse.setdefault(imported, set()).add(module)
        parent = imported.rpartition(".")[0]
        while parent:
            if parent in sources and sources[parent][1]:
                reverse.setdefault(parent, set()).add(module)
            parent = parent.rpartition(".")[0]

    @staticmethod
    def _transitive_reachable(
        reverse: t.MappingKV[str, set[str]],
        seeds: t.IterableOf[str],
    ) -> set[str]:
        """Walk the reverse-import graph from one seed set.

        Returns:
            The resulting ``set[str]``.

        """
        reachable = set(seeds)
        pending = list(seeds)
        while pending:
            for importer in reverse.get(pending.pop(), set()):
                if importer not in reachable:
                    reachable.add(importer)
                    pending.append(importer)
        return reachable

    @staticmethod
    def declared_exports(
        sources: t.MappingKV[str, t.Pair[str, bool]],
    ) -> t.Pair[MutableMapping[str, set[str]], MutableMapping[str, set[str]]]:
        """Index declared public exports and module-scope import identities.

        Returns:
            The resulting ``t.Pair[MutableMapping[str, set[str]], MutableMapping[str,
                set[str]]]``.

        """
        bindings: MutableMapping[str, set[str]] = {}
        exports: MutableMapping[str, set[str]] = {}
        for module, (source, is_package) in sorted(sources.items()):
            package = module if is_package else module.rpartition(".")[0]
            tree = ast.parse(source, filename=module)
            public_names = FlextInfraUtilitiesRopeAnalysis.public_export_names_source(
                source,
            )
            lazy_exports, lazy_name = (
                FlextInfraUtilitiesRopeAnalysis.lazy_public_exports_source(source)
            )
            collector = FlextInfraUtilitiesPrivateImportFacades._ExportBindingCollector(
                bindings,
                package=package,
                module=module,
                lazy_exports=lazy_exports,
                lazy_name=lazy_name,
            )
            collector.collect(tree.body)
            if not any(part.startswith("_") for part in module.split(".")):
                exports.setdefault(module.split(".")[0], set()).update(
                    f"{module}.{name}"
                    for name in public_names
                    if not name.startswith("_") and f"{module}.{name}" in bindings
                )
        return bindings, exports

    class _ExportBindingCollector:
        """Index one module's import and declaration bindings for exports."""

        def __init__(
            self,
            bindings: t.MutableMappingKV[str, set[str]],
            *,
            package: str,
            module: str,
            lazy_exports: t.StrSequence,
            lazy_name: str,
        ) -> None:
            self.bindings = bindings
            self.package = package
            self.module = module
            self.lazy_exports = lazy_exports
            self.lazy_name = lazy_name

        def collect(self, statements: t.SequenceOf[ast.stmt]) -> None:
            """Index every binding one statement suite declares."""
            for node in statements:
                if isinstance(node, ast.ImportFrom):
                    self._bind_import(node)
                elif isinstance(
                    node,
                    ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
                ):
                    self._bind_definition(node)
                elif isinstance(node, ast.Assign | ast.AnnAssign):
                    self._bind_assignment(node)
                elif isinstance(node, ast.If):
                    self._collect_branches(node)

        def _bind_import(self, node: ast.ImportFrom) -> None:
            """Bind every non-star import alias to its resolved source module."""
            imported_module = (
                resolve_name("." * node.level + (node.module or ""), self.package)
                if node.level
                else node.module or ""
            )
            for imported in node.names:
                if imported.name != "*":
                    self.bindings.setdefault(
                        f"{self.module}.{imported.asname or imported.name}",
                        set(),
                    ).add(f"{imported_module}.{imported.name}")

        def _bind_definition(
            self,
            node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        ) -> None:
            """Bind one runtime declaration over any earlier imported name.

            A runtime declaration replaces an earlier imported name in the
            same module. Keeping both fabricated an ambiguity for the
            canonical ``from upstream import u; u = Facade`` shape.
            """
            identity = f"{self.module}.{node.name}"
            self.bindings[identity] = {identity}

        def _bind_assignment(self, node: ast.Assign | ast.AnnAssign) -> None:
            """Bind one module-level assignment to its last declaration.

            Module assignments are runtime rebinding, not an additional
            possible source: the last declaration is the single Python
            authority for the public name.
            """
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    identity = f"{self.module}.{target.id}"
                    destination = (
                        f"{self.module}.{node.value.id}"
                        if isinstance(node.value, ast.Name)
                        else identity
                    )
                    self.bindings[identity] = {destination}

        def _collect_branches(self, node: ast.If) -> None:
            """Enter conditional branches outside type-only lazy facades."""
            type_only = (
                isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"
            )
            if not type_only or self.lazy_exports or self.lazy_name:
                self.collect(node.body)
            self.collect(node.orelse)

    @classmethod
    def declared_public_reference(
        cls,
        qualified: str,
        bindings: t.MappingKV[str, set[str]],
        exports: t.MappingKV[str, set[str]],
    ) -> t.Pair[str, str] | None:
        """Resolve re-export chains by identity, preferring an explicit root ABI.

        Returns:
            The resulting ``t.Pair[str, str] | None``.

        Raises:
            ValueError: If ambiguous private symbol identity for; or if ambiguous
                declared public exports for; or if cyclic public export identity; or if
                ambiguous public export identity for.

        """
        expected = cls._export_identities(bindings, qualified, frozenset())
        if len(expected) != 1:
            msg = (
                f"ambiguous private symbol identity for {qualified}: {sorted(expected)}"
            )
            raise ValueError(msg)
        reverse = cls._reverse_bindings(bindings)
        reachable = cls._transitive_reachable(reverse, expected)
        candidates = exports.get(qualified.split(".", maxsplit=1)[0], set()) & reachable
        roots = {candidate for candidate in candidates if candidate.count(".") == 1}
        canonical = roots or candidates
        cls._verify_export_identities(bindings, canonical, expected)
        if len(canonical) > 1:
            msg = (
                f"ambiguous declared public exports for {qualified}: "
                f"{sorted(canonical)}"
            )
            raise ValueError(msg)
        if not canonical:
            return None
        module, _, name = canonical.pop().rpartition(".")
        return module, name

    @classmethod
    def _export_identities(
        cls,
        bindings: t.MappingKV[str, set[str]],
        name: str,
        visiting: frozenset[str],
    ) -> set[str]:
        """Resolve one binding name to its transitive declared identities.

        Returns:
            The resulting ``set[str]``.

        Raises:
            ValueError: If cyclic public export identity.

        """
        if name in visiting:
            msg = f"cyclic public export identity: {name}"
            raise ValueError(msg)
        targets = bindings.get(name, {name})
        resolved: set[str] = set()
        for target in targets:
            if target == name:
                resolved.add(name)
            else:
                resolved.update(
                    cls._export_identities(bindings, target, visiting | {name}),
                )
        return resolved

    @staticmethod
    def _reverse_bindings(
        bindings: t.MappingKV[str, set[str]],
    ) -> t.MutableMappingKV[str, set[str]]:
        """Invert the binding map from targets back to their binding names.

        Returns:
            The resulting ``t.MutableMappingKV[str, set[str]]``.

        """
        reverse: MutableMapping[str, set[str]] = {}
        for binding, targets in bindings.items():
            for target in targets:
                reverse.setdefault(target, set()).add(binding)
        return reverse

    @classmethod
    def _verify_export_identities(
        cls,
        bindings: t.MappingKV[str, set[str]],
        canonical: t.IterableOf[str],
        expected: t.IterableOf[str],
    ) -> None:
        """Require every canonical export to resolve to the same identity.

        Raises:
            ValueError: If ambiguous public export identity for.

        """
        for export in canonical:
            targets = cls._export_identities(bindings, export, frozenset())
            if targets != set(expected):
                msg = (
                    f"ambiguous public export identity for {export}: {sorted(targets)}"
                )
                raise ValueError(msg)

    @staticmethod
    def private_owner(module: str) -> str | None:
        """Return the distribution root owning ``module``.

        The owner is the module's top-level package (the first segment),
        unless that segment is itself private. Nested private segments
        (``pkg.servers._oid.x``) belong to the same distribution root — the
        importer is a same-project sibling and must rewire relatively, never
        hunt a facade cross-owner.

        Returns:
            The distribution root owning ``module``.

        """
        parts = module.split(".")
        root = parts[0] if parts else ""
        if not root or (len(root) > 1 and root.startswith("_") and root[1].isalpha()):
            return None
        return root

    @staticmethod
    def discover(
        sources: t.MappingKV[str, t.Pair[str, bool]],
    ) -> t.MappingKV[str, t.VariadicTuple[t.Quad[ast.Module, str, str, str]]]:
        """Discover facade aliases and roots from live source assignments.

        Returns:
            The resulting ``t.MappingKV[str, t.VariadicTuple[t.Quad[ast.Module, str,
                str, str]]]``.

        """
        discovered: MutableMapping[str, list[t.Quad[ast.Module, str, str, str]]] = {}
        for module, (source, is_package) in sorted(sources.items()):
            if is_package:
                continue
            package, _, name = module.rpartition(".")
            if not package:
                continue
            tree = ast.parse(source, filename=module)
            class_names = {
                node.name for node in tree.body if isinstance(node, ast.ClassDef)
            }
            for alias, root_name in sorted(
                FlextInfraUtilitiesPrivateImportFacades._facade_owners(
                    tree,
                    class_names,
                ),
            ):
                discovered.setdefault(package, []).append((
                    tree,
                    alias,
                    root_name,
                    f"{name}.py",
                ))
        return {
            package: tuple(owners) for package, owners in sorted(discovered.items())
        }

    @staticmethod
    def _assigned_target_value(
        node: ast.stmt,
    ) -> t.Pair[ast.expr | None, ast.expr | None]:
        """Return one single-target assignment's target and value, if any.

        Returns:
            The resulting ``(target, value)`` pair.

        """
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            return node.targets[0], node.value
        if isinstance(node, ast.AnnAssign):
            return node.target, node.value
        return None, None

    @staticmethod
    def _facade_class_name(value: ast.expr | None) -> str | None:
        """Return the facade class one declaration value names, if any.

        The canonical facade singleton form is
        ``alias: Facade = Facade.fetch_global()``.

        Returns:
            The resulting ``str | None``.

        """
        if isinstance(value, ast.Name):
            return value.id
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name)
        ):
            return value.func.value.id
        return None

    @classmethod
    def _facade_owners(
        cls,
        tree: ast.Module,
        class_names: AbstractSet[str],
    ) -> set[t.Pair[str, str]]:
        """Collect the single-letter facade aliases one module declares.

        Returns:
            The resulting ``set[t.Pair[str, str]]``.

        """
        owners: set[t.Pair[str, str]] = set()
        for node in tree.body:
            target, value = cls._assigned_target_value(node)
            facade_class = cls._facade_class_name(value)
            if (
                isinstance(target, ast.Name)
                and len(target.id) == 1
                and target.id.islower()
                and facade_class is not None
                and facade_class in class_names
            ):
                owners.add((target.id, facade_class))
        return owners

    @classmethod
    def public_reference(
        cls,
        *,
        owners: t.SequenceOf[t.Quad[ast.Module, str, str, str]],
        package: str,
        qualified: str,
        bindings: t.MappingKV[str, set[str]],
        class_bases: t.MappingKV[str, t.VariadicTuple[str]],
    ) -> str | None:
        """Resolve one private class to exactly one inherited facade path.

        Returns:
            The resulting ``str | None``.

        Raises:
            ValueError: If ambiguous public facade references for; or if cyclic public
                facade inheritance; or if ambiguous public facade base identity.

        """
        references: set[str] = set()
        for tree, facade_alias, root_name, facade_file in owners:
            root_class = next(
                (
                    node
                    for node in tree.body
                    if isinstance(node, ast.ClassDef) and node.name == root_name
                ),
                None,
            )
            if root_class is None:
                continue
            cls._collect_facade_references(
                references,
                (bindings, class_bases, qualified),
                root_class,
                facade_alias,
                f"{package}.{Path(facade_file).stem}.{root_name}",
            )
        if not references:
            return None
        deepest = max(reference.count(".") for reference in references)
        canonical = {
            reference for reference in references if reference.count(".") == deepest
        }
        if len(canonical) > 1:
            msg = (
                f"ambiguous public facade references for {qualified}: "
                f"{sorted(canonical)}"
            )
            raise ValueError(msg)
        return canonical.pop()

    @classmethod
    def _inherits_facade(
        cls,
        bindings: t.MappingKV[str, set[str]],
        class_bases: t.MappingKV[str, t.VariadicTuple[str]],
        qualified: str,
        identity: str,
        visiting: frozenset[str],
    ) -> bool:
        """Resolve whether one identity inherits the private class.

        Returns:
            The resulting ``bool``.

        Raises:
            ValueError: If cyclic public facade inheritance; or if ambiguous
                public facade base identity.

        """
        if identity == qualified:
            return True
        if identity in visiting:
            msg = f"cyclic public facade inheritance: {identity}"
            raise ValueError(msg)
        prefix = identity
        while prefix:
            targets = bindings.get(prefix)
            if targets is not None:
                if len(targets) != 1:
                    msg = f"ambiguous public facade base identity: {identity}"
                    raise ValueError(msg)
                target = next(iter(targets)) + identity[len(prefix) :]
                if target != identity:
                    return cls._inherits_facade(
                        bindings,
                        class_bases,
                        qualified,
                        target,
                        visiting | {identity},
                    )
                break
            prefix = prefix.rpartition(".")[0]
        return any(
            cls._inherits_facade(
                bindings,
                class_bases,
                qualified,
                base,
                visiting | {identity},
            )
            for base in class_bases.get(identity, ())
        )

    @classmethod
    def _collect_facade_references(
        cls,
        references: set[str],
        resolvers: t.Triple[
            t.MappingKV[str, set[str]],
            t.MappingKV[str, t.VariadicTuple[str]],
            str,
        ],
        node: ast.ClassDef,
        public_path: str,
        identity: str,
    ) -> None:
        """Add every nested class inheriting the private class to references.

        ``resolvers`` carries ``(bindings, class_bases, qualified)``.
        """
        bindings, class_bases, qualified = resolvers
        if any(
            cls._inherits_facade(bindings, class_bases, qualified, base, frozenset())
            for base in class_bases[identity]
        ):
            references.add(public_path)
        for child in node.body:
            if isinstance(child, ast.ClassDef):
                cls._collect_facade_references(
                    references,
                    resolvers,
                    child,
                    f"{public_path}.{child.name}",
                    f"{identity}.{child.name}",
                )

    @staticmethod
    def facade_alias_binding(
        *,
        owners: t.SequenceOf[t.Quad[ast.Module, str, str, str]],
        alias: str | None,
    ) -> str | None:
        """Return the alias when the owning package publishes it as a facade.

        A private symbol imported under a name the owner already publishes is a
        facade binding, not a class reference: the consumer writes ``m.X``
        against the facade, so the cutover swaps the import statement and every
        usage stays exactly as written.

        Returns:
            The alias when the owning package publishes it as a facade.

        """
        if alias is None:
            return None
        return next(
            (
                facade_alias
                for _tree, facade_alias, _root_name, _facade_file in owners
                if facade_alias == alias
            ),
            None,
        )

    @staticmethod
    def public_root_name(
        *,
        owners: t.SequenceOf[t.Quad[ast.Module, str, str, str]],
        facade_alias: str,
    ) -> str | None:
        """Return the public long name assigned to a canonical facade alias.

        Returns:
            The public long name assigned to a canonical facade alias.

        Raises:
            ValueError: If ambiguous public facade root for alias.

        """
        roots = {
            root_name
            for _tree, alias, root_name, _facade_file in owners
            if alias == facade_alias
        }
        if len(roots) > 1:
            msg = f"ambiguous public facade root for alias {facade_alias}"
            raise ValueError(msg)
        return next(iter(roots), None)

    @staticmethod
    def require_unshadowed_alias(
        tree: ast.Module,
        package: str,
        alias: str,
        file_path: Path,
        removals: t.MappingKV[str, AbstractSet[str]],
    ) -> None:
        """Reject any binding that would shadow the inserted public facade.

        Raises:
            ValueError: If public facade alias.

        """
        allowed_imports = {
            id(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and any(
                (
                    node.module == package
                    and imported.name == alias
                    and imported.asname is None
                )
                or (
                    node.module is not None
                    and node.module in removals
                    and imported.name in removals[node.module]
                    and (imported.asname or imported.name) == alias
                )
                for imported in node.names
            )
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom | ast.Import):
                if id(node) in allowed_imports:
                    continue
                if any(
                    (imported.asname or imported.name.split(".")[0]) == alias
                    for imported in node.names
                ):
                    break
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                if node.id == alias:
                    break
            elif isinstance(node, ast.arg) and node.arg == alias:
                break
            elif isinstance(
                node,
                ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
            ):
                if node.name == alias:
                    break
        else:
            return
        msg = f"public facade alias {alias} is shadowed in {file_path}"
        raise ValueError(msg)


__all__: list[str] = ["FlextInfraUtilitiesPrivateImportFacades"]
