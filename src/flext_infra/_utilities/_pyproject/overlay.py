"""Preserve live CUSTOM project keys and unmanaged tool tables over renders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_cli import r, u

from flext_infra import c, t

from ..dependencies import FlextInfraUtilitiesDependencies
from ..managed_conflicts import FlextInfraUtilitiesManagedConflicts
from .requirements import FlextInfraUtilitiesPyprojectRequirements

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesPyprojectOverlay:
    """Merge one rendered pyproject with its live CUSTOM surface."""

    @classmethod
    def overlay_preserved(
        cls,
        rendered: str,
        live: str | None,
        *,
        preserve_project_keys: t.StrSequence | None = None,
        managed_tool_tables: t.StrSequence | None = None,
    ) -> p.Result[str]:
        """Keep live CUSTOM project keys and unmanaged tool tables."""
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
        rendered_payload = u.Cli.toml_mapping_from_text(rendered)
        # An absent live file takes the same canonicalization path as a present
        # one: the projection is the parse-merge-dump form, so first publication
        # and every later conform produce byte-identical output (fixed point).
        empty_payload: t.JsonMapping = {}
        live_payload = (
            u.Cli.toml_mapping_from_text(live) if live is not None else empty_payload
        )
        if rendered_payload is None:
            return r[str].fail("rendered pyproject is not valid TOML")
        if live_payload is None:
            return r[str].fail("live pyproject is not valid TOML")
        merged = dict(rendered_payload)
        project = dict(u.Cli.toml_mapping_child(merged, c.Infra.PROJECT) or {})
        live_project = u.Cli.toml_mapping_child(live_payload, c.Infra.PROJECT) or {}
        for key in project_keys:
            if key in live_project:
                if key == c.Infra.DEPENDENCIES:
                    validated_required: p.Result[t.StrSequence] = u.validate_value(
                        t.Infra.STR_SEQ_ADAPTER, project.get(key, []), strict=True
                    )
                    if validated_required.failure:
                        return r[str].fail_op(
                            "validate runtime dependencies", validated_required.error
                        )
                    validated_custom: p.Result[t.StrSequence] = u.validate_value(
                        t.Infra.STR_SEQ_ADAPTER, live_project[key], strict=True
                    )
                    if validated_custom.failure:
                        return r[str].fail_op(
                            "validate runtime dependencies", validated_custom.error
                        )
                    required = validated_required.value
                    custom = validated_custom.value
                    owned_names = {
                        FlextInfraUtilitiesDependencies.dep_name(item)
                        for item in required
                    }
                    # Profiles own same-name requirements. CUSTOM requirements
                    # retain full specs, including distinct markers for one name.
                    # Conformance uses this same order: overlay must not move
                    # generated requirements ahead of preserved custom ones.
                    project[key] = list[t.JsonValue](
                        sorted(
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
                        )
                    )
                else:
                    project[key] = live_project[key]
        merged[c.Infra.PROJECT] = project
        # Preserve project dev additions before conformance reapplies fleet floors.
        groups = dict(u.Cli.toml_mapping_child(merged, c.Infra.DEPENDENCY_GROUPS) or {})
        live_groups = (
            u.Cli.toml_mapping_child(live_payload, c.Infra.DEPENDENCY_GROUPS) or {}
        )
        if str(c.Infra.DEV) in live_groups:
            groups[str(c.Infra.DEV)] = live_groups[str(c.Infra.DEV)]
            merged[c.Infra.DEPENDENCY_GROUPS] = groups
        tool = dict(u.Cli.toml_mapping_child(merged, c.Infra.TOOL) or {})
        live_tool = u.Cli.toml_mapping_child(live_payload, c.Infra.TOOL) or {}
        managed = frozenset(tool_tables)
        tool.update({
            key: value for key, value in live_tool.items() if key not in managed
        })
        merged[c.Infra.TOOL] = tool
        return r[str].ok(u.Cli.toml_dumps(u.Cli.toml_document_from_mapping(merged)))


__all__: list[str] = ["FlextInfraUtilitiesPyprojectOverlay"]
