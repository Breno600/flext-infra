"""Namespace-relocation phase of the codemod fixed-point loop.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import m, r, u
from flext_infra.refactor.namespace_relocations import (
    FlextInfraNamespaceRelocationCascade,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraNamespaceRelocationPhase:
    """Relocation callback: the rule catalog's namespace repairs in the loop."""

    name: str = "namespace-relocations"

    @staticmethod
    def apply(
        root: Path,
        preflight: m.Infra.ModScanReport,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
    ) -> p.Result[bool]:
        """Run every declared relocation the preflight captured, per project.

        Returns:
            The resulting ``p.Result[bool]`` — ``True`` marks changed sources.

        """
        cascade = FlextInfraNamespaceRelocationCascade()
        changed = False
        for project_root in u.Infra.governed_project_roots(root):
            if not u.Infra.namespace_enabled(project_root):
                continue
            py_files = cascade.scoped_py_files(project_root)
            findings = cascade.findings_from_report(
                project_root,
                py_files,
                preflight.entries,
            )
            if not findings:
                continue
            cascade.run(
                project_root=project_root,
                rope_project=rope_workspace.rope_project,
                findings=findings,
                py_files=py_files,
            )
            changed = True
        return r[bool].ok(value=changed)


__all__: list[str] = ["FlextInfraNamespaceRelocationPhase"]
