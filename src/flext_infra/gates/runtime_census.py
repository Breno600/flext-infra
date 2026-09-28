"""Runtime enforcement census quality gate.

Imports every ``flext_*`` module in the selected project and runs
``FlextUtilitiesEnforcement.check()`` against every locally-defined class.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import m, u
from flext_infra.validate.runtime_census import FlextInfraRuntimeCensusValidator

from .base_gate import FlextInfraGate

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraRuntimeCensusGate(FlextInfraGate):
    """Post-import runtime enforcement census gate."""

    gate_id: ClassVar[str] = "runtime-census"
    gate_name: ClassVar[str] = "Runtime Enforcement Census"
    can_fix: ClassVar[bool] = False

    @override
    def check(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Run the runtime census scoped to ``project_dir``."""
        _ = ctx
        started = time.monotonic()
        # The filter is the declared project name, never the checkout directory
        # name: a worktree or renamed checkout keeps its manifest identity, and
        # the census discovery keys projects by exactly that pyproject name.
        metadata = u.Infra.read_project_metadata_result(project_dir)
        validator = FlextInfraRuntimeCensusValidator(
            repository_root=project_dir,
            project_filter=(
                metadata.value.project.name if metadata.success else project_dir.name
            ),
        )
        # ``build_report`` (not ``execute``) keeps violations structured so the
        # gate can grade a broken invocation separately from found violations.
        report_result = validator.build_report()
        if report_result.failure:
            return self._build_project_error_gate_result(
                project_dir,
                passed=False,
                errors=[report_result.error or "runtime census failed"],
                started=started,
            )
        report = report_result.value
        return self._build_project_error_gate_result(
            project_dir,
            passed=report.passed,
            errors=list(report.violations),
            started=started,
        )


__all__: list[str] = ["FlextInfraRuntimeCensusGate"]
