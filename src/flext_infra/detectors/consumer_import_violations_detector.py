"""R1 consumer import grammar detector (consumption-law.md section R1).

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from flext_core import u as core_u
from flext_infra import m, u as infra_u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import t


class FlextInfraConsumerImportViolationsDetector:
    """Detect consumer import grammar violations (R1).

    Family roots derive at runtime from the published family surface
    (``core_u.project_alias_owners()``) — prefix discovery plus the lazy
    export structural proof, never a frozen roster. Legality per statement:
    ``from <pkg_root> import X`` is legal iff ``X`` is published by that
    root; any ``pkg.<submodule>`` path is a violation; wildcard imports
    cannot prove membership and stay violations. Fix hints use the derived
    compatibility rename map (long public names -> canonical letters).
    """

    @classmethod
    def _family_roots(cls) -> frozenset[str]:
        """Published family member roots at runtime derivation."""
        return frozenset(core_u.project_alias_owners())

    @staticmethod
    def _importer_root(file_path: Path) -> str:
        """Return the root package name of the module being inspected."""
        module = infra_u.Infra.package_name(file_path) or ""
        return module.split(".", maxsplit=1)[0]

    @staticmethod
    def _published_symbols(root: str) -> frozenset[str]:
        """Return the root's published ``__all__`` membership contract."""
        module = __import__(root)
        published = getattr(module, "__all__", None)
        if published is None:
            msg = f"R1 detector: family root {root!r} publishes no __all__"
            raise ValueError(msg)
        return frozenset(published)

    @classmethod
    def detect_file(
        cls, ctx: m.Infra.DetectorContext
    ) -> t.VariadicTuple[m.Infra.ConsumerImportViolation]:
        """Detect R1 violations in one file with true statement line numbers."""
        path: Path = ctx.file_path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        importer_root = FlextInfraConsumerImportViolationsDetector._importer_root(path)
        family_roots = FlextInfraConsumerImportViolationsDetector._family_roots()
        renames = core_u.compatibility_alias_renames()

        def violation(
            lineno: int, target: str, symbol: str, detail: str
        ) -> m.Infra.ConsumerImportViolation:
            """Build one typed violation with the true line and a derived hint."""
            canonical = renames.get(symbol)
            hint = (
                f"; canonical form: from {target.split('.', maxsplit=1)[0]} import {canonical}"
                if canonical
                else ""
            )
            return m.Infra.ConsumerImportViolation(
                file=str(path),
                line=lineno,
                current_import=f"from {target} import {symbol}",
                target_package=target.split(".", maxsplit=1)[0],
                imported_path=target,
                imported_symbol=symbol,
                detail=f"{detail}{hint}",
            )

        violations: list[m.Infra.ConsumerImportViolation] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level != 0:
                continue
            target = node.module or ""
            root = target.split(".", maxsplit=1)[0]
            if root not in family_roots or root == importer_root:
                continue
            published = FlextInfraConsumerImportViolationsDetector._published_symbols(
                root
            )
            if "." in target:
                violations.append(
                    violation(
                        node.lineno,
                        target,
                        target.rsplit(".", maxsplit=1)[-1],
                        "submodule path import violates R1 facade-only grammar",
                    )
                )
                continue
            for alias in node.names:
                symbol = alias.name
                if symbol == "*":
                    violations.append(
                        violation(
                            node.lineno,
                            f"{target}.<star>",
                            "(wildcard)",
                            "wildcard import cannot prove published membership",
                        )
                    )
                    continue
                if symbol in published:
                    continue
                violations.append(
                    violation(
                        node.lineno,
                        target,
                        symbol,
                        "symbol not published by target root (R1 facade-only grammar)",
                    )
                )
        return tuple(violations)


__all__: list[str] = ["FlextInfraConsumerImportViolationsDetector"]
