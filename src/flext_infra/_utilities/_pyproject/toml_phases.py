"""Declarative TOML phase application over one normalized pyproject payload."""

from __future__ import annotations

from flext_cli import u

from flext_infra import c, m, t


class FlextInfraUtilitiesPyprojectTomlPhases:
    """Apply ``m.Infra.DepsToml.PhaseConfig`` phases to plain TOML payloads."""

    @classmethod
    def apply_toml_phases(
        cls, payload: t.MutableJsonMapping, *phases: m.Infra.DepsToml.PhaseConfig
    ) -> t.StrSequence:
        """Apply declarative phases in order and return one flat change list."""
        return [
            change
            for phase in phases
            for change in cls._apply_toml_phase(payload, phase, parent_path=())
        ]

    @classmethod
    def _apply_toml_phase(
        cls,
        payload: t.MutableJsonMapping,
        phase: m.Infra.DepsToml.PhaseConfig,
        *,
        parent_path: t.StrSequence,
    ) -> t.StrSequence:
        """Apply one phase and its nested tables below ``parent_path``."""
        phase_path = (*parent_path, *phase.root_path, *phase.table_path)
        table = u.Cli.toml_mapping_ensure_path(payload, phase_path)
        prefix = u.Cli.toml_dot_path(*phase_path)
        changes = [
            f"{u.Cli.toml_dot_path(prefix, *path)} {outcome}"
            for operation in phase.operations
            for path, outcome in cls._apply_toml_operation(table, operation)
        ]
        for nested in phase.nested_tables:
            changes.extend(
                cls._apply_toml_phase(payload, nested, parent_path=phase_path)
            )
        return changes

    @staticmethod
    def _apply_toml_operation(
        table: t.MutableJsonMapping,
        operation: m.Infra.DepsToml.SetOp
        | m.Infra.DepsToml.ListOp
        | m.Infra.DepsToml.RemoveOp,
    ) -> t.SequenceOf[t.Pair[t.StrSequence, str]]:
        """Apply one operation; return its ``(relative key path, outcome)`` change."""
        if isinstance(operation, m.Infra.DepsToml.SetOp):
            changed = u.Cli.toml_mapping_sync_value(
                table, operation.key, operation.value
            )
            return (((operation.key,), f"set to {operation.value}"),) if changed else ()
        if isinstance(operation, m.Infra.DepsToml.ListOp):
            if operation.strategy == c.Infra.TomlMergeMode.REPLACE:
                changed = u.Cli.toml_mapping_sync_string_list(
                    table, operation.key, operation.values, sort_values=operation.sort
                )
                return (((operation.key,), "set"),) if changed else ()
            changed = u.Cli.toml_mapping_merge_string_list(
                table, operation.key, operation.values
            )
            return (((operation.key,), "updated"),) if changed else ()
        target = (
            u.Cli.toml_mapping_path(table, operation.table_path)
            if operation.table_path
            else table
        )
        removed = target is not None and u.Cli.toml_mapping_remove_key_if_present(
            target, operation.key
        )
        return (((*operation.table_path, operation.key), "removed"),) if removed else ()


__all__: list[str] = ["FlextInfraUtilitiesPyprojectTomlPhases"]
