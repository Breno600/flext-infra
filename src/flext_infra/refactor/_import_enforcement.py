"""Canonical FLEXT import-form enforcement engine.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, t
from flext_infra.refactor._import_demotion import (
    FlextInfraImportNormalizationDemotionMixin,
)
from flext_infra.refactor._import_family import FlextInfraImportNormalizationFamilyMixin


class FlextInfraImportNormalization(
    FlextInfraImportNormalizationFamilyMixin,
    FlextInfraImportNormalizationDemotionMixin,
):
    """Rewrite one module's imports into the canonical FLEXT forms.

    The four operator rules this engine owns, in one idempotent pass:

    1. Concrete objects (classes/functions) import lazily, inside the
       outermost function that uses them. Class bases, Pydantic annotations,
       decorators and signature defaults are structural module-definition
       uses and stay eager.
    2. Facade letters follow the layer order (settings, config, c, t, p, m,
       u, siblings, base, services, api, cli): a module-level letter binding
       at or after the module's own layer is demoted to the point of use when
       every use sits inside a function body.
    3. Letters of one package bind in ONE root-combined statement
       (``from pkg import c, m, p, t, u``); facade-file, alias-split and
       relative letter forms rewrite into it.
    4. Objects import through the family ``__init__``
       (``from pkg._models import X``); leaf-module paths flatten when the
       family init publishes the name (its ``TYPE_CHECKING`` imports, lazy
       export map and ``__all__`` are the export SSOT); internal family
       wiring the init does not publish stays leaf.

    ``try/except ImportError`` import guards are removed and their names
    re-bound at the point of use; no half-initialized ``= None`` fallback
    survives. A guarded name the module still uses at definition time falls
    back to a plain module-level import, never to a silent ``None``.
    """

    @classmethod
    def apply_files(cls, project_root: Path, files: t.SequenceOf[Path]) -> bool:
        """Normalize every given file; return whether any source changed.

        Returns:
            Whether at least one file changed.

        """
        changed = False
        for file_path in files:
            try:
                source = file_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            except OSError:
                continue
            normalized = cls.normalize_source(
                project_root=project_root,
                file_path=file_path,
                source=source,
            )
            if normalized is None or normalized == source:
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
        """Return the canonical form of one module, or ``None`` when out of scope.

        Returns:
            The resulting ``str | None``.

        """
        located = cls._locate(project_root, file_path)
        if located is None:
            return None
        package, module_name = located
        current = source
        for _ in range(c.Infra.IMPORT_NORMALIZATION_MAX_PASSES):
            updated = cls._one_pass(
                project_root=project_root,
                file_path=file_path,
                package=package,
                module_name=module_name,
                source=current,
            )
            if updated is None or updated == current:
                break
            current = updated
        return current if current != source else None

    # -- one normalization pass ----------------------------------------------------

    @classmethod
    def _one_pass(
        cls,
        *,
        project_root: Path,
        file_path: Path,
        package: str,
        module_name: str,
        source: str,
    ) -> str | None:
        """Run one convergence pass; each rewrite category applies alone.

        A category whose own edits collide is skipped; the outer pass loop
        re-parses the converged text and retries it on the next pass.

        Returns:
            The resulting ``str | None``.

        """
        # One rewrite category per pass: every category's edits are computed
        # against the text they mutate, so categories never share a pass.
        tree = cls._parse(source)
        if tree is None:
            return None
        builders = (
            lambda: cls._relative_import_edits(
                tree,
                source,
                package,
                module_name,
                file_path,
            ),
            lambda: cls._letter_merge_edits(tree, source, package),
            lambda: cls._flatten_edits(
                tree,
                source,
                package,
                file_path,
                cls._family_exports(project_root, package),
            ),
            lambda: cls._lazy_demotion_edits(
                tree,
                source,
                package,
                file_path,
                cls._family_exports(project_root, package),
            ),
            lambda: cls._foundation_routing_edits(tree, source, package, file_path),
            lambda: cls._self_family_unflatten_edits(
                tree,
                source,
                package,
                file_path,
                project_root,
            ),
        )
        for build in builders:
            applied = cls._apply_edits(source, build())
            if applied is None or applied == source:
                continue
            return applied
        return None


__all__: list[str] = ["FlextInfraImportNormalization"]
