"""Route config-owned dynamic environment keys through their settings owner.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections import Counter
from typing import TYPE_CHECKING, override

import libcst as cst
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor
from libcst.metadata import (
    MetadataWrapper,
    ParentNodeProvider,
    QualifiedNameProvider,
    QualifiedNameSource,
)

from flext_infra import m, t
from flext_infra._utilities._semantic_cutover.bindings import (
    FlextInfraUtilitiesSemanticCutoverBindings,
)
from flext_infra._utilities._semantic_cutover.edits import (
    FlextInfraUtilitiesSemanticCutoverEdits,
)

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesSemanticCutoverDynamicEnvironment(
    FlextInfraUtilitiesSemanticCutoverEdits,
    FlextInfraUtilitiesSemanticCutoverBindings,
):
    """Require resolved OS imports and same-function config provenance."""

    class _EnvironmentTransformer(cst.CSTTransformer):
        METADATA_DEPENDENCIES = (ParentNodeProvider, QualifiedNameProvider)

        def __init__(self, bindings: t.MappingKV[str, int]) -> None:
            self.aliases: t.MutableMappingKV[t.Pair[str, cst.FunctionDef], str] = {}
            self.packages: set[str] = set()
            self.bindings = bindings

        def _qualified(self, node: cst.CSTNode, expected: str) -> bool:
            names = self.get_metadata(QualifiedNameProvider, node, ())
            return bool(names) and all(name.name == expected for name in names)

        def _function(self, node: cst.CSTNode) -> cst.FunctionDef | None:
            while parent := self.get_metadata(ParentNodeProvider, node, None):
                if isinstance(parent, cst.FunctionDef):
                    return parent
                node = parent
            return None

        def _config_package(self, node: cst.BaseExpression) -> str | None:
            if (
                isinstance(node, cst.Call)
                and self._qualified(node.func, "builtins.str")
                and len(node.args) == 1
            ):
                return self._config_package(node.args[0].value)
            if isinstance(node, cst.Attribute):
                return self._config_package(node.value)
            if not isinstance(node, cst.Name):
                return None
            if self.bindings.get(node.value) != 1:
                return None
            names = self.get_metadata(QualifiedNameProvider, node, ())
            packages: set[str] = set()
            for name in names:
                if name.source is QualifiedNameSource.IMPORT and name.name.endswith(
                    ".config",
                ):
                    packages.add(name.name.removesuffix(".config"))
                elif (function := self._function(node)) is not None:
                    package = self.aliases.get((name.name, function))
                    if package is not None:
                        packages.add(package)
            return next(iter(packages)) if len(packages) == 1 else None

        @override
        def visit_Assign(self, node: cst.Assign) -> None:
            parent = self.get_metadata(ParentNodeProvider, node)
            if not isinstance(parent, cst.SimpleStatementLine):
                return
            block = self.get_metadata(ParentNodeProvider, parent)
            if not isinstance(block, cst.IndentedBlock):
                return
            function = self.get_metadata(ParentNodeProvider, block, None)
            if not isinstance(function, cst.FunctionDef):
                return
            package = self._config_package(node.value)
            for target in node.targets:
                if not isinstance(target.target, cst.Name):
                    continue
                for name in self.get_metadata(QualifiedNameProvider, target.target, ()):
                    key = (name.name, function)
                    if package is None:
                        self.aliases.pop(key, None)
                    else:
                        self.aliases[key] = package

        def _read(self, key: cst.BaseExpression, method: str) -> cst.Call:
            package = self._config_package(key)
            if package is None:
                msg = "environment key lacks unambiguous typed-config provenance"
                raise ValueError(msg)
            self.packages.add(package)
            return cst.Call(
                cst.Attribute(cst.Name("settings"), cst.Name(method)),
                (cst.Arg(key),),
            )

        @override
        def leave_Call(
            self,
            original_node: cst.Call,
            updated_node: cst.Call,
        ) -> cst.BaseExpression:
            if not self._qualified(original_node.func, "os.environ.get"):
                return updated_node
            if (
                len(original_node.args) != 1
                or original_node.args[0].keyword is not None
                or original_node.args[0].star
            ):
                msg = (
                    "dynamic environment lookup has an unsupported default or argument"
                )
                raise ValueError(msg)
            return self._read(original_node.args[0].value, "env_lookup")

        @override
        def leave_Subscript(
            self,
            original_node: cst.Subscript,
            updated_node: cst.Subscript,
        ) -> cst.BaseExpression:
            if not self._qualified(original_node.value, "os.environ"):
                return updated_node
            if len(original_node.slice) != 1 or not isinstance(
                original_node.slice[0].slice,
                cst.Index,
            ):
                msg = "dynamic environment lookup requires a single key"
                raise ValueError(msg)
            parent = self.get_metadata(ParentNodeProvider, original_node)
            if isinstance(parent, cst.AssignTarget | cst.Del | cst.AugAssign):
                msg = "environment mutation is not a settings lookup"
                raise TypeError(msg)
            return self._read(original_node.slice[0].slice.value, "env_required")

    @classmethod
    def _plan_dynamic_environment(
        cls,
        root: Path,
        sources: t.MappingKV[Path, str],
        findings: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        selected = {(root / finding.file).resolve() for finding in findings}

        def rewrite(_path: Path, source: str) -> t.Infra.TransformResult:
            tree = ast.parse(source)
            bindings = Counter(
                name for node in ast.walk(tree) for name in cls.bound_identifiers(node)
            )
            transformer = cls._EnvironmentTransformer(bindings)
            updated = MetadataWrapper(cst.parse_module(source)).visit(transformer)
            if not transformer.packages:
                return source, ()
            if len(transformer.packages) != 1:
                msg = "dynamic environment reads resolve to competing settings owners"
                raise ValueError(msg)
            package = next(iter(transformer.packages))
            cls._require_settings_owner(package, sources)
            for node in ast.walk(tree):
                if "settings" in cls.bound_identifiers(node) and not (
                    isinstance(node, ast.ImportFrom)
                    and node.module == package
                    and not node.level
                    and any(
                        alias.name == "settings" and alias.asname is None
                        for alias in node.names
                    )
                ):
                    msg = (
                        "dynamic environment migration conflicts "
                        "with a settings binding"
                    )
                    raise ValueError(msg)
                if isinstance(node, ast.ImportFrom) and any(
                    alias.name == "*" for alias in node.names
                ):
                    msg = (
                        "dynamic environment migration cannot resolve wildcard imports"
                    )
                    raise ValueError(msg)
            context = CodemodContext()
            AddImportsVisitor.add_needed_import(context, package, "settings")
            updated = updated.visit(AddImportsVisitor(context))
            return updated.code, (
                "routed config-owned environment keys through settings",
            )

        return cls._semantic_edits(
            tuple(
                item for item in cls._editable_sources(sources) if item[0] in selected
            ),
            rewrite,
        )

    @staticmethod
    def _require_settings_owner(package: str, sources: t.MappingKV[Path, str]) -> None:
        """Require the destination settings API to exist in the source inventory.

        Raises:
            ValueError: If dynamic environment migration requires one declared settings
                owner; or if settings owner lacks optional/required dynamic environment
                reads.

        """
        owners = [
            source
            for path, source in sources.items()
            if path.name == "_settings.py"
            and path.parent.name == package.rsplit(".", maxsplit=1)[-1]
        ]
        if len(owners) != 1:
            msg = (
                f"dynamic environment migration requires one "
                f"declared settings owner: {package}"
            )
            raise ValueError(msg)
        methods = {
            node.name
            for node in ast.walk(ast.parse(owners[0]))
            if isinstance(node, ast.FunctionDef)
        }
        if not {"env_lookup", "env_required"} <= methods:
            msg = (
                f"settings owner lacks optional/required "
                f"dynamic environment reads: {package}"
            )
            raise ValueError(msg)


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverDynamicEnvironment"]
