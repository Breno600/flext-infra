"""Namespace, layer and lazy-export facts of the FLEXT import law.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, config, t
from flext_infra._utilities import (
    FlextInfraUtilitiesCodegenNamespace,
    FlextInfraUtilitiesRopeAnalysisSourceScan,
)


class FlextInfraUtilitiesImportLaw:
    """Resolve the namespace, layer and lazy exports one import law decides on.

    A namespace is a top-level package of a project: the source package
    under ``src/`` or an internal tier (``tests``, ``examples``, ``scripts``)
    whose directory carries an ``__init__.py``. Layers come from the tooling
    ``lazy-init.import-layer-order``; a module's layer is the first path
    segment, from its namespace downwards, that names a layer either
    directly (``settings``, ``config``, ``base``, ``services``, ``api``,
    ``cli``) or through the facade family it stands for (``_models`` and
    ``models.py`` stand for ``m``). A module naming no layer sits in the
    ``other`` slot.
    """

    @classmethod
    def import_namespace(
        cls,
        project_root: Path,
        file_path: Path,
    ) -> t.Pair[Path, str] | None:
        """Return the namespace directory and dotted module of one file.

        Returns:
            The namespace directory and the file's dotted module name, or
            ``None`` when the file belongs to no namespace of the project.

        """
        root = project_root.resolve()
        resolved = file_path.resolve()
        if not resolved.is_relative_to(root):
            return None
        relative = resolved.relative_to(root)
        source_dir = root / c.Infra.DEFAULT_SRC_DIR
        if relative.parts and relative.parts[0] == c.Infra.DEFAULT_SRC_DIR:
            relative = resolved.relative_to(source_dir)
            base = source_dir
        else:
            base = root
        namespace_name, *module_parts = relative.parts
        if not module_parts:
            return None
        namespace_dir = base / namespace_name
        if not (namespace_dir / c.Infra.INIT_PY).is_file():
            return None
        parts = relative.with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        return namespace_dir, ".".join(parts)

    @classmethod
    def import_layer_order(cls) -> t.StrSequence:
        """Return the declared import-layer order.

        Returns:
            The layer names, lowest layer first.

        """
        return tuple(config.Infra.tooling.lazy_init.import_layer_order)

    @classmethod
    def module_import_layer(cls, module: str) -> int:
        """Return the layer rank of one dotted module of a namespace.

        Returns:
            The index of the module's layer in the declared order.

        """
        order = cls.import_layer_order()
        families = {
            family.module: letter
            for letter, family in (
                FlextInfraUtilitiesCodegenNamespace.facade_families().items()
            )
        }
        for part in module.split(".")[1:]:
            stem = part.lstrip("_")
            layer = families.get(stem, stem)
            if layer in order:
                return order.index(layer)
        return order.index(c.Infra.IMPORT_LAW_OTHER_LAYER)

    @classmethod
    def lazy_exports(cls, package_dir: Path, package: str) -> t.StrMapping:
        """Map each name one package ``__init__`` publishes to its module.

        Relative targets resolve against the package; a target naming another
        distribution (``flext_cli``) stays absolute.

        Returns:
            The published name to absolute defining module mapping.

        Raises:
            ValueError: If the package init declares its lazy map indirectly.

        """
        init = package_dir / c.Infra.INIT_PY
        if not init.is_file():
            return {}
        targets, references = (
            FlextInfraUtilitiesRopeAnalysisSourceScan.lazy_import_mapping_source(
                init.read_text(encoding=c.Cli.ENCODING_DEFAULT),
            )
        )
        if references:
            msg = f"{init}: lazy map is declared through {', '.join(references)}"
            raise ValueError(msg)
        return {
            name: f"{package}{module}" if module.startswith(".") else module
            for module, names in targets
            for name in names
        }


__all__: list[str] = ["FlextInfraUtilitiesImportLaw"]
