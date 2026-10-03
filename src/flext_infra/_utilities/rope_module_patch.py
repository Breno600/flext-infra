"""Small Rope-driven text patch helpers for governed module aliases.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from flext_infra._utilities._rope_analysis.exports import (
    FlextInfraUtilitiesRopeAnalysisExports,
)

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesRopeModulePatch:
    """String-level patch helpers driven by Rope-discovered module rules."""

    @staticmethod
    def runtime_alias_bindings(
        source: str,
        *,
        alias: str,
    ) -> t.VariadicTuple[ast.Assign | ast.AnnAssign]:
        """Return only direct module bindings for the declared alias.

        Returns:
            Only direct module bindings for the declared alias.

        """
        return tuple(
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.Assign | ast.AnnAssign)
            and any(
                isinstance(target, ast.Name) and target.id == alias
                for target in (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
            )
        )

    @classmethod
    def facade_letter_names_source(cls, source: str) -> frozenset[str]:
        """Return the exported lower-case names bound directly to a class.

        A facade letter (ADR-015 R1a, ADR-018 p.1) is a published alias whose
        single module binding names a class the module declares or imports,
        e.g. ``c = FlextCliConstants`` or ``tm = FlextTestsMatchersUtilities.X``.
        Singleton instances (``cli = FlextCli.fetch_global()``), functions
        (``main``), and attributes of instances (``lazy.attribute``) stay in
        the namespace root that declares them and are never inherited.

        Returns:
            The exported lower-case names bound directly to a class.

        """
        tree = ast.parse(source)
        class_names = {
            node.name for node in tree.body if isinstance(node, ast.ClassDef)
        } | {
            alias.asname or alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        letters: set[str] = set()
        for name in FlextInfraUtilitiesRopeAnalysisExports.public_export_names_source(
            source,
        ):
            if not name.islower() or name.startswith("_"):
                continue
            bindings = cls.runtime_alias_bindings(source, alias=name)
            if len(bindings) != 1 or bindings[0].value is None:
                continue
            root = bindings[0].value
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in class_names:
                letters.add(name)
        return frozenset(letters)

    @staticmethod
    def absolute_import_sources_source(source: str, *, name: str) -> t.StrSequence:
        """Return the top-level packages an absolute ``from X import`` binds name from.

        Returns:
            The top-level packages an absolute ``from X import`` binds name from.

        """
        return tuple(
            dict.fromkeys(
                node.module.split(".", 1)[0]
                for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module is not None
                and any((alias.asname or alias.name) == name for alias in node.names)
            ),
        )

    @classmethod
    def remove_runtime_alias_export(cls, source: str, *, alias: str) -> str:
        """Return source with one published alias letter removed from ``__all__``.

        The owner of a declared-but-unbound letter is the declaration itself:
        removing the letter repairs the published surface without inventing a
        runtime binding the module never wrote.

        Returns:
            Source with one published alias letter removed from ``__all__``.

        """
        exports = FlextInfraUtilitiesRopeAnalysisExports.public_export_names_source(
            source,
        )
        if alias not in exports:
            return source
        return cls._rewrite_all_declaration(
            source,
            names=[name for name in exports if name != alias],
        )

    @staticmethod
    def _rewrite_all_declaration(source: str, *, names: list[str]) -> str:
        """Publish exactly ``names`` through the canonical ``__all__`` rewrite.

        Returns:
            The resulting ``str``.

        Raises:
            ValueError: If ambiguous __all__ declarations during facade repair; or if
                facade repair requires an explicit literal __all__ declaration; or if
                __all__ declaration has no complete source span; or if __all__
                declaration shares a source line with another statement.

        """
        declarations = [
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.Assign | ast.AnnAssign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
            )
        ]
        if len(declarations) > 1:
            message = "ambiguous __all__ declarations during facade repair"
            raise ValueError(message)
        rendered = f"__all__: list[str] = {names!r}\n"
        if not declarations:
            return source.rstrip() + "\n\n" + rendered
        declaration = declarations[0]
        if not isinstance(declaration.value, ast.List | ast.Tuple) or (
            isinstance(declaration, ast.Assign) and len(declaration.targets) != 1
        ):
            message = "facade repair requires an explicit literal __all__ declaration"
            raise ValueError(message)
        lines = source.splitlines(keepends=True)
        if declaration.end_lineno is None or declaration.end_col_offset is None:
            message = "__all__ declaration has no complete source span"
            raise ValueError(message)
        if lines[declaration.lineno - 1][: declaration.col_offset].strip() or (
            (
                trailing := lines[declaration.end_lineno - 1][
                    declaration.end_col_offset :
                ].strip()
            )
            and not trailing.startswith("#")
        ):
            message = "__all__ declaration shares a source line with another statement"
            raise ValueError(message)
        lines[declaration.lineno - 1 : declaration.end_lineno] = [rendered]
        return "".join(lines)


__all__: list[str] = ["FlextInfraUtilitiesRopeModulePatch"]
