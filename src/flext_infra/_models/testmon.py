"""Typed pytest-testmon cache state owned by the model namespace."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal

from flext_cli import m, t


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
        """Complete selection and outcome accounting for one runner invocation."""

        mode: Annotated[
            Literal["incremental", "full", "coverage"],
            m.Field(description="Requested test runner execution mode."),
        ]
        cache_hit: Annotated[
            bool,
            m.Field(
                description="An integrity-checked incremental run selected no nodes."
            ),
        ] = False
        inventory: Annotated[
            tuple[str, ...],
            m.Field(description="Complete eligible node IDs reported by collection."),
        ] = ()
        selected: Annotated[
            tuple[str, ...],
            m.Field(description="Collected node IDs selected for this execution."),
        ] = ()
        executed: Annotated[
            tuple[str, ...],
            m.Field(
                description="Node IDs with complete reported execution lifecycles."
            ),
        ] = ()
        deselected: Annotated[
            tuple[str, ...],
            m.Field(description="Eligible node IDs omitted by incremental selection."),
        ] = ()
        database: Annotated[
            str, m.Field(description="Persistent external testmon database path.")
        ]

        executed_count: Annotated[
            int,
            m.Field(
                ge=0, description="Unique nodes with complete reported lifecycles."
            ),
        ]
        deselected_count: Annotated[
            int,
            m.Field(
                ge=0,
                description="Deselections reported by pytest or proven by complete collection inventory.",
            ),
        ]
        cache_restored: Annotated[
            bool, m.Field(description="Input database passed SQLite integrity checks.")
        ]

    class PytestReportEvent(m.Value):
        """Native reportlog event fields needed for execution accounting."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore", frozen=True)
        report_type: str = m.Field(
            alias="$report_type", description="Native pytest reportlog event type."
        )
        nodeid: Annotated[
            str, m.Field(description="Pytest node ID associated with the event.")
        ] = ""
        when: Annotated[
            str | None,
            m.Field(description="Execution phase reported by pytest, when applicable."),
        ] = None
        outcome: Annotated[
            Literal["passed", "failed", "skipped"] | None,
            m.Field(description="Native collection or execution outcome."),
        ] = None
        category: Annotated[
            str | None, m.Field(description="Native warning category name, if present.")
        ] = None
        message: Annotated[
            str, m.Field(description="Original warning message emitted by pytest.")
        ] = ""
        filename: Annotated[
            str, m.Field(description="Source filename associated with a warning event.")
        ] = ""
        lineno: Annotated[
            int, m.Field(description="Source line reported for a warning event.")
        ] = 0
        longrepr: Annotated[
            t.JsonValue,
            m.Field(
                description="Original serialized failure or collection skip detail."
            ),
        ] = None


__all__: list[str] = ["FlextInfraModelsTestmon"]
