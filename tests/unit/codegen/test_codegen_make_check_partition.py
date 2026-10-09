"""The Make check partition derives from the gate kind in the registry.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, m, t, u
from tests.unit.codegen.test_ci_integration_branch_triggers import (
    TestsFlextInfraCiIntegrationBranchTriggers,
)


class TestsFlextInfraCodegenMakeCheckPartition:
    """CI and pre-commit run only external gates; the rest block locally."""

    @staticmethod
    def test_registry_declares_one_kind_per_gate() -> None:
        """Every gate vocabulary is derived from the single kind declaration."""
        declared = [
            gate for tools in c.Infra.GATE_TOOLS_BY_KIND.values() for gate in tools
        ]
        tm.that(len(declared), eq=len(set(declared)))
        tm.that(set(c.Infra.GATE_KINDS), eq=set(c.Infra.SARIF_TOOL_INFO))
        tm.that(set(c.Infra.GATE_KINDS), eq=set(c.Infra.ALLOWED_GATES))
        tm.that(
            c.Infra.TYPE_CHECKER_GATES,
            eq=frozenset(
                gate
                for gate, kind in c.Infra.GATE_KINDS.items()
                if kind is c.Infra.GateKind.TYPE_CHECKER
            ),
        )

    @staticmethod
    def test_fast_partition_holds_only_active_external_gates() -> None:
        """CI=Y is exactly the active external gates; CI=N is the complement."""
        make = config.Infra.codegen.make
        external = c.Infra.GateKind.EXTERNAL
        tm.that(
            make.check_gates_ci,
            eq=tuple(
                gate
                for gate in make.check_gates_default
                if c.Infra.GATE_KINDS.get(gate) is external
            ),
        )
        tm.that(set(make.check_gates_ci) & set(make.check_gates_local), eq=set())
        tm.that(
            set(make.check_gates_ci) | set(make.check_gates_local),
            eq=set(make.check_gates_default),
        )
        for gate in make.check_gates_local:
            tm.that(c.Infra.GATE_KINDS.get(gate) is external, eq=False)

    @staticmethod
    def test_project_declared_gates_never_join_the_fast_partition() -> None:
        """A gate the registry does not classify as external stays local."""
        payload = config.Infra.codegen.make.model_dump(exclude_computed_fields=True)
        payload["project_check_gates"] = ("fixture-project-gate",)

        active = m.Infra.MakeSpec.model_validate(payload)

        tm.that(active.check_gates_default, has="fixture-project-gate")
        tm.that(active.check_gates_local, has="fixture-project-gate")
        tm.that("fixture-project-gate" in active.check_gates_ci, eq=False)

    @staticmethod
    def test_ci_workflow_runs_only_the_fast_partition() -> None:
        """The rendered CI job never runs the local check partition."""
        make = config.Infra.codegen.make
        steps = u.CodegenTestSupport.Ci.ci_job_steps(
            TestsFlextInfraCiIntegrationBranchTriggers.render_ci(
                repository_branch="0.12.0-dev",
            ),
        )
        commands = [str(step.get("run", "")) for step in steps]
        fast = f"{make.ci.variable}={make.ci.value} make {c.Infra.VERB_CHECK}"
        local = f"{make.ci.variable}={make.ci.local_value} make {c.Infra.VERB_CHECK}"
        tm.that(sum(fast in command for command in commands), eq=1)
        tm.that(any(local in command for command in commands), eq=False)

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize("context", ["ci", "local", "all"])
    def test_make_check_keeps_a_missing_runtime_fatal(
        tmp_path: Path,
        context: str,
    ) -> None:
        """A real missing runtime stays fatal in every check context."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        tm.ok(u.Tests.create_python_environment(root))
        policy = config.Infra.codegen.make
        environment: t.StrMapping
        if context == "ci":
            environment = {policy.ci.variable: policy.ci.value}
            gates = policy.check_gates_ci
            label = f"{policy.ci.variable}={policy.ci.value}"
        elif context == "local":
            environment = {policy.ci.variable: policy.ci.local_value}
            gates = policy.check_gates_local
            label = f"{policy.ci.variable}={policy.ci.local_value}"
        else:
            environment = {}
            gates = policy.check_gates_default
            label = "default context"
        process = tm.ok(
            u.Cli.run_raw(
                [c.Infra.MAKE, "--no-print-directory", "check"],
                cwd=root,
                env=environment,
                remove_env_keys=(
                    *c.Tests.MAKE_ISOLATION_ENV_KEYS,
                    *((policy.ci.variable,) if context == "all" else ()),
                ),
            ),
        )

        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(
            process.stdout,
            has=f"INFO: {label} runs check gates: {' '.join(gates)}\n",
        )
        tm.that(
            process.stderr,
            has=(
                "No module named flext_infra"
                if gates
                else "no active check gates remain in the selected context"
            ),
        )
