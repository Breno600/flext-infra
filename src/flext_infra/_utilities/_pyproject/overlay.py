"""Preserve live CUSTOM project keys and unmanaged tool tables over renders.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import r, u

from flext_infra import c, p, t
from flext_infra._utilities import (
    FlextInfraUtilitiesDependencies,
    FlextInfraUtilitiesManagedConflicts,
    FlextInfraUtilitiesPyprojectRequirements,
)


class FlextInfraUtilitiesPyprojectOverlay:
    """Merge one rendered pyproject with its live CUSTOM surface."""

    @staticmethod
    def _validated_requirement_lists(
        project: t.MutableJsonMapping,
        live_project: t.JsonMapping,
        key: str,
    ) -> p.Result[t.Pair[t.StrSequence, t.StrSequence]]:
        """Validate generated and CUSTOM runtime dependency lists once.

        Returns:
            The resulting ``(required, custom)`` requirement lists.

        """
        validated_required: p.Result[t.StrSequence] = u.validate_value(
            t.Infra.STR_SEQ_ADAPTER,
            project.get(key, []),
            strict=True,
        )
        if validated_required.failure:
            return r[t.Pair[t.StrSequence, t.StrSequence]].fail_op(
                "validate runtime dependencies",
                validated_required.error,
            )
        validated_custom: p.Result[t.StrSequence] = u.validate_value(
            t.Infra.STR_SEQ_ADAPTER,
            live_project[key],
            strict=True,
        )
        if validated_custom.failure:
            return r[t.Pair[t.StrSequence, t.StrSequence]].fail_op(
                "validate runtime dependencies",
                validated_custom.error,
            )
        return r[t.Pair[t.StrSequence, t.StrSequence]].ok(
            (validated_required.value, validated_custom.value),
        )

    @staticmethod
    def _merged_requirements(
        required: t.StrSequence,
        custom: t.StrSequence,
    ) -> list[t.JsonValue]:
        """Merge CUSTOM runtime requirements under the generated ownership order.

        Profiles own same-name requirements. CUSTOM requirements retain full
        specs, including distinct markers for one name. Conformance uses this
        same order: overlay must not move generated requirements ahead of
        preserved custom ones.

        Returns:
            The resulting ``list[t.JsonValue]``.

        """
        owned_names = {
            FlextInfraUtilitiesDependencies.dep_name(item) for item in required
        }
        # The list display widens the sorted ``str`` items to the JSON value
        # list the caller stores, in the single pass that materializes them.
        return [
            *sorted(
                dict.fromkeys((
                    *required,
                    *(
                        item
                        for item in custom
                        if FlextInfraUtilitiesDependencies.dep_name(item)
                        not in owned_names
                    ),
                )),
                key=FlextInfraUtilitiesPyprojectRequirements.dependency_order_key,
            ),
        ]

    @classmethod
    def _overlay_project_surface(
        cls,
        merged: t.MutableJsonMapping,
        live_payload: t.JsonMapping,
        project_keys: t.StrSequence,
    ) -> p.Result[t.JsonDict]:
        """Overlay every declared CUSTOM project key onto the merged document.

        Returns:
            The resulting ``p.Result[t.JsonDict]``.

        """
        project = dict(u.Cli.toml_mapping_child(merged, c.Infra.PROJECT) or {})
        live_project = u.Cli.toml_mapping_child(live_payload, c.Infra.PROJECT) or {}
        for key in project_keys:
            if key not in live_project:
                continue
            if key == c.Infra.DEPENDENCIES:
                validated = cls._validated_requirement_lists(
                    project,
                    live_project,
                    key,
                )
                if validated.failure:
                    return r[t.JsonDict].from_failure(validated)
                required, custom = validated.value
                project[key] = cls._merged_requirements(required, custom)
            else:
                project[key] = live_project[key]
        return r[t.JsonDict].ok(project)

    @staticmethod
    def _overlay_dev_group(
        merged: t.MutableJsonMapping,
        live_payload: t.JsonMapping,
    ) -> None:
        """Preserve the live project dev additions before conformance floors."""
        groups = dict(u.Cli.toml_mapping_child(merged, c.Infra.DEPENDENCY_GROUPS) or {})
        live_groups = (
            u.Cli.toml_mapping_child(live_payload, c.Infra.DEPENDENCY_GROUPS) or {}
        )
        if str(c.Infra.DEV) in live_groups:
            groups[str(c.Infra.DEV)] = live_groups[str(c.Infra.DEV)]
            merged[c.Infra.DEPENDENCY_GROUPS] = groups

    @staticmethod
    def _overlay_tool_tables(
        merged: t.MutableJsonMapping,
        live_payload: t.JsonMapping,
        tool_tables: t.StrSequence,
    ) -> None:
        """Copy every live tool table the fleet does not manage."""
        tool = dict(u.Cli.toml_mapping_child(merged, c.Infra.TOOL) or {})
        live_tool = u.Cli.toml_mapping_child(live_payload, c.Infra.TOOL) or {}
        managed = frozenset(tool_tables)
        tool.update({
            key: value for key, value in live_tool.items() if key not in managed
        })
        merged[c.Infra.TOOL] = tool

    @classmethod
    def overlay_preserved(
        cls,
        rendered: str,
        live: str | None,
        *,
        preserve_project_keys: t.StrSequence | None = None,
        managed_tool_tables: t.StrSequence | None = None,
    ) -> p.Result[str]:
        """Keep live CUSTOM project keys and unmanaged tool tables.

        Returns:
            The resulting ``p.Result[str]``.

        """
        spec = FlextInfraUtilitiesManagedConflicts.pyproject_managed_file()
        if spec.failure:
            return r[str].from_failure(spec)
        project_keys = (
            spec.value.preserve_project_keys
            if preserve_project_keys is None
            else preserve_project_keys
        )
        tool_tables = (
            spec.value.managed_tool_tables
            if managed_tool_tables is None
            else managed_tool_tables
        )
        rendered_payload = u.Cli.toml_mapping_from_text_result(rendered)
        # An absent live file takes the same canonicalization path as a present
        # one: the projection is the parse-merge-dump form, so first publication
        # and every later conform produce byte-identical output (fixed point).
        empty_payload: t.JsonMapping = {}
        live_payload = (
            u.Cli.toml_mapping_from_text_result(live)
            if live is not None
            else r[t.JsonMapping].ok(empty_payload)
        )
        if rendered_payload.failure:
            return r[str].fail(
                f"rendered pyproject is not valid TOML: {rendered_payload.error}",
                error_code=rendered_payload.error_code,
                error_data=rendered_payload.error_data,
                exception=rendered_payload.exception,
            )
        if live_payload.failure:
            return r[str].fail(
                f"live pyproject is not valid TOML: {live_payload.error}",
                error_code=live_payload.error_code,
                error_data=live_payload.error_data,
                exception=live_payload.exception,
            )
        merged = dict(rendered_payload.value)
        project = cls._overlay_project_surface(merged, live_payload.value, project_keys)
        if project.failure:
            return r[str].from_failure(project)
        merged[c.Infra.PROJECT] = project.value
        cls._overlay_dev_group(merged, live_payload.value)
        cls._overlay_tool_tables(merged, live_payload.value, tool_tables)
        return r[str].ok(u.Cli.toml_dumps(u.Cli.toml_document_from_mapping(merged)))


__all__: list[str] = ["FlextInfraUtilitiesPyprojectOverlay"]
