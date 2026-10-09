"""Semantic compatibility-alias cutover planning.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, r, t
from flext_infra._utilities._semantic_cutover.alias_cst import (
    FlextInfraUtilitiesSemanticCutoverAliasCst,
)
from flext_infra._utilities._semantic_cutover.edits import (
    FlextInfraUtilitiesSemanticCutoverEdits,
)
from flext_infra._utilities.compatibility_alias_validation import (
    FlextInfraUtilitiesCompatibilityAliasValidation,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesSemanticCutoverAliases(
    FlextInfraUtilitiesSemanticCutoverAliasCst,
    FlextInfraUtilitiesSemanticCutoverEdits,
):
    """Plan atomic removal of API aliases and their proven consumers."""

    @classmethod
    def _api_alias_specs(
        cls,
        root: Path,
        findings: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> p.Result[
        t.Pair[t.MappingKV[Path, t.StrMapping], t.MappingKV[str, t.StrMapping]]
    ]:
        """Index every API alias finding by owner file and importable module.

        Returns:
            The resulting ``p.Result[t.Pair[t.MappingKV[Path, t.StrMapping],
                t.MappingKV[str, t.StrMapping]]]``.

        """
        planned = r[
            t.Pair[t.MappingKV[Path, t.StrMapping], t.MappingKV[str, t.StrMapping]]
        ]
        specs_by_file: MutableMapping[Path, MutableMapping[str, str]] = {}
        specs_by_module: MutableMapping[str, MutableMapping[str, str]] = {}
        for finding in findings:
            relative = finding.file
            statement = cls._finding_statement(finding)
            if not (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and isinstance(statement.value, ast.Name)
            ):
                return planned.fail(
                    f"invalid compatibility-alias finding: {finding.text}",
                )
            if c.Infra.DEFAULT_SRC_DIR not in relative.parts:
                return planned.fail(f"API alias owner is outside src: {relative}")
            alias, target = statement.targets[0].id, statement.value.id
            source_index = relative.parts.index(c.Infra.DEFAULT_SRC_DIR)
            module_parts = (*relative.parts[source_index + 1 : -1], relative.stem)
            specs_by_file.setdefault((root / relative).resolve(), {})[alias] = target
            for import_module in (".".join(module_parts), module_parts[0]):
                current = specs_by_module.setdefault(import_module, {})
                if current.setdefault(alias, target) != target:
                    return planned.fail(f"ambiguous API alias {import_module}.{alias}")
        return planned.ok((specs_by_file, specs_by_module))

    @classmethod
    def _plan_api_aliases(
        cls,
        root: Path,
        sources: t.MappingKV[Path, str],
        findings: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan API alias removals and AST-proven consumer rewrites.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]``.

        """
        specs = cls._api_alias_specs(
            root,
            tuple(
                finding for finding in findings if finding.file.name == c.Infra.API_PY
            ),
        )
        if specs.failure:
            return r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]].from_failure(specs)
        specs_by_file, specs_by_module = specs.value

        def rewrite(path: Path, source: str) -> t.Infra.TransformResult:
            local_aliases = specs_by_file.get(path, {})
            tree = ast.parse(source, filename=str(path))
            import_aliases: MutableMapping[str, MutableMapping[str, str]] = {}
            attribute_aliases: MutableMapping[t.Pair[str, str], str] = {}
            qualified_aliases = dict(local_aliases)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module is not None
                    and node.module in specs_by_module
                ):
                    for imported in node.names:
                        imported_target = specs_by_module[node.module].get(
                            imported.name,
                        )
                        if imported_target is None:
                            continue
                        if imported.asname not in {None, imported.name}:
                            msg = (
                                "ambiguous compatibility import alias "
                                f"{imported.name} as {imported.asname}"
                            )
                            raise ValueError(msg)
                        import_aliases.setdefault(node.module, {})[imported.name] = (
                            imported_target
                        )
                        qualified_aliases[f"{node.module}.{imported.name}"] = (
                            imported_target
                        )
                elif isinstance(node, ast.Import):
                    attribute_aliases.update(
                        ((imported.asname or imported.name, alias), target)
                        for imported in node.names
                        for alias, target in specs_by_module.get(
                            imported.name,
                            {},
                        ).items()
                    )
            if not (local_aliases or import_aliases or attribute_aliases):
                return source, ()
            FlextInfraUtilitiesCompatibilityAliasValidation.require_static_compatibility_alias_exports(
                tree,
                path,
                frozenset(local_aliases),
            )
            rewritten = cls._rewrite_compatibility_alias_source(
                source,
                m.Infra.CompatibilityAliasRewritePlan(
                    local_aliases=local_aliases,
                    import_aliases=import_aliases,
                    attribute_aliases=attribute_aliases,
                    qualified_aliases=qualified_aliases,
                    target_bindings=cls._bound_names(tree),
                ),
            )
            FlextInfraUtilitiesCompatibilityAliasValidation.require_zero_compatibility_alias_residue(
                rewritten,
                path,
                qualified_aliases=qualified_aliases,
                exported_aliases=frozenset(local_aliases),
            )
            return rewritten, tuple(
                f"rewired {alias} to {target}"
                for alias, target in sorted(qualified_aliases.items())
            )

        return cls._semantic_edits(cls._editable_sources(sources), rewrite)

    @staticmethod
    def _bound_names(tree: ast.Module) -> frozenset[str]:
        """Return statically bound module names for redundant-import removal.

        Returns:
            Statically bound module names for redundant-import removal.

        """
        names: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                names.add(node.name)
            elif isinstance(node, ast.ImportFrom):
                names.update(item.asname or item.name for item in node.names)
            elif isinstance(node, ast.Import):
                names.update(
                    item.asname or item.name.split(".")[0] for item in node.names
                )
        return frozenset(names)


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverAliases"]
