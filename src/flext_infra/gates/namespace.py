"""Static namespace-rule quality gate (NS-000..003)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import m
from flext_infra.validate.namespace_validator import FlextInfraNamespaceValidator

from .base_gate import FlextInfraGate

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraNamespaceGate(FlextInfraGate):
    """Rope-backed namespace rule gate."""

    gate_id: ClassVar[str] = "namespace"
    gate_name: ClassVar[str] = "Namespace Rules"
    can_fix: ClassVar[bool] = False

    @override
    def check(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Reject execution outside the injected shared Rope cycle."""
        _ = ctx
        return self._build_project_error_gate_result(
            project_dir,
            passed=False,
            errors=["namespace gate requires the shared Rope cycle"],
            started=time.monotonic(),
        )

    def rope_callback_binding(
        self, project_dir: Path, rope: p.Infra.RopeWorkspaceDsl
    ) -> m.Infra.RopeCallbackBinding:
        """Return the namespace callback bound to one project and shared Rope."""
        validator = FlextInfraNamespaceValidator(repository_root=project_dir, rope=rope)
        return validator.callback_binding()

    def check_rope_outcomes(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        outcomes: tuple[m.Infra.RopeCallbackOutcome, ...],
    ) -> m.Infra.GateExecution:
        """Build the namespace gate result from the owner cycle outcomes."""
        _ = ctx
        started = time.monotonic()
        violations = [
            violation
            for outcome in outcomes
            if outcome.callback_id == self.gate_id
            and outcome.project_root.resolve() == project_dir.resolve()
            and outcome.applicable
            for violation in outcome.violations
        ]
        return self._build_project_error_gate_result(
            project_dir, passed=not violations, errors=violations, started=started
        )


__all__: list[str] = ["FlextInfraNamespaceGate"]
