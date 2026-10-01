"""Defer elected self-facade imports to their resolved function-body uses.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, override

import libcst as cst
from libcst.metadata import MetadataWrapper, ParentNodeProvider, QualifiedNameProvider

from flext_infra import m, t
from flext_infra._utilities._semantic_cutover.edits import (
    FlextInfraUtilitiesSemanticCutoverEdits,
)
from flext_infra._utilities.qualified_names import FlextInfraUtilitiesQualifiedNames

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesSemanticCutoverSelfFacade(
    FlextInfraUtilitiesSemanticCutoverEdits,
):
    """Keep utility-facade composition free of an eager reverse import."""

    class _SelfFacadeTransformer(cst.CSTTransformer):
        METADATA_DEPENDENCIES = (ParentNodeProvider, QualifiedNameProvider)

        def __init__(self, module: str, local: str) -> None:
            self.module = module
            self.local = local
            self.functions: set[cst.FunctionDef] = set()

        @override
        def visit_Name(self, node: cst.Name) -> None:
            if node.value != self.local:
                return
            names = self.get_metadata(QualifiedNameProvider, node, ())
            target = f"{self.module}.u"
            if not any(name.name == target for name in names):
                return
            if any(name.name != target for name in names):
                msg = f"self-facade reference has ambiguous binding: {self.local}"
                raise ValueError(msg)
            child: cst.CSTNode = node
            while parent := self.get_metadata(ParentNodeProvider, child, None):
                if isinstance(parent, cst.ImportAlias | cst.ImportFrom):
                    return
                if isinstance(parent, cst.FunctionDef):
                    if child is not parent.body:
                        msg = "self-facade eager function metadata cannot be deferred"
                        raise ValueError(msg)
                    self.functions.add(parent)
                    return
                if isinstance(parent, cst.ClassDef):
                    msg = "self-facade class-body use cannot be deferred"
                    raise TypeError(msg)
                child = parent
            msg = "self-facade module-body use cannot be deferred"
            raise ValueError(msg)

        @override
        def leave_FunctionDef(
            self,
            original_node: cst.FunctionDef,
            updated_node: cst.FunctionDef,
        ) -> cst.FunctionDef:
            if original_node not in self.functions:
                return updated_node
            if not isinstance(updated_node.body, cst.IndentedBlock):
                msg = "self-facade use requires an indented function body"
                raise TypeError(msg)
            alias = "" if self.local == "u" else f" as {self.local}"
            imported = cst.parse_statement(f"from {self.module} import u{alias}\n")
            body = list(updated_node.body.body)
            offset = 0
            if body and isinstance(body[0], cst.SimpleStatementLine):
                statements = body[0].body
                if (
                    len(statements) == 1
                    and isinstance(statements[0], cst.Expr)
                    and isinstance(statements[0].value, cst.SimpleString)
                ):
                    offset = 1
            body.insert(offset, imported)
            return updated_node.with_changes(
                body=updated_node.body.with_changes(body=body),
            )

        @override
        def leave_ImportFrom(
            self,
            original_node: cst.ImportFrom,
            updated_node: cst.ImportFrom,
        ) -> cst.BaseSmallStatement | cst.RemovalSentinel:
            parent = self.get_metadata(ParentNodeProvider, original_node)
            if not isinstance(parent, cst.SimpleStatementLine):
                return updated_node
            if not isinstance(
                self.get_metadata(ParentNodeProvider, parent),
                cst.Module,
            ):
                return updated_node
            if FlextInfraUtilitiesQualifiedNames.dotted_name(
                original_node.module,
            ) != self.module or isinstance(updated_node.names, cst.ImportStar):
                return updated_node
            retained: list[cst.ImportAlias] = []
            for item in updated_node.names:
                if not isinstance(item.name, cst.Name):
                    retained.append(item)
                    continue
                if item.asname is None:
                    local = item.name.value
                elif isinstance(item.asname.name, cst.Name):
                    local = item.asname.name.value
                else:
                    msg = "self-facade import alias is not a simple name"
                    raise TypeError(msg)
                if item.name.value != "u" or local != self.local:
                    retained.append(item)
            if retained:
                return updated_node.with_changes(
                    names=FlextInfraUtilitiesQualifiedNames.normalized_import_aliases(
                        retained,
                        parenthesized=updated_node.lpar is not None,
                    ),
                )
            return cst.RemoveFromParent()

    @classmethod
    def _plan_self_facade_imports(
        cls,
        root: Path,
        sources: t.MappingKV[Path, str],
        findings: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        selected = {
            (root / finding.file).resolve(): {
                declaration.module
                for candidate in findings
                if candidate.file == finding.file
                and isinstance(
                    declaration := cls._finding_statement(candidate),
                    ast.ImportFrom,
                )
                and declaration.module
            }
            for finding in findings
        }

        def rewrite(path: Path, source: str) -> t.Infra.TransformResult:
            updated = source
            tree = ast.parse(source, filename=str(path))
            targets: set[t.Pair[str, str]] = set()
            for node in tree.body:
                if (
                    not isinstance(node, ast.ImportFrom)
                    or node.module not in selected[path]
                    or node.level
                ):
                    continue
                for alias in node.names:
                    if alias.name != "u":
                        continue
                    targets.add((node.module, alias.asname or alias.name))
            for module, local in sorted(targets):
                if any(
                    isinstance(node, ast.Global | ast.Nonlocal) and local in node.names
                    for node in ast.walk(tree)
                ):
                    msg = f"self-facade scope declaration cannot be deferred: {local}"
                    raise ValueError(msg)
                transformer = cls._SelfFacadeTransformer(module, local)
                updated = (
                    MetadataWrapper(cst.parse_module(updated)).visit(transformer).code
                )
            return updated, ("deferred elected self-facade imports to resolved uses",)

        return cls._semantic_edits(
            tuple(
                item for item in cls._editable_sources(sources) if item[0] in selected
            ),
            rewrite,
        )


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverSelfFacade"]
