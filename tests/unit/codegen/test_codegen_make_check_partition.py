"""The Make check partition derives from the gate kind in the registry."""

from __future__ import annotations

from flext_tests import tm

from flext_infra import config
from tests import c, m

from ._support import CodegenTestSupport
from .test_ci_integration_branch_triggers import (
    TestsFlextInfraCiIntegrationBranchTriggers,
)


class TestsFlextInfraCodegenMakeCheckPartition:
    """CI and pre-commit run only external gates; the rest block locally."""

    def test_registry_declares_one_kind_per_gate(self) -> None:
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

    def test_fast_partition_holds_only_active_external_gates(self) -> None:
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

    def test_project_declared_gates_never_join_the_fast_partition(self) -> None:
        """A gate the registry does not classify as external stays local."""
        payload = config.Infra.codegen.make.model_dump(exclude_computed_fields=True)
        payload["project_check_gates"] = ("fixture-project-gate",)

        active = m.Infra.MakeSpec.model_validate(payload)

        tm.that(active.check_gates_default, has="fixture-project-gate")
        tm.that(active.check_gates_local, has="fixture-project-gate")
        tm.that("fixture-project-gate" in active.check_gates_ci, eq=False)

    def test_ci_workflow_runs_only_the_fast_partition(self) -> None:
        """The rendered CI job never runs the local check partition."""
        make = config.Infra.codegen.make
        steps = CodegenTestSupport.Ci.ci_job_steps(
            TestsFlextInfraCiIntegrationBranchTriggers.render_ci(
                repository_branch="0.12.0-dev"
            )
        )
        commands = [str(step.get("run", "")) for step in steps]
        fast = f"{make.ci.variable}={make.ci.value} make {c.Infra.VERB_CHECK}"
        local = f"{make.ci.variable}={make.ci.local_value} make {c.Infra.VERB_CHECK}"
        tm.that(sum(fast in command for command in commands), eq=1)
        tm.that(any(local in command for command in commands), eq=False)
