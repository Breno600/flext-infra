"""Mod loop repair phases invoked as callbacks of the joint fixed point.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import m, p, u
from flext_infra.refactor._accessor_rewrite import (
    FlextInfraAccessorMigrationRewriteMixin,
)

if TYPE_CHECKING:
    from pathlib import Path


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
        from flext_infra.refactor._import_enforcement import FlextInfraImportNormalization
        from flext_infra.refactor.namespace_relocations import FlextInfraNamespaceRelocationCascade
        changed = False
        for project_root in u.Infra.governed_project_roots(root):
            if not u.Infra.namespace_enabled(project_root):
                continue
            scoped = FlextInfraNamespaceRelocationCascade.scoped_py_files(project_root)
            if FlextInfraImportNormalization.apply_files(project_root, scoped):
                changed = True
        return r[bool].ok(value=changed)


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
        from flext_infra.refactor.namespace_relocations import FlextInfraNamespaceRelocationCascade
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


class FlextInfraAccessorRenamePhase(FlextInfraAccessorMigrationRewriteMixin):
    """Accessor callback: origin-owned rename catalog repairs in the loop.

    Reuses the accessor migration's origin-aware rewrite, so a homonym the
    catalog does not own is never renamed inside the loop either.
    """

    name: str = "accessor-rename"

    def apply(
        self,
        root: Path,
        _preflight: m.Infra.ModScanReport,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
    ) -> p.Result[bool]:
        """Apply the rename catalog over the governed files of the repository.

        Returns:
            The resulting ``p.Result[bool]`` — ``True`` marks changed sources.

        """
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


__all__: list[str] = [
    "FlextInfraAccessorRenamePhase",
    "FlextInfraImportNormalizationPhase",
    "FlextInfraNamespaceRelocationPhase",
]
