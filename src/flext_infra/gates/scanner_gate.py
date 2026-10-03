"""Gate template for per-file, Rope-backed scanners.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraScannerGateMixin(FlextInfraGate):
    """Mixin for gates that detect per-file issues via a rope-backed scanner.

    Subclasses provide ``scan_error_message`` and implement
    ``_detect_file_issues``.  The shared ``check`` method handles file
    discovery, rope-project lifecycle, and result assembly.
    """

    scan_error_message: ClassVar[str] = ""
    requires_python_targets: ClassVar[bool] = True

    @override
    def check(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.GateExecution:
        """Scan all Python files in ``project_dir`` and report detected issues.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        """
        _ = ctx
        started = time.monotonic()
        files_result = u.Infra.iter_python_files(
            m.Infra.SourceScanRequest(project_roots=(project_dir,)),
        )
        if files_result.failure:
            return self._build_single_issue_result(
                project_dir,
                Path(c.PYPROJECT_FILENAME),
                files_result.error or self.scan_error_message,
                passed=False,
                started=started,
            )
        if not files_result.value:
            return self._skip_result(project_dir, started)
        rope_project = u.Infra.init_rope_project(project_dir)
        try:
            issues = [
                issue
                for file_path in files_result.value
                for issue in self._detect_file_issues(
                    file_path,
                    project_dir,
                    rope_project,
                )
            ]
        finally:
            rope_project.close()
        return self._detected_gate_execution(
            project_dir,
            issues=issues,
            started=started,
        )

    @staticmethod
    def _detect_file_issues(
        file_path: Path,
        project_dir: Path,
        rope_project: t.Infra.RopeProject,
    ) -> t.SequenceOf[m.Infra.Issue]:
        """Override in subclass to detect issues for a single file.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.Issue]``.

        """
        _ = file_path, project_dir, rope_project
        return ()


__all__: list[str] = ["FlextInfraScannerGateMixin"]
