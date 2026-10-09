"""Behavioral tests for the tagged per-project pytest worker ceiling.

Every expected value is derived from the typed SSOT (the PytestWorkerCeiling
model and the live process CPU count) — no hardcoded worker counts.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraPytestRunner, config, m
from tests.unit.validate.pytest_runner_support import runner_for


@pytest.mark.unit
class TestsFlextInfraPytestWorkerCeiling:
    """Public contract of the tagged worker ceiling and its resolution."""

    @staticmethod
    def test_legacy_integer_coerces_to_absolute_workers() -> None:
        """The legacy bare-integer YAML form still reads as workers."""
        ceiling = m.Infra.PytestWorkerCeiling.model_validate(4)
        tm.that(ceiling.workers, eq=4)
        tm.that(ceiling.cpu_fraction, eq=None)

    @staticmethod
    def test_exactly_one_form_is_required() -> None:
        """Both or neither form set is rejected."""
        with pytest.raises(ValueError, match="exactly one"):
            m.Infra.PytestWorkerCeiling.model_validate({})
        with pytest.raises(ValueError, match="exactly one"):
            m.Infra.PytestWorkerCeiling.model_validate({
                "workers": 4,
                "cpu_fraction": "1/4",
            })

    @staticmethod
    def test_cpu_fraction_shape_is_validated() -> None:
        """Non-fraction strings are rejected at validation."""
        with pytest.raises(ValueError, match="cpu_fraction"):
            m.Infra.PytestWorkerCeiling.model_validate({"cpu_fraction": "quarter"})

    @staticmethod
    def test_fraction_resolves_from_the_process_cpu_count() -> None:
        """A 1/4 ceiling resolves to max(1, cpus//4) of the process count."""
        ceiling = m.Infra.PytestWorkerCeiling.model_validate({"cpu_fraction": "1/4"})
        cpus = os.process_cpu_count()
        expected = max(1, cpus // 4)
        resolved = FlextInfraPytestRunner.resolve_worker_ceiling(ceiling, cpus)
        tm.that(resolved, eq=expected)
        tm.that(resolved, eq=max(1, resolved))

    @staticmethod
    def test_fraction_never_yields_zero_on_a_single_cpu_host() -> None:
        """A fraction of one CPU still resolves to one worker."""
        ceiling = m.Infra.PytestWorkerCeiling.model_validate({"cpu_fraction": "1/4"})
        resolved = FlextInfraPytestRunner.resolve_worker_ceiling(ceiling, 1)
        tm.that(resolved, eq=1)

    @staticmethod
    def test_absolute_workers_pass_through() -> None:
        """An absolute ceiling resolves to itself regardless of CPU count."""
        ceiling = m.Infra.PytestWorkerCeiling.model_validate({"workers": 3})
        resolved = FlextInfraPytestRunner.resolve_worker_ceiling(
            ceiling,
            os.process_cpu_count(),
        )
        tm.that(resolved, eq=3)

    @staticmethod
    def test_default_arrives_as_a_bare_int_and_passes_through() -> None:
        """The fleet-wide default (int) resolves unchanged."""
        resolved = FlextInfraPytestRunner.resolve_worker_ceiling(
            2,
            os.process_cpu_count(),
        )
        tm.that(resolved, eq=2)

    @staticmethod
    def test_declared_overrides_come_from_the_typed_ssot() -> None:
        """The tooling SSOT carries validated ceilings of either form."""
        from flext_infra import config

        overrides = config.Infra.tooling.tools.pytest.parallel_worker_overrides
        tm.that(len(overrides) > 0, eq=True)
        for declared in overrides.values():
            tm.that(
                (declared.workers is None) != (declared.cpu_fraction is None),
                eq=True,
            )

    @staticmethod
    def test_worker_ceiling_defaults_without_declared_project(
        cached_runner_project: Path,
    ) -> None:
        """A tree without ``[project].name`` takes the fleet-wide ceiling."""
        policy = config.Infra.tooling.tools.pytest
        runner = runner_for(cached_runner_project)
        assert runner.parallel_worker_budget(policy) == policy.parallel_workers

    @staticmethod
    def test_worker_ceiling_follows_the_declared_project_override(
        cached_runner_project: Path,
    ) -> None:
        """The runner resolves the declared project's override from the SSOT."""
        policy = config.Infra.tooling.tools.pytest
        assert policy.parallel_worker_overrides
        declared_name = next(iter(policy.parallel_worker_overrides))
        pyproject = cached_runner_project / "pyproject.toml"
        pyproject.write_text(
            pyproject.read_text(encoding="utf-8")
            + f'\n[project]\nname = "{declared_name}"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        runner = runner_for(cached_runner_project)
        report = (
            cached_runner_project
            / config.Infra.codegen.make.testmon_cache.reports_directory
        )
        declared_ceiling = policy.parallel_worker_overrides[declared_name]
        expected_workers = runner.resolve_worker_ceiling(
            declared_ceiling,
            os.process_cpu_count(),
        )
        budget = runner.parallel_worker_budget(policy)
        assert budget == expected_workers
        command = runner.build_command(report)
        workers = command[command.index("-n") + 1]
        assert workers == str(budget)
