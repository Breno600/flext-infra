"""Import-normalization phase of the codemod fixed-point loop.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import m, r, u
from flext_infra.refactor._import_enforcement import FlextInfraImportNormalization
from flext_infra.refactor.namespace_relocations import (
    FlextInfraNamespaceRelocationCascade,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraImportNormalizationPhase:
    """Import-form callback: the canonical import law in the loop.

    The engine self-scans every governed source file — leaf flattening,
    lazy placement and guard cleanup are semantic judgments no ast-grep
    capture owns — so this phase does not wait for a rule finding before
    normalizing a file.
    """

    name: str = "import-normalization"

    @staticmethod
    def apply(
        root: Path,
        _preflight: m.Infra.ModScanReport,
        _rope_workspace: p.Infra.RopeWorkspaceDsl,
    ) -> p.Result[bool]:
        """Normalize every governed project's source imports.

        Returns:
            The resulting ``p.Result[bool]`` — ``True`` marks changed sources.

        """
        changed = False
        for project_root in u.Infra.governed_project_roots(root):
            if not u.Infra.namespace_enabled(project_root):
                continue
            scoped = FlextInfraNamespaceRelocationCascade.scoped_py_files(project_root)
            if FlextInfraImportNormalization.apply_files(project_root, scoped):
                changed = True
        return r[bool].ok(value=changed)


__all__: list[str] = ["FlextInfraImportNormalizationPhase"]
