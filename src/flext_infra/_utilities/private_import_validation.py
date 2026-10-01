"""Postconditions for semantic private-import rewrites."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

from .qualified_names import FlextInfraUtilitiesQualifiedNames

if TYPE_CHECKING:
    from flext_infra import m, t


class FlextInfraUtilitiesPrivateImportValidation:
    """Reject old import residue or an incomplete public cutover."""

    @staticmethod
    def require_zero_private_import_residue(
        source: str,
        *,
        file_path: Path,
        plan: m.Infra.PrivateImportRewritePlan,
        removals: t.MappingKV[str, set[str]],
    ) -> None:
        """Require old imports/bindings gone and public imports present.

        ``removals`` is every import binding that must disappear: the plan's
        private removals, its superseded public roots, and relocated exports.
        """
        tree = ast.parse(source, filename=str(file_path))
        for absolute_module, relative_module in plan.relative_imports.items():
            level = len(relative_module) - len(relative_module.lstrip("."))
            module = relative_module[level:] or None
            if any(
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module == absolute_module
                for node in ast.walk(tree)
            ):
                msg = (
                    f"absolute same-owner import residue from {absolute_module} "
                    f"in {file_path}"
                )
                raise ValueError(msg)
            imported_symbols = {
                imported.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                and node.level == level
                and node.module == module
                for imported in node.names
            }
            missing = plan.relative_symbols[absolute_module] - imported_symbols
            if missing:
                msg = (
                    f"relative same-owner import {relative_module} missing "
                    f"{sorted(missing)} in {file_path}"
                )
                raise ValueError(msg)
        for module, symbols in removals.items():
            if any(
                isinstance(node, ast.ImportFrom)
                and node.module == module
                and any(imported.name in symbols for imported in node.names)
                for node in ast.walk(tree)
            ):
                msg = f"private import residue from {module} in {file_path}"
                raise ValueError(msg)
        for alias, package in plan.public_imports.items():
            if not any(
                isinstance(node, ast.ImportFrom)
                and node.module == package
                and any(
                    imported.name == alias and imported.asname is None
                    for imported in node.names
                )
                for node in ast.walk(tree)
            ):
                msg = f"public facade import {package}.{alias} missing in {file_path}"
                raise ValueError(msg)
        residue = FlextInfraUtilitiesQualifiedNames.qualified_name_residue(
            source,
            plan.replacements,
        )
        if residue:
            msg = f"private binding residue {sorted(residue)} in {file_path}"
            raise ValueError(msg)


__all__: list[str] = ["FlextInfraUtilitiesPrivateImportValidation"]
