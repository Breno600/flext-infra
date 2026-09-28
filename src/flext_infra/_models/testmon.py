"""Typed pytest-testmon cache state owned by the model namespace."""

from __future__ import annotations

from typing import Annotated, Self

from flext_cli import m, u


class FlextInfraModelsTestmon:
    """Models produced by the persistent testmon lifecycle."""

    class TestmonCacheState(m.Value):
        """Decision record after a testmon database integrity pass."""

        seed_needed: Annotated[bool, m.Field(description="No usable DB was present.")]
        restored_accepted: Annotated[
            bool, m.Field(description="An existing DB passed integrity checks.")
        ]
        changed: Annotated[
            bool,
            m.Field(description="DB content changed relative to its input digest."),
        ]
        saveable: Annotated[
            bool, m.Field(description="DB may be published as a cache generation.")
        ]
        reason: Annotated[
            str, m.Field(min_length=1, description="Decisive cache-state reason.")
        ]

    class TestmonRunAccounting(m.Value):
        """Typed proof for an executed suite or an integrity-checked cache hit."""

        executed_count: Annotated[
            int, m.Field(ge=0, description="JUnit testcase count.")
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
                ge=1, description="Complete testmon inventory; absent for coverage."
            ),
        ]
        cache_restored: Annotated[
            bool, m.Field(description="Input database passed SQLite integrity checks.")
        ]

        @u.model_validator(mode="after")
        def require_execution_or_verified_deselection(self) -> Self:
            """Zero execution requires positive accounting against a valid cache."""
            if (
                self.inventory_count is not None
                and self.deselected_count > self.inventory_count
            ):
                msg = "deselections cannot exceed the complete collection inventory"
                raise ValueError(msg)
            if not self.executed_count and not (
                self.cache_restored
                and self.inventory_count is not None
                and self.deselected_count == self.inventory_count
            ):
                msg = "zero execution requires a restored cache and complete deselection accounting"
                raise ValueError(msg)
            return self


__all__: list[str] = ["FlextInfraModelsTestmon"]
