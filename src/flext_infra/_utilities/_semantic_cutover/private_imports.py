"""Semantic private-import cutover planning.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from flext_infra import m, r, t
from flext_infra._utilities import (
    FlextInfraUtilitiesPrivateImportAncestry as ImportAncestry,
    FlextInfraUtilitiesPrivateImportFacades,
    FlextInfraUtilitiesPrivateImportValidation,
)
from flext_infra._utilities._semantic_cutover.edits import (
    FlextInfraUtilitiesSemanticCutoverEdits,
)
from flext_infra._utilities._semantic_cutover.private_import_cst import (
    FlextInfraUtilitiesSemanticCutoverPrivateImportCst,
)

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesSemanticCutoverPrivateImports(
    FlextInfraUtilitiesSemanticCutoverPrivateImportCst,
    FlextInfraUtilitiesSemanticCutoverEdits,
):
    """Plan uniquely public cutovers for cross-owner private imports.

    The ``ban-private-import`` rule reports only private imports of another
    package; imports inside one package are absolute and stay as written.
    """

    @staticmethod
    def _type_checking_ancestors(tree: ast.Module) -> t.MappingKV[ast.AST, ast.AST]:
        """Map every node of one module tree to its parent.

        Returns:
            The resulting ``t.MappingKV[ast.AST, ast.AST]``.

        """
        return {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }

    @staticmethod
    def _is_type_only(
        parents: t.MappingKV[ast.AST, ast.AST],
        node: ast.AST,
    ) -> bool:
        """Report whether one node sits inside a ``TYPE_CHECKING`` boundary.

        Returns:
            The resulting ``bool``.

        """
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

    @staticmethod
    def _imported_public_aliases(
        node: ast.ImportFrom,
        plan: m.Infra.PrivateImportRewritePlan,
    ) -> set[str]:
        """Return the facade aliases one import-from statement contributes.

        Returns:
            The resulting ``set[str]``.

        """
        aliases: set[str] = set()
        module = node.module
        if module is None:
            return aliases
        for imported in node.names:
            qualified = f"{module}.{imported.name}"
            if imported.name in plan.removals.get(module, frozenset()):
                reference = plan.replacements.get(qualified)
                if reference is not None:
                    aliases.add(reference.split(".", 1)[0])
            elif imported.name in plan.obsolete_imports.get(
                module,
                frozenset(),
            ):
                aliases.add(imported.asname or imported.name)
            elif (
                plan.public_imports.get(imported.name) == module
                and imported.asname is None
            ):
                aliases.add(imported.name)
        return aliases

    @classmethod
    def _runtime_public_aliases(
        cls,
        tree: ast.Module,
        plan: m.Infra.PrivateImportRewritePlan,
    ) -> frozenset[str]:
        """Return facades required outside a ``TYPE_CHECKING`` boundary.

        Returns:
            Facades required outside a ``TYPE_CHECKING`` boundary.

        """
        parents = cls._type_checking_ancestors(tree)
        runtime_aliases: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if not cls._is_type_only(parents, node):
                runtime_aliases.update(cls._imported_public_aliases(node, plan))
        return frozenset(runtime_aliases)

    @classmethod
    def _cross_owner_statements(
        cls,
        live_findings: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> t.VariadicTuple[str]:
        """Return the cross-owner private import texts among live findings.

        Returns:
            The resulting ``t.VariadicTuple[str]``.

        """
        cross_owner_statements: list[str] = []
        for finding in live_findings:
            statement = cls._finding_statement(finding)
            if not isinstance(statement, ast.ImportFrom) or statement.level:
                continue
            if (
                FlextInfraUtilitiesPrivateImportFacades.private_owner(
                    statement.module or "",
                )
                is not None
            ):
                cross_owner_statements.append(finding.text)
        return tuple(cross_owner_statements)

    @classmethod
    def _resolved_facades(
        cls,
        cross_owner_statements: t.VariadicTuple[str],
        sources: t.MappingKV[Path, str],
    ) -> t.Pair[
        t.MappingKV[str, t.VariadicTuple[t.Quad[ast.Module, str, str, str]]],
        t.Triple[
            t.MappingKV[str, set[str]],
            t.MappingKV[str, set[str]],
            t.MappingKV[str, t.VariadicTuple[str]],
        ],
    ]:
        """Resolve facade inventories for the cross-owner import statements.

        Returns:
            The resulting ``(facades, bindings)`` pair, where bindings carries
            ``(export bindings, declared exports, class bases)``.

        """
        facades: t.MappingKV[
            str,
            t.VariadicTuple[t.Quad[ast.Module, str, str, str]],
        ] = {}
        bindings: t.Triple[
            t.MappingKV[str, set[str]],
            t.MappingKV[str, set[str]],
            t.MappingKV[str, t.VariadicTuple[str]],
        ] = ({}, {}, {})
        if not cross_owner_statements:
            return facades, bindings
        discovery_sources = FlextInfraUtilitiesPrivateImportFacades.reachable_sources(
            FlextInfraUtilitiesPrivateImportFacades.source_modules(
                sources,
                cross_owner_statements,
            ),
            cross_owner_statements,
        )
        export_bindings, declared_exports = (
            FlextInfraUtilitiesPrivateImportFacades.declared_exports(
                discovery_sources,
            )
        )
        ancestry = ImportAncestry.FlextInfraUtilitiesPrivateImportAncestry
        return (
            FlextInfraUtilitiesPrivateImportFacades.discover(discovery_sources),
            (
                export_bindings,
                declared_exports,
                ancestry.class_bases(discovery_sources),
            ),
        )

    @staticmethod
    def _import_target_reference(
        package: str,
        qualified: str,
        imported: ast.alias,
        facades: t.MappingKV[
            str,
            t.VariadicTuple[t.Quad[ast.Module, str, str, str]],
        ],
        bindings: t.Triple[
            t.MappingKV[str, set[str]],
            t.MappingKV[str, set[str]],
            t.MappingKV[str, t.VariadicTuple[str]],
        ],
    ) -> str | None:
        """Resolve one imported private name to its public facade reference.

        Returns:
            The resulting ``str | None``.

        """
        export_bindings, _declared_exports, class_bases = bindings
        return FlextInfraUtilitiesPrivateImportFacades.facade_alias_binding(
            owners=facades.get(package, ()),
            alias=imported.asname,
        ) or FlextInfraUtilitiesPrivateImportFacades.public_reference(
            owners=facades.get(package, ()),
            package=package,
            qualified=qualified,
            bindings=export_bindings,
            class_bases=class_bases,
        )

    @classmethod
    def _finding_import_specs(
        cls,
        root: Path,
        live_findings: t.SequenceOf[m.Infra.ModScanFinding],
        facades: t.MappingKV[
            str,
            t.VariadicTuple[t.Quad[ast.Module, str, str, str]],
        ],
        bindings: t.Triple[
            t.MappingKV[str, set[str]],
            t.MappingKV[str, set[str]],
            t.MappingKV[str, t.VariadicTuple[str]],
        ],
    ) -> t.Pair[
        t.MappingKV[Path, list[t.Infra.PrivateImportSpec]],
        t.MappingKV[Path, t.MappingKV[str, t.Pair[str, str]]],
    ]:
        """Resolve every live finding into its per-file import specs.

        Returns:
            The resulting ``(specs, direct specs)`` mapping pair.

        Raises:
            ValueError: If ambiguous private star import in; or if no public facade
                exposes cross-owner private import.

        """
        export_bindings, declared_exports, _class_bases = bindings
        direct_specs: MutableMapping[Path, MutableMapping[str, t.Pair[str, str]]] = {}
        specs: MutableMapping[Path, list[t.Infra.PrivateImportSpec]] = {}
        for finding in live_findings:
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
            file_specs = specs.setdefault(file_path, [])
            for imported in statement.names:
                if imported.name == "*":
                    msg = f"ambiguous private star import in {finding.file}"
                    raise ValueError(msg)
                qualified = f"{private_module}.{imported.name}"
                declared = (
                    FlextInfraUtilitiesPrivateImportFacades.declared_public_reference(
                        qualified,
                        export_bindings,
                        declared_exports,
                    )
                )
                if declared is not None:
                    direct_specs.setdefault(file_path, {})[qualified] = declared
                    continue
                target_reference = cls._import_target_reference(
                    package,
                    qualified,
                    imported,
                    facades,
                    bindings,
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
        return specs, direct_specs

    @classmethod
    def _private_import_references(
        cls,
        root: Path,
        sources: t.MappingKV[Path, str],
        findings: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> t.Infra.PrivateImportReferences:
        """Resolve every reported cross-owner private import to its public owner.

        Returns:
            The resulting ``t.Infra.PrivateImportReferences``.

        """
        live_findings = tuple(
            finding
            for finding in findings
            if cls._finding_is_live(root, sources, finding)
        )
        cross_owner_statements = cls._cross_owner_statements(live_findings)
        facades, bindings = cls._resolved_facades(
            cross_owner_statements,
            sources,
        )
        specs, direct_specs = cls._finding_import_specs(
            root,
            live_findings,
            facades,
            bindings,
        )
        return specs, direct_specs, facades

    @classmethod
    def _finding_is_live(
        cls,
        root: Path,
        sources: t.MappingKV[Path, str],
        finding: m.Infra.ModScanFinding,
    ) -> bool:
        """Reject a preflight import already moved by an earlier semantic phase.

        Returns:
            The resulting ``bool``.

        Raises:
            ValueError: If private import source missing from inventory.

        """
        statement = cls._finding_statement(finding)
        if not isinstance(statement, ast.ImportFrom):
            return False
        path = (root / finding.file).resolve()
        source = sources.get(path)
        if source is None:
            msg = f"private import source missing from inventory: {path}"
            raise ValueError(msg)
        expected = tuple((alias.name, alias.asname) for alias in statement.names)
        return any(
            isinstance(node, ast.ImportFrom)
            and node.module == statement.module
            and node.level == statement.level
            and tuple((alias.name, alias.asname) for alias in node.names) == expected
            for node in ast.walk(ast.parse(source))
        )

    @classmethod
    def _plan_private_imports(
        cls,
        root: Path,
        sources: t.MappingKV[Path, str],
        findings: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan binding-aware public import rewrites.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]``.

        """
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
        """Rewrite one module's private imports and prove zero residue.

        Returns:
            The resulting ``t.Infra.TransformResult``.

        Raises:
            ValueError: If ambiguous facade alias; or if ambiguous public reference for.

        """
        tree = ast.parse(source, filename=str(file_path))
        removals: MutableMapping[str, set[str]] = {}
        obsolete_imports: MutableMapping[str, set[str]] = {}
        replacements: MutableMapping[str, str] = {}
        public_imports: MutableMapping[str, str] = {}
        for private_module, symbol, qualified, package, reference in file_specs:
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
                f"rewired {private} to {public}"
                for private, public in sorted(replacements.items())
            ),
        )


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverPrivateImports"]
