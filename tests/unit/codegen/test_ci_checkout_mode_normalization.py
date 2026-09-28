"""Verify ci.yml normalizes runner checkout modes before any gate runs."""

from __future__ import annotations

from flext_cli import t, u
from flext_tests import tm

from flext_infra import config

from .test_ci_integration_branch_triggers import (
    TestsFlextInfraCiIntegrationBranchTriggers,
)


class TestsFlextInfraCiCheckoutModeNormalization:
    """Runner umask 002 checks out 0664; canonical Mise artifacts demand 0o644."""

    def test_ci_job_normalizes_checkout_modes_before_gates(self) -> None:
        rendered = TestsFlextInfraCiIntegrationBranchTriggers.render_ci(
            repository_branch="0.12.0-dev"
        )
        document = t.Cli.JSON_MAPPING_ADAPTER.validate_python(
            tm.ok(u.Cli.yaml_parse(rendered))
        )
        jobs = t.Cli.JSON_MAPPING_ADAPTER.validate_python(document["jobs"])
        job = t.Cli.JSON_MAPPING_ADAPTER.validate_python(jobs["ci"])
        steps = job["steps"]
        if not isinstance(steps, list):
            msg = "workflow job steps must be a sequence"
            raise TypeError(msg)
        commands: list[str] = []
        for raw_step in steps:
            step = t.Cli.JSON_MAPPING_ADAPTER.validate_python(raw_step)
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
