"""Declarative TOML phase models for dependency configuration synchronization.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Annotated, Literal

from flext_cli import m

from flext_infra import c, t


class FlextInfraModelsDepsToml:
    """TOML operation models exposed through ``m.Infra.DepsToml``."""

    """Dependency-management model domains."""

    class DepsToml:
        """Declarative TOML sync model domain."""

        class SetOp(m.ContractModel):
            """Set one TOML key to one JSON-compatible value."""

            kind: Literal[c.Infra.TomlOperationKind.SET] = m.Field(
                c.Infra.TomlOperationKind.SET,
                description="Operation kind",
                validate_default=True,
            )
            key: str = m.Field(description="TOML key name")
            value: t.JsonValue = m.Field(description="JSON-compatible value")

        class ListOp(m.ContractModel):
            """Set or merge one TOML string list."""

            kind: Literal[c.Infra.TomlOperationKind.LIST] = m.Field(
                c.Infra.TomlOperationKind.LIST,
                description="Operation kind",
                validate_default=True,
            )
            key: str = m.Field(description="TOML key name")
            values: t.StrSequence = m.Field(description="Expected values")
            strategy: Annotated[
                c.Infra.TomlMergeMode,
                m.Field(description="Merge strategy", validate_default=True),
            ] = c.Infra.TomlMergeMode.REPLACE
            sort: Annotated[
                bool,
                m.Field(description="Sort values before sync", validate_default=True),
            ] = True

        class RemoveOp(m.ContractModel):
            """Remove one TOML key, optionally from a nested relative table."""

            kind: Literal[c.Infra.TomlOperationKind.REMOVE] = m.Field(
                c.Infra.TomlOperationKind.REMOVE,
                description="Operation kind",
                validate_default=True,
            )
            key: str = m.Field(description="Key to remove")
            table_path: Annotated[
                t.StrSequence,
                m.Field(description="Relative sub-table path", validate_default=True),
            ] = ()

        class PhaseConfig(m.ContractModel):
            """Declarative TOML phase with inline Builder DSL."""

            name: str = m.Field(description="Phase name")
            root_path: Annotated[
                t.StrSequence,
                m.Field(description="Root path before table_path"),
            ] = (c.Infra.TOOL,)
            table_path: Annotated[
                t.StrSequence,
                m.Field(description="Primary table path"),
            ] = ()
            operations: Annotated[
                t.SequenceOf[
                    Annotated[
                        FlextInfraModelsDepsToml.DepsToml.SetOp
                        | FlextInfraModelsDepsToml.DepsToml.ListOp
                        | FlextInfraModelsDepsToml.DepsToml.RemoveOp,
                        m.Field(discriminator="kind"),
                    ]
                ],
                m.Field(description="Declarative TOML operations"),
            ] = ()
            nested_tables: Annotated[
                t.SequenceOf[FlextInfraModelsDepsToml.DepsToml.PhaseConfig],
                m.Field(description="Nested TOML phase configs"),
            ] = ()


__all__: list[str] = ["FlextInfraModelsDepsToml"]
