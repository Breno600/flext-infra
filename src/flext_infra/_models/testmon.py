"""Typed pytest-testmon cache state owned by the model namespace.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Self

from flext_cli import m


class FlextInfraModelsTestmon:
    """Models produced by the persistent testmon lifecycle."""

    class TestmonCacheState(m.Value):
        """Decision record after a testmon database integrity pass."""

        seed_needed: Annotated[bool, m.Field(description="No usable DB was present.")]
        restored_accepted: Annotated[
            bool,
            m.Field(description="An existing DB passed integrity checks."),
        ]
        changed: Annotated[
            bool,
            m.Field(description="DB content changed relative to its input digest."),
        ]
        saveable: Annotated[
            bool,
            m.Field(description="DB may be published as a cache generation."),
        ]
        reason: Annotated[
            str,
            m.Field(min_length=1, description="Decisive cache-state reason."),
        ]

    class TestmonCachePublication(m.Value):
        """Fresh checkpoint receipt from one completed runner invocation."""

        database: Annotated[
            Path,
            m.Field(description="Integrity-checked project database"),
        ]
        digest: Annotated[
            str,
            m.Field(pattern=r"^[a-f0-9]{64}$", description="Checkpoint digest"),
        ]
        saveable: Annotated[
            bool,
            m.Field(description="Completed run may publish this generation"),
        ]

    class TestmonRunAccounting(m.Value):
        """Typed proof for an executed suite or an integrity-checked cache hit."""

        executed_count: Annotated[
            int,
            m.Field(ge=0, description="JUnit testcase count."),
        ]
        reported_count: Annotated[
            int,
            m.Field(ge=0, description="Unique node IDs with real TestReport events."),
        ]
        deselected_count: Annotated[
            int,
            m.Field(
                ge=0,
                description="Complete inventory minus the canonical selected node IDs.",
            ),
        ]
        inventory_count: Annotated[
            int | None,
            m.Field(
                ge=0,
                description=(
                    "Complete testmon inventory; absent for coverage; zero only "
                    "when the project owns no test module (owns_no_tests receipt)"
                ),
            ),
        ]
        cache_restored: Annotated[
            bool,
            m.Field(description="Input database passed SQLite integrity checks."),
        ]
        owns_no_tests: Annotated[
            bool,
            m.Field(
                description=(
                    "The project declares no test module under the config-owned "
                    "collection roots: zero execution by declared design"
                ),
            ),
        ] = False

        @m.model_validator(mode="after")
        def require_execution_or_verified_deselection(self) -> Self:
            """Zero execution requires positive accounting against a valid cache.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If deselections cannot exceed the complete collection
                    inventory; or if zero execution requires a restored cache and
                    complete deselection accounting.

            """
            if (
                self.inventory_count is not None
                and self.deselected_count > self.inventory_count
            ):
                msg = "deselections cannot exceed the complete collection inventory"
                raise ValueError(msg)
            if not self.executed_count and not (
                self.owns_no_tests
                or (
                    self.cache_restored
                    and self.inventory_count is not None
                    and self.deselected_count == self.inventory_count
                )
            ):
                msg = (
                    "zero execution requires a restored cache "
                    "and complete deselection accounting"
                )
                raise ValueError(msg)
            return self


__all__: list[str] = ["FlextInfraModelsTestmon"]
