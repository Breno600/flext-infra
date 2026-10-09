"""Accessor-rename phase of the codemod fixed-point loop.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import m, p, r, u
from flext_infra.refactor._accessor_rewrite import (
    FlextInfraAccessorMigrationRewriteMixin,
)


class FlextInfraAccessorRenamePhase(FlextInfraAccessorMigrationRewriteMixin):
    """Accessor callback: origin-owned rename catalog repairs in the loop.

    Reuses the accessor migration's origin-aware rewrite, so a homonym the
    catalog does not own is never renamed inside the loop either.
    """

    name: str = "accessor-rename"

    def apply(
        self,
        root: Path,
        preflight: m.Infra.ModScanReport,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
    ) -> p.Result[bool]:
        """Apply the rename catalog over the governed files of the repository.

        Returns:
            The resulting ``p.Result[bool]`` — ``True`` marks changed sources.

        """
        del preflight
        iter_result = u.Infra.iter_python_files(
            m.Infra.SourceScanRequest(
                project_roots=tuple(u.Infra.governed_project_roots(root)),
            ),
        )
        if iter_result.failure:
            return r[bool].from_failure(iter_result)
        changed = False
        for py_file in iter_result.value:
            read = u.Cli.files_read_text(py_file)
            if read.failure:
                return r[bool].from_failure(read)
            updated_source, rewrite_changes = self._apply_automated_rewrites(
                rope_workspace.rope_project,
                py_file,
                read.value,
            )
            if not any(change.automated for change in rewrite_changes):
                continue
            ok, report = u.Infra.protected_source_write(
                py_file,
                request=m.Infra.ProtectedSourceWriteRequest(
                    workspace=root,
                    updated_source=updated_source,
                    gates=(),
                ),
            )
            if not ok:
                return r[bool].fail(
                    "; ".join(report[:3]) or "protected write failed",
                )
            changed = True
        return r[bool].ok(value=changed)


__all__: list[str] = ["FlextInfraAccessorRenamePhase"]
