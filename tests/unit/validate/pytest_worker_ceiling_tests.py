"""Behavioral tests for the tagged per-project pytest worker ceiling.

Every expected value is derived from the typed SSOT (the PytestWorkerCeiling
model and the live process CPU count) — no hardcoded worker counts.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

import os

import pytest
from flext_tests import tm

from flext_infra import FlextInfraPytestRunner, m


@pytest.mark.unit
class TestsFlextInfraPytestWorkerCeiling:
    """Public contract of the tagged worker ceiling and its resolution."""

    def test_legacy_integer_coerces_to_absolute_workers(self) -> None:
        """The legacy bare-integer YAML form still reads as workers."""
        ceiling = m.Infra.PytestWorkerCeiling.model_validate(4)
        tm.that(ceiling.workers, eq=4)
        tm.that(ceiling.cpu_fraction, eq=None)

    def test_exactly_one_form_is_required(self) -> None:
        """Both or neither form set is rejected."""
        with pytest.raises(ValueError, match="exactly one"):
            m.Infra.PytestWorkerCeiling.model_validate({})
        with pytest.raises(ValueError, match="exactly one"):
            m.Infra.PytestWorkerCeiling.model_validate({
                "workers": 4,
                "cpu_fraction": "1/4",
            })

    def test_cpu_fraction_shape_is_validated(self) -> None:
        """Non-fraction strings are rejected at validation."""
        with pytest.raises(ValueError, match="cpu_fraction"):
            m.Infra.PytestWorkerCeiling.model_validate({"cpu_fraction": "quarter"})

    def test_fraction_resolves_from_the_process_cpu_count(self) -> None:
        """A 1/4 ceiling resolves to max(1, cpus//4) of the process count."""
        ceiling = m.Infra.PytestWorkerCeiling.model_validate({"cpu_fraction": "1/4"})
        cpus = os.process_cpu_count()
        expected = max(1, cpus // 4)
        resolved = FlextInfraPytestRunner.resolve_worker_ceiling(ceiling, cpus)
        tm.that(resolved, eq=expected)
        tm.that(resolved, eq=max(1, resolved))

    def test_fraction_never_yields_zero_on_a_single_cpu_host(self) -> None:
        """A fraction of one CPU still resolves to one worker."""
        ceiling = m.Infra.PytestWorkerCeiling.model_validate({"cpu_fraction": "1/4"})
        resolved = FlextInfraPytestRunner.resolve_worker_ceiling(ceiling, 1)
        tm.that(resolved, eq=1)

    def test_absolute_workers_pass_through(self) -> None:
        """An absolute ceiling resolves to itself regardless of CPU count."""
        ceiling = m.Infra.PytestWorkerCeiling.model_validate({"workers": 3})
        resolved = FlextInfraPytestRunner.resolve_worker_ceiling(
            ceiling, os.process_cpu_count()
        )
        tm.that(resolved, eq=3)

    def test_default_arrives_as_a_bare_int_and_passes_through(self) -> None:
        """The fleet-wide default (int) resolves unchanged."""
        resolved = FlextInfraPytestRunner.resolve_worker_ceiling(
            2, os.process_cpu_count()
        )
        tm.that(resolved, eq=2)

    def test_declared_overrides_come_from_the_typed_ssot(self) -> None:
        """The tooling SSOT carries validated ceilings of either form."""
        from flext_infra import config

        overrides = config.Infra.tooling.tools.pytest.parallel_worker_overrides
        tm.that(len(overrides) > 0, eq=True)
        for declared in overrides.values():
            tm.that(
                (declared.workers is None) != (declared.cpu_fraction is None), eq=True
            )
