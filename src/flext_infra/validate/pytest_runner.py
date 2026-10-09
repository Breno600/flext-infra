"""Public facade for the canonical persistent-testmon pytest runner.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra.validate._pytest_runner.execution import (
    FlextInfraPytestRunnerExecution,
)

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraPytestRunner(FlextInfraPytestRunnerExecution):
    """Expose whole-suite cached execution through the public package boundary."""


__all__: t.VariadicTuple[str] = ("FlextInfraPytestRunner",)
