"""Project-layout quality gate (flext-0wuz, epic flext-hzox).

Reports layout-SSOT violations per project. Severity is config-driven
(``codegen.yaml layout.severity``); every reported finding fails the gate.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import ClassVar, override

from flext_infra import config, m, t
from flext_infra.codegen.layout import FlextInfraCodegenLayout

from .base_gate import FlextInfraGate


class FlextInfraLayoutGate(FlextInfraGate):
    """Layout-SSOT conformance gate backed by the layout engine check mode."""

    gate_id: ClassVar[str] = "layout"
    gate_name: ClassVar[str] = "Project Layout"
    can_fix: ClassVar[bool] = False

    @override
    def check(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Report layout violations for ``project_dir`` from the layout SSOT."""
        started = time.monotonic()
        spec = config.Infra.codegen.layout
        engine = FlextInfraCodegenLayout(repository_root=ctx.repository_root)
        report = engine.check_project(project_dir)
        warning = spec.severity == "warning"
        report_findings: t.VariadicTuple[m.Infra.LayoutFinding] = report.findings
        issues = tuple(
            m.Infra.Issue(
                file=str(project_dir / finding.path),
                line=1,
                column=1,
                code=f"{self.gate_id}-{finding.rule}",
                message=finding.message,
                severity="WARNING" if warning or finding.rule == "review" else "ERROR",
            )
            for finding in report_findings
        )
        passed = not issues
        return self._build_check_gate_execution(
            project_dir,
            passed=passed,
            issues=issues,
            raw_output="\n".join(issue.formatted for issue in issues),
            started=started,
            ctx=ctx,
        )


__all__: list[str] = ["FlextInfraLayoutGate"]
