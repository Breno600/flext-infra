"""Typed, config-derived pytest execution policy contracts.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c


class TestsFlextInfraPytestTimeoutConfig:
    """Prove the operator caps and relational policy at the typed SSOT."""

    @staticmethod
    def test_policy_round_trips_through_its_production_model() -> None:
        """Test policy round trips through its production model."""
        policy = config.Infra.tooling.tools.pytest

        round_tripped = type(policy).model_validate(
            policy.model_dump(by_alias=True, exclude_computed_fields=True),
        )

        tm.that(round_tripped, eq=policy)

    @staticmethod
    @pytest.mark.parametrize(
        (
            "case_timeout_seconds",
            "run_timeout_seconds",
            "termination_grace_seconds",
            "parallel_workers",
        ),
        [(1, 6, 1, 1), (7, 20, 2, 8)],
    )
    def test_arbitrary_valid_execution_policy_round_trips(
        case_timeout_seconds: int,
        run_timeout_seconds: int,
        termination_grace_seconds: int,
        parallel_workers: int,
    ) -> None:
        """Test arbitrary valid execution policy round trips."""
        policy = config.Infra.tooling.tools.pytest
        payload = policy.model_dump(by_alias=True, exclude_computed_fields=True)
        slow_timeout_seconds = case_timeout_seconds + 1
        run_timeout_seconds = max(
            run_timeout_seconds,
            max(2, policy.parallel_schedule_chunk) * slow_timeout_seconds
            + termination_grace_seconds
            + 1,
        )
        payload.update({
            "case-timeout-seconds": case_timeout_seconds,
            "run-timeout-seconds": run_timeout_seconds,
            "slow-timeout-seconds": slow_timeout_seconds,
            "termination-grace-seconds": termination_grace_seconds,
            "parallel-workers": parallel_workers,
        })

        arbitrary_policy = type(policy).model_validate(payload)
        round_tripped = type(policy).model_validate(
            arbitrary_policy.model_dump(by_alias=True, exclude_computed_fields=True),
        )

        tm.that(round_tripped, eq=arbitrary_policy)

    @staticmethod
    @pytest.mark.parametrize(
        "field",
        ["case-timeout-seconds", "run-timeout-seconds", "termination-grace-seconds"],
    )
    def test_operator_caps_are_hard_typed_boundaries(field: str) -> None:
        """Test operator caps are hard typed boundaries."""
        policy = config.Infra.tooling.tools.pytest
        payload = policy.model_dump(by_alias=True, exclude_computed_fields=True)
        payload[field] = 0

        with pytest.raises(c.ValidationError, match="greater than"):
            type(policy).model_validate(payload)

    @staticmethod
    @pytest.mark.parametrize(
        "override",
        ["-o", "-o=addopts=", "--override-ini", "--override-ini=addopts="],
    )
    def test_pytest_ini_override_is_forbidden(override: str) -> None:
        """Test pytest ini override is forbidden."""
        policy = config.Infra.tooling.tools.pytest
        payload = policy.model_dump(by_alias=True, exclude_computed_fields=True)
        payload["standard-addopts"] = [override]

        with pytest.raises(
            c.ValidationError,
            match="pytest runtime policy options are derived from typed fields",
        ):
            type(policy).model_validate(payload)

    @staticmethod
    def test_run_budget_exceeds_the_derived_suite_stop_reserve() -> None:
        """A run budget at the reserve (item windows + grace) is unrepresentable.

        The slow budget stays inside its own case/run walls, so only the
        reserve relation is violated.
        """
        policy = config.Infra.tooling.tools.pytest
        payload = policy.model_dump(by_alias=True, exclude_computed_fields=True)
        payload["run-timeout-seconds"] = policy.suite_stop_reserve_seconds
        payload["slow-timeout-seconds"] = policy.case_timeout_seconds + 1

        with pytest.raises(
            c.ValidationError,
            match="pytest run timeout must exceed the suite stop reserve",
        ):
            type(policy).model_validate(payload)

    @staticmethod
    def test_slow_budget_is_declared_and_bounded_by_the_case_and_run_walls() -> None:
        """An explicitly slow item gets a longer arm than the per-case default."""
        policy = config.Infra.tooling.tools.pytest

        tm.that(policy.slow_timeout_seconds > policy.case_timeout_seconds, eq=True)
        tm.that(policy.slow_timeout_seconds < policy.run_timeout_seconds, eq=True)

    @staticmethod
    @pytest.mark.parametrize(
        "expected",
        [
            "pytest slow timeout must exceed the per-case timeout",
            "pytest slow timeout must be less than run timeout",
        ],
    )
    def test_slow_budget_is_a_hard_typed_boundary(expected: str) -> None:
        """A slow budget outside the case/run walls is unrepresentable."""
        policy = config.Infra.tooling.tools.pytest
        payload = policy.model_dump(by_alias=True, exclude_computed_fields=True)
        if "exceed the per-case" in expected:
            payload["slow-timeout-seconds"] = policy.case_timeout_seconds
        else:
            payload["slow-timeout-seconds"] = policy.run_timeout_seconds

        with pytest.raises(c.ValidationError, match=expected):
            type(policy).model_validate(payload)

    @staticmethod
    def test_process_budget_is_derived_from_run_and_termination_windows() -> None:
        """Test process budget is derived from run and termination windows."""
        policy = config.Infra.tooling.tools.pytest
        expected = policy.run_timeout_seconds + (policy.termination_grace_seconds * 2)

        tm.that(policy.process_timeout_seconds, eq=expected)
        tm.that("process-timeout-seconds" in policy.model_dump(by_alias=True), eq=False)

    @staticmethod
    def test_project_run_budget_exceeds_the_derived_suite_stop_reserve() -> None:
        """Test project run budget exceeds the derived suite stop reserve."""
        policy = config.Infra.tooling.tools.pytest
        payload = policy.model_dump(by_alias=True, exclude_computed_fields=True)
        payload["run-timeout-overrides"] = {
            config.Infra.name: policy.suite_stop_reserve_seconds,
        }

        with pytest.raises(
            c.ValidationError,
            match="pytest run timeout must exceed the suite stop reserve",
        ):
            type(policy).model_validate(payload)

    @staticmethod
    def test_progress_policy_cannot_hide_item_names() -> None:
        """Test progress policy cannot hide item names."""
        policy = config.Infra.tooling.tools.pytest
        payload = policy.model_dump(by_alias=True, exclude_computed_fields=True)
        payload["progress-args"] = ["-q"]

        with pytest.raises(
            c.ValidationError,
            match="pytest progress args must expose verbose item progress",
        ):
            type(policy).model_validate(payload)

    @staticmethod
    @pytest.mark.parametrize(
        "argument",
        [
            "tests",
            "-o",
            "--override-ini=addopts=",
            "--timeout=999",
            "-n=auto",
            "--dist=load",
            f"-p=no:{config.Infra.tooling.tools.pytest.enforcement_plugin}",
            "--junitxml=elsewhere.xml",
            "--cov=unowned",
            "--tb=short\n-o=addopts=",
        ],
    )
    def test_reporting_policy_cannot_override_runner_owned_argv(
        argument: str,
    ) -> None:
        """Test reporting policy cannot override runner owned argv."""
        policy = config.Infra.tooling.tools.pytest
        payload = policy.model_dump(by_alias=True, exclude_computed_fields=True)
        payload["report-args"] = [argument]

        with pytest.raises(
            c.ValidationError,
            match="pytest reporting args must not override runner-owned policy",
        ):
            type(policy).model_validate(payload)
