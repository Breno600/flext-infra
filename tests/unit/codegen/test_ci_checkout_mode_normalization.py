"""Verify ci.yml normalizes runner checkout modes before any gate runs.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import config
from tests import u
from tests.unit.codegen.test_ci_integration_branch_triggers import (
    TestsFlextInfraCiIntegrationBranchTriggers,
)


class TestsFlextInfraCiCheckoutModeNormalization:
    """Runner umask 002 checks out 0664; canonical Mise artifacts demand 0o644."""

    @staticmethod
    def test_ci_job_normalizes_checkout_modes_before_gates() -> None:
        """Test ci job normalizes checkout modes before gates."""
        steps = u.CodegenTestSupport.Ci.ci_job_steps(
            TestsFlextInfraCiIntegrationBranchTriggers.render_ci(
                repository_branch="0.12.0-dev",
            ),
        )
        commands: list[str] = []
        for step in steps:
            script = step.get("run")
            if isinstance(script, str):
                commands.extend(line.strip() for line in script.splitlines())
        normalize_at = commands.index("chmod -R go-w .")
        ci = config.Infra.codegen.make.ci
        generation_at = commands.index(f"{ci.variable}={ci.value} make gen")
        tm.that(normalize_at < generation_at, eq=True)
        for step in config.Infra.codegen.make.workflow:
            if "ci" not in step.contexts:
                continue
            gate_at = commands.index(f"{ci.variable}={ci.value} make {step.verb}")
            tm.that(normalize_at < gate_at, eq=True)
