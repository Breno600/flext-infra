"""Authorized gate suspensions preserve the active Make check contract."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, m, t, u


class TestsFlextInfraCodegenMakeGateSuspensions:
    """One typed gate universe drives local, CI, and hook execution."""

    @pytest.mark.parametrize("local_count", [0, 1, 3])
    def test_project_gates_and_suspensions_share_the_ci_partition(
        self, local_count: int
    ) -> None:
        payload = config.Infra.codegen.make.model_dump(exclude_computed_fields=True)
        payload["project_check_gates"] = ("fixture-active", "fixture-suspended")
        payload["check_gate_suspensions"] = ()
        declared = m.Infra.MakeSpec.model_validate(payload)
        builtin_defaults = tuple(
            gate
            for gate in declared.check_gates_default
            if gate not in declared.project_check_gates
        )
        local_gates = builtin_defaults[:local_count]
        payload["ci"] = {**declared.ci.model_dump(), "local_check_gates": local_gates}
        suspended_gates = (*builtin_defaults[:1], "fixture-suspended")
        payload["check_gate_suspensions"] = tuple(
            {
                "gate": gate,
                "authority": "fixture recovery decision",
                "reason": "fixture policy suspension",
            }
            for gate in suspended_gates
        )

        active = m.Infra.MakeSpec.model_validate(payload)

        tm.that(active.check_gates_allowed, eq=declared.check_gates_allowed)
        tm.that(
            active.check_gates_default,
            eq=tuple(
                gate
                for gate in declared.check_gates_default
                if gate not in suspended_gates
            ),
        )
        tm.that(active.check_gates_ci, has="fixture-active")
        tm.that(
            active.check_gates_local,
            eq=tuple(
                gate for gate in active.check_gates_default if gate in local_gates
            ),
        )
        tm.that(
            active.check_gates_ci,
            eq=tuple(
                gate
                for gate in active.check_gates_default
                if gate not in active.ci.local_check_gates
            ),
        )
        tm.that(set(active.check_gates_local) & set(active.check_gates_ci), eq=set())
        tm.that(
            set(active.check_gates_local) | set(active.check_gates_ci),
            eq=set(active.check_gates_default),
        )

    @pytest.mark.parametrize("invalid", ["unknown", "duplicate", "missing", "blank"])
    def test_suspensions_require_a_known_unique_gate_and_authority(
        self, invalid: str
    ) -> None:
        payload = config.Infra.codegen.make.model_dump(exclude_computed_fields=True)
        row = {
            "gate": config.Infra.codegen.make.check_gates_allowed[0],
            "authority": "fixture authorization",
            "reason": "fixture decision",
        }
        if invalid == "unknown":
            row["gate"] = "undeclared-fixture-gate"
        elif invalid == "missing":
            del row["authority"]
        elif invalid == "blank":
            row["reason"] = " \n"
        payload["check_gate_suspensions"] = (
            [row, row] if invalid == "duplicate" else [row]
        )

        with pytest.raises(m.ValidationError):
            m.Infra.MakeSpec.model_validate(payload)

    @pytest.mark.slow
    @pytest.mark.parametrize("context", ["ci", "local", "all"])
    def test_make_reports_suspensions_without_hiding_a_runtime_failure(
        self, tmp_path: Path, context: str
    ) -> None:
        """A real missing runtime remains fatal after the authorized receipts."""
        root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
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
            )
        )

        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(
            process.stdout, has=f"INFO: {label} runs check gates: {' '.join(gates)}\n"
        )
        tm.that(
            process.stderr,
            has=(
                "No module named flext_infra"
                if gates
                else "no active check gates remain in the selected context"
            ),
        )
        for suspension in policy.check_gate_suspensions:
            tm.that(
                process.stdout,
                has=(
                    f"INFO: SUSPENDED check gate {suspension.gate}; "
                    f"authority={suspension.authority}; reason={suspension.reason}"
                ),
            )
