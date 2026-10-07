"""Documentation builder service.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_infra.constants import c
from flext_infra.docs.base import FlextInfraDocServiceBase
from flext_infra.utilities import u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra.docs.models import m
    from flext_infra.protocols import p
    from flext_infra.docs.typings import t


class FlextInfraDocBuilder(FlextInfraDocServiceBase):
    """Build MkDocs sites for governed FLEXT scopes."""

    def build(
        self,
        repository_root: Path,
        *,
        projects: t.StrSequence | None = None,
        output_dir: Path | str | None = None,
    ) -> p.Result[t.SequenceOf[m.Infra.DocsPhaseReport]]:
        """Build MkDocs sites across project scopes.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.DocsPhaseReport]]``.

        """
        return self.run_scoped_docs(
            repository_root,
            projects=projects,
            output_dir=output_dir,
            handler=self._build_scope,
        )

    @override
    def execute(self) -> p.Result[bool]:
        """Execute the configured docs build flow.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return self._propagate_phase_outcome(
            "build",
            self.build(
                repository_root=self.repository_root,
                projects=self.selected_projects,
                output_dir=self.output_dir,
            ),
            failure_predicate=lambda report: report.result == c.Infra.ResultStatus.FAIL,
        )

    def _build_scope(self, scope: m.Infra.DocScope) -> m.Infra.DocsPhaseReport:
        """Build one scope via the docs build utilities and persist its reports.

        Returns:
            The resulting ``m.Infra.DocsPhaseReport``.

        """
        report: m.Infra.DocsPhaseReport = u.Infra.docs_run_mkdocs(scope)
        u.Infra.docs_write_build_reports(scope, report)
        self.logger.info(
            "docs_build_scope_completed",
            project=scope.name,
            phase=c.Infra.DIR_BUILD,
            result=report.result,
            reason=report.reason,
        )
        return report


__all__: list[str] = ["FlextInfraDocBuilder"]
