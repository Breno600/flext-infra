"""Tier-whitelist / abstraction-boundary quality gate.

Replaces the legacy ``ban-direct-*.yml`` ast-grep rules with the
OWNERS-driven ``FlextInfraValidateTierWhitelist`` rope detector.

The gate reports every violation the detector found. ``execute()`` collapses
the report into a single ``bool`` plus a count, which made the gate emit one
aggregate issue pinned to the repository root -- unactionable, and an
aggregation ``fail-loud`` forbids. ``build_report()`` is the same scan and
already carries one entry per violation, each naming its own file, so the gate
consumes that instead.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import ClassVar, override

from flext_infra import m
from flext_infra.validate.tier_whitelist import FlextInfraValidateTierWhitelist

from .base_gate import FlextInfraGate


class FlextInfraTierWhitelistGate(FlextInfraGate):
    """Enforce the tier-whitelist abstraction boundary per project."""

    gate_id: ClassVar[str] = "tier-whitelist"
    gate_name: ClassVar[str] = "Tier Whitelist"
    can_fix: ClassVar[bool] = False

    @override
    def check(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Run the tier-whitelist scan scoped to ``project_dir``."""
        _ = ctx
        started = time.monotonic()
        validator = FlextInfraValidateTierWhitelist(repository_root=project_dir)
        report = validator.build_report(project_dir)
        if report.failure:
            return self._build_project_error_gate_result(
                project_dir,
                passed=False,
                errors=[report.error or "tier-whitelist validation failed"],
                started=started,
            )
        validated = report.unwrap()
        return self._build_project_error_gate_result(
            project_dir,
            passed=validated.passed,
            errors=list(validated.violations),
            started=started,
        )


__all__: list[str] = ["FlextInfraTierWhitelistGate"]
