"""Public facade for the canonical persistent-testmon pytest runner."""

from __future__ import annotations

from flext_infra import t

from ._pytest_runner.execution import FlextInfraPytestRunnerExecution


class FlextInfraPytestRunner(FlextInfraPytestRunnerExecution):
    """Expose whole-suite cached execution through the public package boundary."""


__all__: t.VariadicTuple[str] = ("FlextInfraPytestRunner",)
