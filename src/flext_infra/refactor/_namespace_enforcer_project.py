"""Per-project namespace enforcement — extracted concern of the namespace enforcer.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraNamespaceEnforcerProjectMixin:
    """Run the rule catalog's relocations over one project and report the rest.

    The rule catalog owns detection: every namespace law is a rule document
    the one scan engine evaluates. A rule that a rope relocation repairs
    names it under ``metadata.relocation``; this pass runs those relocations
    over what the rules captured and reports the findings that remain. The
    relocation machinery itself is the shared cascade — the same engine the
    mod loop's relocation callback invokes.
    """

    if TYPE_CHECKING:
        _repository_root: Path
        _rope_project: t.Infra.RopeProject

    def _enforce_project(
        self,
        *,
        project_root: Path,
        project_name: str,
        apply: bool,
        gates: t.StrSequence | None = None,
    ) -> m.Infra.ProjectEnforcementReport:
        """Run the relocations of one project and report what remains.

        Returns:
            The resulting ``m.Infra.ProjectEnforcementReport``.

        """
        from flext_infra.refactor._import_enforcement import FlextInfraImportNormalization
        from flext_infra.refactor.namespace_relocations import FlextInfraNamespaceRelocationCascade
        py_files = self._collect_py_files(project_root=project_root)
        if apply:
            # The canonical import-form engine runs over every scoped file
            # before the residue count: its rewrites are the same canonical
            # pass the mod loop's import-normalization phase applies, and a
            # rule capture is not required to reach a file the operator law
            # governs.
            FlextInfraImportNormalization.apply_files(project_root, py_files)
        scan = self._scan_project(project_root=project_root)
        if scan is None:
            return m.Infra.ProjectEnforcementReport(
                project=project_name,
                project_root=str(project_root),
                files_scanned=len(py_files),
                error="mod scan failed; see the published scan evidence",
            )
        findings = FlextInfraNamespaceRelocationCascade.findings_from_report(
            project_root,
            py_files,
            scan.entries,
        )
        remaining, applied = self._relocate_rule_findings(
            project_root=project_root,
            py_files=py_files,
            findings=findings,
            apply=apply,
            gates=gates,
        )
        return m.Infra.ProjectEnforcementReport(
            project=project_name,
            project_root=str(project_root),
            relocation_findings=remaining,
            applied_relocations=applied,
            warnings=scan.detection_only + scan.non_actionable_with_fix,
            files_scanned=len(py_files),
        )

    @staticmethod
    def _scan_project(*, project_root: Path) -> t.Infra.ModScanReport | None:
        """Scan one project once; ``None`` means the scan itself failed.

        Returns:
            The resulting ``t.Infra.ModScanReport | None``.

        """
        from flext_infra.codemod.batch_gates import FlextInfraModGateEngine
        scan = FlextInfraModGateEngine.scan(project_root, fix=False)
        return None if scan.failure else scan.value

    @staticmethod
    def _collect_py_files(*, project_root: Path) -> t.SequenceOf[Path]:
        """Collect Python files for scanning.

        Returns:
            The resulting ``t.SequenceOf[Path]``.

        """
        from flext_infra.refactor.namespace_relocations import FlextInfraNamespaceRelocationCascade
        return FlextInfraNamespaceRelocationCascade.scoped_py_files(project_root)

    def _relocate_rule_findings(
        self,
        *,
        project_root: Path,
        py_files: t.SequenceOf[Path],
        findings: t.SequenceOf[
            t.Pair[c.Infra.CodemodRelocation, m.Infra.ModScanFinding]
        ],
        apply: bool,
        gates: t.StrSequence | None,
    ) -> t.Pair[t.NonNegativeInt, t.NonNegativeInt]:
        """Run the rope relocation each finding's rule declares; count the rest.

        With ``apply`` the relocations run once over the captured values and
        the catalog is scanned again; the returned pair is the residue and
        the number of relocations performed.

        Returns:
            The resulting ``t.Pair[t.NonNegativeInt, t.NonNegativeInt]``.

        """
        from flext_infra.refactor.namespace_relocations import FlextInfraNamespaceRelocationCascade
        if not (apply and findings):
            return len(findings), 0
        cascade = FlextInfraNamespaceRelocationCascade()
        remaining = cascade.run(
            project_root=project_root,
            rope_project=self._rope_project,
            findings=findings,
            py_files=py_files,
            gates=gates,
        )
        return remaining, max(len(findings) - remaining, 0)


__all__: list[str] = ["FlextInfraNamespaceEnforcerProjectMixin"]
