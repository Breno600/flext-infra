"""Per-project namespace enforcement — extracted concern of the namespace enforcer.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import m
from flext_infra.refactor.namespace_relocations import (
    FlextInfraNamespaceRelocationCascade,
)

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
        py_files = self._collect_py_files(project_root=project_root)
        return m.Infra.ProjectEnforcementReport(
            project=project_name,
            project_root=str(project_root),
            relocation_findings=self._relocate_rule_findings(
                project_root=project_root,
                py_files=py_files,
                apply=apply,
                gates=gates,
            ),
            files_scanned=len(py_files),
        )

    @staticmethod
    def _collect_py_files(*, project_root: Path) -> t.SequenceOf[Path]:
        """Collect Python files for scanning.

        Returns:
            The resulting ``t.SequenceOf[Path]``.

        """
        return FlextInfraNamespaceRelocationCascade.scoped_py_files(project_root)

    def _relocate_rule_findings(
        self,
        *,
        project_root: Path,
        py_files: t.SequenceOf[Path],
        apply: bool,
        gates: t.StrSequence | None,
    ) -> t.NonNegativeInt:
        """Run the rope relocation each finding's rule declares; count the rest.

        With ``apply`` the relocations run once over the captured values and
        the catalog is scanned again; the returned count is what remains.

        Returns:
            The resulting ``t.NonNegativeInt``.

        """
        cascade = FlextInfraNamespaceRelocationCascade()
        findings = cascade.scan_findings(project_root, py_files)
        if not (apply and findings):
            return len(findings)
        return cascade.run(
            project_root=project_root,
            rope_project=self._rope_project,
            findings=findings,
            py_files=py_files,
            gates=gates,
        )


__all__: list[str] = ["FlextInfraNamespaceEnforcerProjectMixin"]
