"""Absolute, root-alias and lazy-export import routes of the import law.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping

from flext_infra import c, m, t, u
from flext_infra.refactor._import_ast import FlextInfraImportNormalizationAstMixin


class FlextInfraImportNormalizationRoutesMixin(
    FlextInfraImportNormalizationAstMixin,
):
    """Route every import to its canonical source module.

    Relative imports become absolute; a root alias (facade letter,
    operational letter, ``config``/``settings`` or a name the namespace root
    re-exports unchanged) binds through the importing module's own namespace
    root; a concrete object binds through the nearest package ``__init__``
    that publishes it lazily.
    """

    # -- relative -> absolute --------------------------------------------------------

    @classmethod
    def _relative_import_edits(
        cls,
        state: m.Infra.ImportLawPass,
        lines: t.StrSequence,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Rewrite relative imports into their absolute form.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        parts = state.scope.module.split(".")
        package_parts = (
            parts if state.scope.file_path.name == c.Infra.INIT_PY else parts[:-1]
        )
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        for node in cls._iter_imports(state.tree):
            if not isinstance(node, ast.ImportFrom) or not node.level:
                continue
            base = package_parts[: len(package_parts) - (node.level - 1)]
            target = ".".join([*base, node.module or ""]).strip(".")
            indent = cls._line_indent(lines[node.lineno - 1])
            clauses = ", ".join(cls._clause(alias) for alias in node.names)
            edits.append(
                (
                    node.lineno,
                    cls._end_line(node),
                    (f"{indent}from {target} import {clauses}",),
                ),
            )
        return edits

    # -- root aliases and lazy routes -------------------------------------------------

    @classmethod
    def _route_edits(
        cls,
        state: m.Infra.ImportLawPass,
        lines: t.StrSequence,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Rewrite each ``from`` import onto its canonical lazy source.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        if state.scope.direct_imports:
            return ()
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        for node in cls._iter_imports(state.tree):
            if not isinstance(node, ast.ImportFrom) or node.level or not node.module:
                continue
            routed: MutableMapping[str, list[str]] = {}
            for alias in node.names:
                root = cls._root_alias_source(state, node.module, alias)
                if root is not None:
                    # The root publishes the alias under its bound name, so the
                    # long class spelling (``TestsFooConstants as c``) collapses
                    # to the published letter.
                    routed.setdefault(root, []).append(alias.asname or alias.name)
                    continue
                source = cls._lazy_source(state.scope, node.module, alias.name)
                routed.setdefault(source or node.module, []).append(
                    cls._clause(alias),
                )
            if list(routed) == [node.module]:
                continue
            indent = cls._line_indent(lines[node.lineno - 1])
            edits.append(
                (
                    node.lineno,
                    cls._end_line(node),
                    tuple(
                        f"{indent}from {module} import {', '.join(clauses)}"
                        for module, clauses in routed.items()
                    ),
                ),
            )
        return edits

    @staticmethod
    def _root_alias_source(
        state: m.Infra.ImportLawPass,
        module: str,
        alias: ast.alias,
    ) -> str | None:
        """Return the namespace root when one binding is a root alias.

        A facade module keeps the letters it declares and a family package
        keeps its own letter's upstream source; every other routed module
        binds a root alias through its own namespace root.

        Returns:
            The namespace root, or ``None`` when the binding is no root alias.

        """
        scope = state.scope
        bound = alias.asname or alias.name
        published = state.root_exports.get(bound)
        if module == scope.namespace or published is None:
            return None
        aliases = c.Infra.ALIAS_NAMES | c.Infra.IMPORT_LAW_ROOT_SINGLETONS
        if bound not in aliases and published != module:
            return None
        if bound in scope.own_exports or bound == scope.family_letter:
            return None
        return scope.namespace

    @staticmethod
    def _lazy_source(
        scope: m.Infra.ImportLawScope,
        module: str,
        name: str,
    ) -> str | None:
        """Return the nearest package that lazily publishes one leaf object.

        Returns:
            The publishing parent package, or ``None`` when the import already
            binds through a package or no parent publishes the name.

        """
        package, _, leaf = module.rpartition(".")
        if not package or module == scope.module:
            return None
        package_dir = u.Infra.import_package_dir(scope.project_root, package)
        if package_dir is None or (package_dir / leaf).is_dir():
            return None
        if u.Infra.import_lazy_exports(package_dir, package).get(name) != module:
            return None
        return package


__all__: list[str] = ["FlextInfraImportNormalizationRoutesMixin"]
