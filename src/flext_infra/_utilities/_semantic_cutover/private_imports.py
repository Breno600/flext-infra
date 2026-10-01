"""Semantic private-import cutover planning."""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, t

from ..private_import_ancestry import FlextInfraUtilitiesPrivateImportAncestry
from ..private_import_facades import FlextInfraUtilitiesPrivateImportFacades
from ..private_import_validation import FlextInfraUtilitiesPrivateImportValidation
from .edits import FlextInfraUtilitiesSemanticCutoverEdits
from .private_import_cst import FlextInfraUtilitiesSemanticCutoverPrivateImportCst

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesSemanticCutoverPrivateImports(
    FlextInfraUtilitiesSemanticCutoverPrivateImportCst,
    FlextInfraUtilitiesSemanticCutoverEdits,
):
    """Plan cycle-free local imports and uniquely public cross-owner cutovers."""

    @staticmethod
    def _same_owner_relative_module(
        file_path: Path,
        *,
        package: str,
        private_module: str,
    ) -> str | None:
        """Derive the minimal relative module for a same-owner source path."""
        package_parts = tuple(package.split("."))
        target_parts = tuple(private_module.split("."))
        candidates: set[str] = set()
        path_parts = file_path.resolve().parts
        source_candidates = [
            path_parts[index + 1 :]
            for index, part in enumerate(path_parts)
            if part == c.Infra.DEFAULT_SRC_DIR
        ]
        # Repo-rooted trees (tests) import from the checkout root, so the
        # package path itself anchors the module without a src segment. The
        # anchor applies at ANY depth inside the owner: a module nested in a
        # private segment (tests/_utilities/x.py) is a same-owner sibling and
        # must resolve to a minimal relative import, never to a facade hunt.
        owner_length = len(package_parts)
        for index in range(len(path_parts) - owner_length):
            if tuple(path_parts[index : index + owner_length]) == package_parts:
                source_candidates.append(path_parts[index:])
                break
        for source_parts in source_candidates:
            if (
                len(source_parts) <= len(package_parts)
                or tuple(source_parts[: len(package_parts)]) != package_parts
            ):
                continue
            is_package_module = source_parts[-1] in {c.Infra.INIT_PY, c.Infra.INIT_PYI}
            module_parts = (
                source_parts[:-1]
                if is_package_module
                else (*source_parts[:-1], Path(source_parts[-1]).stem)
            )
            current_package = module_parts if is_package_module else module_parts[:-1]
            common = 0
            for current_part, target_part in zip(
                current_package,
                target_parts,
                strict=False,
            ):
                if current_part != target_part:
                    break
                common += 1
            level = len(current_package) - common + 1
            suffix = ".".join(target_parts[common:])
            candidates.add(f"{'.' * level}{suffix}")
        if len(candidates) > 1:
            msg = f"ambiguous source owner for private import in {file_path}"
            raise ValueError(msg)
        return next(iter(candidates), None)

    @staticmethod
    def _runtime_public_aliases(
        tree: ast.Module,
        plan: m.Infra.PrivateImportRewritePlan,
    ) -> frozenset[str]:
        """Return facades required outside a ``TYPE_CHECKING`` boundary."""
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }

        def is_type_only(node: ast.AST) -> bool:
            parent = parents.get(node)
            while parent is not None:
                if (
                    isinstance(parent, ast.If)
                    and isinstance(parent.test, ast.Name)
                    and parent.test.id == "TYPE_CHECKING"
                ):
                    return True
                parent = parents.get(parent)
            return False

        runtime_aliases: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            aliases: set[str] = set()
            for imported in node.names:
                qualified = f"{node.module}.{imported.name}"
                if imported.name in plan.removals.get(node.module, frozenset()):
                    reference = plan.replacements.get(qualified)
                    if reference is not None:
                        aliases.add(reference.split(".", 1)[0])
                elif imported.name in plan.obsolete_imports.get(
                    node.module,
                    frozenset(),
                ):
                    aliases.add(imported.asname or imported.name)
                elif (
                    plan.public_imports.get(imported.name) == node.module
                    and imported.asname is None
                ):
                    aliases.add(imported.name)
            if not is_type_only(node):
                runtime_aliases.update(aliases)
        return frozenset(runtime_aliases)

    @classmethod
    def _private_import_references(
        cls,
        root: Path,
        sources: t.MappingKV[Path, str],
        findings: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> t.Infra.PrivateImportReferences:
        """Resolve every reported private import to its relative or public owner."""
        cross_owner_statements: list[str] = []
        for finding in findings:
            statement = cls._finding_statement(finding)
            if not isinstance(statement, ast.ImportFrom) or statement.level:
                continue
            private_module = statement.module or ""
            package = FlextInfraUtilitiesPrivateImportFacades.private_owner(
                private_module,
            )
            if package is None:
                continue
            file_path = (root / finding.file).resolve()
            if (
                cls._same_owner_relative_module(
                    file_path,
                    package=package,
                    private_module=private_module,
                )
                is None
            ):
                cross_owner_statements.append(finding.text)
        facades: t.MappingKV[
            str,
            t.VariadicTuple[t.Quad[ast.Module, str, str, str]],
        ] = {}
        export_bindings: t.MappingKV[str, set[str]] = {}
        declared_exports: t.MappingKV[str, set[str]] = {}
        class_bases: t.MappingKV[str, t.VariadicTuple[str]] = {}
        if cross_owner_statements:
            discovery_sources = (
                FlextInfraUtilitiesPrivateImportFacades.reachable_sources(
                    FlextInfraUtilitiesPrivateImportFacades.source_modules(
                        sources,
                        tuple(cross_owner_statements),
                    ),
                    tuple(cross_owner_statements),
                )
            )
            facades = FlextInfraUtilitiesPrivateImportFacades.discover(
                discovery_sources,
            )
            export_bindings, declared_exports = (
                FlextInfraUtilitiesPrivateImportFacades.declared_exports(
                    discovery_sources,
                )
            )
            class_bases = FlextInfraUtilitiesPrivateImportAncestry.class_bases(
                discovery_sources,
            )
        direct_specs: MutableMapping[Path, MutableMapping[str, t.Pair[str, str]]] = {}
        specs: MutableMapping[Path, list[t.Infra.PrivateImportSpec]] = {}
        for finding in findings:
            statement = cls._finding_statement(finding)
            if not isinstance(statement, ast.ImportFrom) or statement.level:
                continue
            private_module = statement.module or ""
            package = FlextInfraUtilitiesPrivateImportFacades.private_owner(
                private_module,
            )
            if package is None:
                continue
            file_path = (root / finding.file).resolve()
            relative_module = cls._same_owner_relative_module(
                file_path,
                package=package,
                private_module=private_module,
            )
            file_specs = specs.setdefault(file_path, [])
            for imported in statement.names:
                if imported.name == "*" and relative_module is None:
                    msg = f"ambiguous private star import in {finding.file}"
                    raise ValueError(msg)
                qualified = f"{private_module}.{imported.name}"
                declared = (
                    FlextInfraUtilitiesPrivateImportFacades.declared_public_reference(
                        qualified,
                        export_bindings,
                        declared_exports,
                    )
                    if relative_module is None
                    else None
                )
                if declared is not None:
                    direct_specs.setdefault(file_path, {})[qualified] = declared
                    continue
                target_reference = (
                    relative_module
                    or FlextInfraUtilitiesPrivateImportFacades.facade_alias_binding(
                        owners=facades.get(package, ()),
                        alias=imported.asname,
                    )
                    or FlextInfraUtilitiesPrivateImportFacades.public_reference(
                        owners=facades.get(package, ()),
                        package=package,
                        qualified=qualified,
                        bindings=export_bindings,
                        class_bases=class_bases,
                    )
                )
                if target_reference is None:
                    msg = (
                        f"no public facade exposes cross-owner private import "
                        f"{qualified} in {file_path}"
                    )
                    raise ValueError(msg)
                file_specs.append((
                    private_module,
                    imported.name,
                    qualified,
                    package,
                    target_reference,
                ))
        return specs, direct_specs, facades

    @classmethod
    def _plan_private_imports(
        cls,
        root: Path,
        sources: t.MappingKV[Path, str],
        findings: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan owner-aware relative and binding-aware public import rewrites."""
        planned_edits = r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]
        specs, direct_specs, facades = cls._private_import_references(
            root,
            sources,
            findings,
        )
        missing = sorted(str(path) for path in specs if path not in sources)
        if missing:
            return planned_edits.fail(
                f"private import source missing from inventory: {', '.join(missing)}",
            )

        def rewrite(path: Path, source: str) -> t.Infra.TransformResult:
            return cls._rewrite_private_imports(
                path,
                source,
                file_specs=specs[path],
                direct_specs=direct_specs.get(path, {}),
                facades=facades,
            )

        return cls._semantic_edits(
            tuple(item for item in cls._editable_sources(sources) if item[0] in specs),
            rewrite,
        )

    @classmethod
    def _rewrite_private_imports(
        cls,
        file_path: Path,
        source: str,
        *,
        file_specs: t.SequenceOf[t.Infra.PrivateImportSpec],
        direct_specs: t.MappingKV[str, t.Pair[str, str]],
        facades: t.MappingKV[str, t.VariadicTuple[t.Quad[ast.Module, str, str, str]]],
    ) -> t.Infra.TransformResult:
        """Rewrite one module's private imports and prove zero residue."""
        tree = ast.parse(source, filename=str(file_path))
        relative_imports: MutableMapping[str, str] = {}
        relative_symbols: MutableMapping[str, set[str]] = {}
        removals: MutableMapping[str, set[str]] = {}
        obsolete_imports: MutableMapping[str, set[str]] = {}
        replacements: MutableMapping[str, str] = {}
        public_imports: MutableMapping[str, str] = {}
        for private_module, symbol, qualified, package, reference in file_specs:
            if reference.startswith("."):
                if relative_imports.setdefault(private_module, reference) != reference:
                    msg = f"ambiguous relative import for {private_module}"
                    raise ValueError(msg)
                relative_symbols.setdefault(private_module, set()).add(symbol)
                continue
            facade_alias = reference.split(".", 1)[0]
            if public_imports.setdefault(facade_alias, package) != package:
                msg = (
                    f"ambiguous facade alias {facade_alias}: "
                    f"{public_imports[facade_alias]}, {package}"
                )
                raise ValueError(msg)
            if replacements.setdefault(qualified, reference) != reference:
                msg = f"ambiguous public reference for {qualified}"
                raise ValueError(msg)
            removals.setdefault(private_module, set()).add(symbol)
        for facade_alias, package in public_imports.items():
            public_root_name = FlextInfraUtilitiesPrivateImportFacades.public_root_name(
                owners=facades.get(package, ()),
                facade_alias=facade_alias,
            )
            if public_root_name is None:
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module == package
                    and any(
                        imported.name == public_root_name
                        and imported.asname == facade_alias
                        for imported in node.names
                    )
                ):
                    obsolete_imports.setdefault(package, set()).add(public_root_name)
                    replacements[f"{package}.{public_root_name}"] = facade_alias
        plan = m.Infra.PrivateImportRewritePlan(
            relative_imports=relative_imports,
            relative_symbols={
                key: frozenset(value) for key, value in relative_symbols.items()
            },
            removals={key: frozenset(value) for key, value in removals.items()},
            obsolete_imports={
                key: frozenset(value) for key, value in obsolete_imports.items()
            },
            replacements=replacements,
            public_imports=public_imports,
        )
        all_removals = {
            module: removals.get(module, set()) | obsolete_imports.get(module, set())
            for module in removals.keys() | obsolete_imports.keys()
        }
        for facade_alias, package in public_imports.items():
            FlextInfraUtilitiesPrivateImportFacades.require_unshadowed_alias(
                tree,
                package,
                facade_alias,
                file_path,
                all_removals,
            )
        rewritten = cls._rewrite_private_import_source(
            cls._relocate_declared_exports(source, direct_specs),
            plan,
            runtime_public_imports=cls._runtime_public_aliases(tree, plan),
        )
        for qualified in direct_specs:
            module, _, name = qualified.rpartition(".")
            all_removals.setdefault(module, set()).add(name)
        FlextInfraUtilitiesPrivateImportValidation.require_zero_private_import_residue(
            rewritten,
            file_path=file_path,
            plan=plan,
            removals=all_removals,
        )
        return rewritten, (
            *(
                f"rewired {private} to {module}.{name}"
                for private, (module, name) in sorted(direct_specs.items())
            ),
            *(
                f"relativized {absolute} to {relative}"
                for absolute, relative in sorted(relative_imports.items())
            ),
            *(
                f"rewired {private} to {public}"
                for private, public in sorted(replacements.items())
            ),
        )


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverPrivateImports"]
