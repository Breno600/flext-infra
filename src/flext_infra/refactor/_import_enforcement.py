"""Canonical FLEXT import-law enforcement engine.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from pathlib import Path

from flext_infra import c, m, t, u
from flext_infra.refactor._import_placement import (
    FlextInfraImportNormalizationPlacementMixin,
)
from flext_infra.refactor._import_routes import FlextInfraImportNormalizationRoutesMixin


class FlextInfraImportNormalization(
    FlextInfraImportNormalizationRoutesMixin,
    FlextInfraImportNormalizationPlacementMixin,
):
    """Rewrite one module's imports into the FLEXT import law.

    The law (operator-ruling-2026-10-08-import-law), applied to every module
    of a namespace (the source package or an internal tier such as
    ``tests``) except the generated package initializers:

    1. Every import lives at module level; ``try/except ImportError`` guards
       become plain imports.
    2. Imports follow the tooling layer order (settings, config, c, t, p, m,
       u, other, base, services, api, cli): a reverse import read only in
       annotations moves under ``if TYPE_CHECKING:``; a reverse import read
       at runtime keeps its place and its finding, for manual repair.
    3. A root alias (facade and operational letters, ``config``,
       ``settings``, names the namespace root re-exports) binds through the
       module's own namespace root; facade modules keep the letters they
       declare, family packages keep their own letter's upstream source and
       settings/config modules keep their own law.
    4. A concrete object binds through the nearest package ``__init__`` that
       publishes it lazily.

    ``make mod`` runs it over every governed file; the ``make fix`` lint
    recipe ``normalize-imports`` runs it over each file Ruff reports for
    ``import-outside-top-level``, so both verbs converge on one fixed point.
    """

    @classmethod
    def apply_files(cls, project_root: Path, files: t.SequenceOf[Path]) -> bool:
        """Normalize every given file; return whether any source changed.

        Returns:
            Whether at least one file changed.

        """
        changed = False
        for file_path in files:
            source = file_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            normalized = cls.normalize_source(
                project_root=project_root,
                file_path=file_path,
                source=source,
            )
            if normalized is None:
                continue
            file_path.write_text(normalized, encoding=c.Cli.ENCODING_DEFAULT)
            changed = True
        return changed

    @classmethod
    def normalize_source(
        cls,
        *,
        project_root: Path,
        file_path: Path,
        source: str,
    ) -> str | None:
        """Return the canonical form of one module, or ``None`` when unchanged.

        Returns:
            The rewritten source, or ``None`` when the module is out of scope
            or already canonical.

        """
        if file_path.name == c.Infra.INIT_PY:
            return None
        located = u.Infra.import_namespace(project_root, file_path)
        if located is None:
            return None
        namespace_dir, module = located
        root_exports = u.Infra.import_lazy_exports(namespace_dir, namespace_dir.name)
        current = source
        for _ in range(c.Infra.IMPORT_NORMALIZATION_MAX_PASSES):
            tree = ast.parse(current, filename=str(file_path))
            state = m.Infra.ImportLawPass(
                scope=m.Infra.ImportLawScope(
                    project_root=project_root.resolve(),
                    file_path=file_path,
                    namespace_dir=namespace_dir,
                    module=module,
                    layer=u.Infra.module_import_layer(module),
                    own_exports=cls._declared_exports(tree),
                    family_letter=cls._family_letter(namespace_dir, file_path),
                    direct_imports=u.Infra.import_direct_module(
                        namespace_dir,
                        file_path,
                    ),
                ),
                tree=tree,
                parents=cls._parent_map(tree),
                bindings=cls._module_bindings(tree),
                root_exports=root_exports,
            )
            updated = cls._one_pass(state, current)
            if updated is None:
                break
            current = updated
        return current if current != source else None

    @classmethod
    def _one_pass(cls, state: m.Infra.ImportLawPass, source: str) -> str | None:
        """Apply the first rewrite category that changes the module.

        Every category's edits are computed against the text they mutate, so
        categories never share a pass; the caller re-parses between passes.

        Returns:
            The rewritten source, or ``None`` when every category is a no-op.

        Raises:
            ValueError: If one category plans overlapping edits.

        """
        lines = source.splitlines()
        builders = (
            lambda: cls._relative_import_edits(state, lines),
            lambda: cls._guard_edits(state.tree, lines),
            lambda: cls._placement_edits(state, lines),
            lambda: cls._route_edits(state, lines),
        )
        for build in builders:
            edits = build()
            if not edits:
                continue
            applied = cls._apply_edits(source, edits)
            if applied is None:
                msg = f"{state.scope.file_path}: overlapping import-law edits {edits}"
                raise ValueError(msg)
            if applied != source:
                return applied
        return None

    @staticmethod
    def _declared_exports(tree: ast.Module) -> frozenset[str]:
        """Return the names one module declares in its literal ``__all__``.

        Returns:
            The resulting ``frozenset[str]``.

        """
        for node in tree.body:
            target = (
                node.targets[0]
                if isinstance(node, ast.Assign) and len(node.targets) == 1
                else node.target
                if isinstance(node, ast.AnnAssign)
                else None
            )
            value = node.value if isinstance(node, ast.Assign | ast.AnnAssign) else None
            if (
                isinstance(target, ast.Name)
                and target.id == "__all__"
                and isinstance(value, ast.List | ast.Tuple)
            ):
                return frozenset(
                    element.value
                    for element in value.elts
                    if isinstance(element, ast.Constant)
                    and isinstance(element.value, str)
                )
        return frozenset()

    @staticmethod
    def _family_letter(namespace_dir: Path, file_path: Path) -> str | None:
        """Return the facade letter of the family package holding one module.

        Returns:
            The family letter, or ``None`` outside every family package.

        """
        directories = {
            family.directory: letter
            for letter, family in u.Infra.facade_families().items()
        }
        relative = file_path.resolve().relative_to(namespace_dir.resolve())
        return next(
            (directories[part] for part in relative.parts[:-1] if part in directories),
            None,
        )


__all__: list[str] = ["FlextInfraImportNormalization"]
