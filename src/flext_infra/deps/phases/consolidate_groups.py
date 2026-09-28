"""Phase: Consolidate optional-dependencies and Poetry groups into single dev group."""

from __future__ import annotations

from flext_infra import c, t, u


class FlextInfraConsolidateGroupsPhase:
    """Consolidate optional-dependencies and Poetry groups into single dev group."""

    @staticmethod
    def _merged_dev_requirements(
        existing: t.MappingKV[str, t.StrSequence], canonical_dev: t.StrSequence
    ) -> t.StrSequence:
        """Merge the canonical dev requirements with every legacy dev group."""
        return u.Infra.dedupe_specs([
            *canonical_dev,
            *[
                requirement
                for group in c.Infra.CANONICAL_DEV_DEPENDENCY_GROUPS
                for requirement in existing.get(str(group), ())
            ],
        ])

    def apply_payload(
        self, payload: t.MutableJsonMapping, canonical_dev: t.StrSequence
    ) -> t.StrSequence:
        """Merge legacy groups into one canonical dev group in one plain payload."""
        changes: t.MutableSequenceOf[str] = []
        project = u.Cli.toml_mapping_ensure_table(payload, c.Infra.PROJECT)
        optional = u.Cli.toml_mapping_ensure_table(
            project, c.Infra.OPTIONAL_DEPENDENCIES
        )
        merged_dev = self._merged_dev_requirements(
            u.Infra.project_dev_groups_from_payload(payload), canonical_dev
        )
        if u.Cli.toml_mapping_sync_string_list(
            optional, c.Infra.DEV, sorted(merged_dev)
        ):
            changes.append("project.optional-dependencies.dev consolidated")
        for old_key in c.Infra.LEGACY_DEV_DEPENDENCY_GROUPS:
            if u.Cli.toml_mapping_remove_key_if_present(optional, old_key):
                changes.append(f"project.optional-dependencies.{old_key} removed")
        poetry_group = u.Cli.toml_mapping_path(
            payload, (c.Infra.TOOL, c.Infra.POETRY, c.Infra.GROUP)
        )
        for old_group in c.Infra.LEGACY_DEV_DEPENDENCY_GROUPS:
            old_deps = u.Cli.toml_mapping_path(
                payload,
                (
                    c.Infra.TOOL,
                    c.Infra.POETRY,
                    c.Infra.GROUP,
                    old_group,
                    c.Infra.DEPENDENCIES,
                ),
            )
            if old_deps is not None:
                poetry_dev = u.Cli.toml_mapping_ensure_path(
                    payload,
                    (
                        c.Infra.TOOL,
                        c.Infra.POETRY,
                        c.Infra.GROUP,
                        c.Infra.DEV,
                        c.Infra.DEPENDENCIES,
                    ),
                )
                for dep_name, dep_value in old_deps.items():
                    _ = poetry_dev.setdefault(dep_name, dep_value)
            if poetry_group is not None and u.Cli.toml_mapping_remove_key_if_present(
                poetry_group, old_group
            ):
                changes.append(f"tool.poetry.group.{old_group} removed")
        deptry = u.Cli.toml_mapping_ensure_path(payload, (c.Infra.TOOL, c.Infra.DEPTRY))
        if u.Cli.toml_mapping_sync_string_list(
            deptry, "pep621_dev_dependency_groups", [c.Infra.DEV]
        ):
            changes.append("tool.deptry.pep621_dev_dependency_groups set to ['dev']")
        return changes


__all__: list[str] = ["FlextInfraConsolidateGroupsPhase"]
