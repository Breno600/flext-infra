"""Absolute, root-alias and lazy-export import routes of the import law.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping

from flext_infra import c, m, t
from flext_infra._utilities.import_law import FlextInfraUtilitiesImportLaw
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
        tree: ast.Module,
        lines: t.StrSequence,
        scope: m.Infra.ImportLawScope,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Rewrite relative imports into their absolute form.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        parts = scope.module.split(".")
        package_parts = (
            parts if scope.file_path.name == c.Infra.INIT_PY else parts[:-1]
        )
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        for node in cls._iter_imports(tree):
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
        tree: ast.Module,
        lines: t.StrSequence,
        scope: m.Infra.ImportLawScope,
    ) -> t.SequenceOf[tuple[int, int, t.StrSequence]]:
        """Rewrite each ``from`` import onto its canonical lazy source.

        Returns:
            The resulting ``t.SequenceOf[tuple[int, int, t.StrSequence]]``.

        """
        root_exports = FlextInfraUtilitiesImportLaw.lazy_exports(
            scope.namespace_dir,
            scope.namespace,
        )
        edits: t.MutableSequenceOf[tuple[int, int, t.StrSequence]] = []
        for node in cls._iter_imports(tree):
            if not isinstance(node, ast.ImportFrom) or node.level or not node.module:
                continue
            routed: MutableMapping[str, list[str]] = {}
            for alias in node.names:
                source = cls._root_alias_source(
                    node.module,
                    alias,
                    scope,
                    root_exports,
                ) or cls._lazy_source(node.module, alias.name, scope)
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

    @classmethod
    def _root_alias_source(
        cls,
        module: str,
        alias: ast.alias,
        scope: m.Infra.ImportLawScope,
        root_exports: t.StrMapping,
    ) -> str | None:
        """Return the namespace root when one binding is a root alias.

        A facade module keeps the letters it declares, a family package keeps
        its own letter's upstream source, and the settings/config layers keep
        their own law; every other module binds a root alias through its own
        namespace root.

        Returns:
            The namespace root, or ``None`` when the binding is no root alias.

        """
        bound = alias.asname or alias.name
        if module == scope.namespace or bound not in root_exports:
            return None
        aliases = c.Infra.ALIAS_NAMES | c.Infra.IMPORT_LAW_ROOT_SINGLETONS
        if bound not in aliases and root_exports[bound] != module:
            return None
        order = FlextInfraUtilitiesImportLaw.import_layer_order()
        if (
            bound in scope.own_exports
            or bound == scope.family_letter
            or order[scope.layer] in c.Infra.IMPORT_LAW_ROOT_SINGLETONS
        ):
            return None
        return scope.namespace

    @classmethod
    def _lazy_source(
        cls,
        module: str,
        name: str,
        scope: m.Infra.ImportLawScope,
    ) -> str | None:
        """Return the nearest package that lazily publishes one leaf object.

        Returns:
            The publishing parent package, or ``None`` when the import already
            binds through a package or no parent publishes the name.

        """
        package, _, leaf = module.rpartition(".")
        if not package or module == scope.module:
            return None
        package_dir = FlextInfraUtilitiesImportLaw.package_dir(
            scope.project_root,
            package,
        )
        if package_dir is None or (package_dir / leaf).is_dir():
            return None
        exports = FlextInfraUtilitiesImportLaw.lazy_exports(package_dir, package)
        if exports.get(name) != module:
            return None
        return package


__all__: list[str] = ["FlextInfraImportNormalizationRoutesMixin"]
