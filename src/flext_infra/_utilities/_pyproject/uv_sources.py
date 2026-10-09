"""Conform-owned ``[tool.uv]`` rendering for one pyproject document.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from flext_cli import r, u

from flext_infra import c, m, p, t
from flext_infra._utilities import FlextInfraUtilitiesDependencies
from flext_infra._utilities._pyproject.requirements import (
    FlextInfraUtilitiesPyprojectRequirements,
)
from flext_infra._utilities._pyproject.session import (
    FlextInfraUtilitiesPyprojectSession,
)

if TYPE_CHECKING:
    from tomlkit.items import Table


class FlextInfraUtilitiesPyprojectUvSources(
    FlextInfraUtilitiesPyprojectRequirements,
    FlextInfraUtilitiesPyprojectSession,
):
    """Render the conform-owned ``[tool.uv]`` keys of one pyproject document."""

    @classmethod
    def _document_requirement_lines(
        cls,
        document: t.Cli.TomlDocument,
    ) -> p.Result[list[str]]:
        """Collect every declared requirement line of one pyproject document.

        Returns:
            The resulting ``p.Result[list[str]]``.

        """
        payload = u.Cli.toml_as_mapping(document)
        if payload is None:
            return r[list[str]].fail("pyproject document is not a TOML mapping")
        requirements: list[str] = []
        project = payload.get(c.Infra.PROJECT)
        if isinstance(project, Mapping):
            for key in (c.Infra.DEPENDENCIES, c.Infra.OPTIONAL_DEPENDENCIES):
                requirements.extend(
                    FlextInfraUtilitiesDependencies.raw_requirement_values(
                        project.get(key),
                    ),
                )
        groups = payload.get(c.Infra.DEPENDENCY_GROUPS)
        if isinstance(groups, Mapping):
            for group in groups.values():
                requirements.extend(
                    FlextInfraUtilitiesDependencies.raw_requirement_values(
                        group,
                    ),
                )
        return r[list[str]].ok(requirements)

    @classmethod
    def active_session_requirements(
        cls,
        document: t.Cli.TomlDocument,
        *,
        environment: t.StrMapping,
    ) -> t.VariadicTuple[str]:
        """Read strictly parsed requirements active on the consumer interpreter.

        Returns:
            The resulting ``t.VariadicTuple[str]``.

        """
        return tuple(
            active
            for item in cls._document_requirement_lines(document).unwrap()
            if (
                active := FlextInfraUtilitiesDependencies.active_requirement(
                    item,
                    environment=environment,
                )
            )
            is not None
        )

    @classmethod
    def direct_source_names(
        cls,
        document: t.Cli.TomlDocument,
    ) -> p.Result[t.VariadicTuple[str]]:
        """Name every requirement taken by direct ``@ source`` reference.

        Forks and local projects reach a project only this way, never from a
        registry, so this is the derived set the supply-chain cooldown skips.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[str]]``.

        """
        lines = cls._document_requirement_lines(document)
        if lines.failure:
            return r[t.VariadicTuple[str]].from_failure(lines)
        return r[t.VariadicTuple[str]].ok(
            tuple(
                sorted({
                    name
                    for item in lines.value
                    if cls._declares_direct_source(item)
                    and (name := FlextInfraUtilitiesDependencies.dep_name(item))
                    is not None
                }),
            ),
        )

    @staticmethod
    def _resolved_uv_table(document: t.Cli.TomlDocument) -> Table:
        """Return the ``[tool.uv]`` table, creating its nesting when absent.

        Returns:
            The resulting ``Table``.

        """
        tool = u.Cli.toml_table_child(document, c.Infra.TOOL)
        if tool is None:
            tool = u.Cli.toml_ensure_table(document, c.Infra.TOOL)
        uv = u.Cli.toml_table_child(tool, "uv")
        return uv if uv is not None else u.Cli.toml_ensure_table(tool, "uv")

    @staticmethod
    def _sync_uv_candidates(
        uv: Table,
        candidate_sources: t.StrMapping,
    ) -> None:
        """Sync the staging candidate pins over every resolved requirement.

        A declared candidate commit replaces every direct and transitive
        requirement for that distribution during staging. The candidate
        manifest owns this temporary pin; the committed lock owns normal
        resolutions when no candidate is declared (flext-oe420).
        """
        if candidate_sources:
            u.Cli.toml_sync_string_list(
                uv,
                "override-dependencies",
                [
                    f"{name} @ {source}"
                    for name, source in sorted(candidate_sources.items())
                ],
            )
        else:
            u.Cli.toml_remove_key_if_present(uv, "override-dependencies")

    @staticmethod
    def _sync_uv_constraints(
        uv: Table,
        resolution: m.Infra.UvResolutionSpec,
    ) -> None:
        """Sync the SSOT-rendered constraints, link mode, and banned cooldown keys.

        Constraints are SSOT-rendered: the declared config value is the only
        source, so a removed declaration exterminates the key everywhere and
        no orphan cap can survive without an owner. uv carries no cooldown
        key: `exclude-newer` (any form) is banned (operator 2026-09-16). The
        fleet cooldown lives once in
        codegen.toolchain.dependency_cooldown_days and reaches mise and
        dependabot (operator 2026-10-01). Removed declarations exterminate
        the keys everywhere so no orphan cap survives (flext-gzfd2 class).
        """
        retained_constraints = tuple(
            requirement
            for requirement in resolution.constraint_dependencies
            if FlextInfraUtilitiesDependencies.dep_name(requirement) != "uv"
        )
        if retained_constraints:
            u.Cli.toml_sync_string_list(
                uv,
                "constraint-dependencies",
                retained_constraints,
            )
        else:
            u.Cli.toml_remove_key_if_present(uv, "constraint-dependencies")
        u.Cli.toml_sync_value(uv, "link-mode", resolution.link_mode)
        u.Cli.toml_remove_key_if_present(uv, "exclude-newer")
        u.Cli.toml_remove_key_if_present(uv, "exclude-newer-package")

    @staticmethod
    def _sync_uv_environments(uv: Table, resolution: m.Infra.UvResolutionSpec) -> None:
        """Sync the fleet toolchain SSOT environments.

        Environments come from the fleet toolchain SSOT: an empty declaration
        removes the key so uv resolves every environment, and a declared
        sequence skips the splits the fleet does not support (win32 resolves
        meltano's structlog cap against flext-core's floor and is
        unsatisfiable).
        """
        if resolution.environments:
            # Declared as list[JsonValue], not list[str]: `list` is invariant,
            # so the narrower element type is not assignable to the writer's
            # parameter even though every element is a valid JsonValue.
            environments: list[t.JsonValue] = list(resolution.environments)
            u.Cli.toml_sync_value(uv, "environments", environments)
        else:
            u.Cli.toml_remove_key_if_present(uv, "environments")

    @staticmethod
    def _sync_uv_excludes(uv: Table, resolution: m.Infra.UvResolutionSpec) -> None:
        """Sync the uv scoped exclude-dependencies payload.

        Project is a flext-infra routing key only; uv scoped form is
        {package={name, version?}, dependencies=[...]} (uv settings docs).
        Emit on every owning pyproject so standalone CI clones resolve;
        do not gate on owns_uv_root_policy (that stripped member excludes).
        """
        exclude_payload = list(
            t.Cli.JSON_LIST_ADAPTER.validate_python([
                {
                    key: value
                    for key, value in item.model_dump(
                        mode="json",
                        exclude_none=True,
                    ).items()
                    if key != "project"
                }
                for item in resolution.exclude_dependencies
            ]),
        )
        if exclude_payload:
            u.Cli.toml_sync_value(uv, "exclude-dependencies", exclude_payload)
        else:
            u.Cli.toml_remove_key_if_present(uv, "exclude-dependencies")

    @classmethod
    def _sync_uv_sources(
        cls,
        document: t.Cli.TomlDocument,
        *,
        resolution: m.Infra.UvResolutionSpec,
        candidate_sources: t.StrMapping,
        workspace_members: t.StrSequence = (),
        owns_workspace_table: bool = False,
    ) -> p.Result[bool]:
        """Render the conform-owned ``[tool.uv]`` keys and workspace identity.

        The resolver keys are always declared, so the table always exists and
        never ends empty.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        uv = cls._resolved_uv_table(document)
        cls._sync_uv_candidates(uv, candidate_sources)
        u.Cli.toml_remove_key_if_present(uv, "required-version")
        cls._sync_uv_constraints(uv, resolution)
        cls._sync_uv_environments(uv, resolution)
        cls._sync_uv_excludes(uv, resolution)
        cls._sync_uv_workspace(
            uv,
            workspace_members,
            owns_workspace_table=owns_workspace_table,
        )
        return r[bool].ok(value=True)

    @classmethod
    def _wanted_workspace_members(
        cls,
        document: t.Cli.TomlDocument,
        workspace_members: t.StrSequence,
    ) -> t.VariadicTuple[str]:
        """Intersect the declared members with the document's requirements.

        Returns:
            The resulting ``t.VariadicTuple[str]``.

        """
        from flext_infra._utilities import FlextInfraUtilitiesDependencies

        required_names = {
            name
            for line in cls._document_requirement_lines(document).unwrap()
            if (name := FlextInfraUtilitiesDependencies.dep_name(line)) is not None
        }
        return tuple(sorted(set(workspace_members) & required_names))

    @classmethod
    def _sync_member_sources(
        cls,
        uv: Table,
        wanted_members: t.VariadicTuple[str],
    ) -> None:
        """Prune stale member sources and redirect every wanted member."""
        sources = u.Cli.toml_table_child(uv, "sources")
        if sources is None:
            sources = u.Cli.toml_ensure_table(uv, "sources")
        for source_name in tuple(sources):
            if source_name not in wanted_members:
                u.Cli.toml_remove_key_if_present(sources, source_name)
        for member_name in wanted_members:
            u.Cli.toml_sync_value(sources, member_name, {"workspace": True})

    @staticmethod
    def _prune_member_sources(uv: Table) -> None:
        """Drop fleet member sources left over from a workspace render."""
        sources = u.Cli.toml_table_child(uv, "sources")
        if sources is None:
            return
        for source_name in tuple(sources):
            if source_name.startswith("flext-"):
                u.Cli.toml_remove_key_if_present(sources, source_name)
        if not tuple(sources):
            u.Cli.toml_remove_key_if_present(uv, "sources")

    @classmethod
    def _sync_uv_workspace(
        cls,
        uv: Table,
        workspace_members: t.StrSequence,
        *,
        owns_workspace_table: bool,
    ) -> None:
        """Render or remove the native uv workspace identity and its sources.

        The `[tool.uv.workspace]` TABLE is owned by the pyproject template
        alone: only the workspace root's render declares it, so a member
        manifest never grows a nested workspace (uv rejects nesting).
        Workspace-root sources apply to every member and override a member's
        direct ``@ git+`` requirement, so only the root redirects fleet
        members through ``[tool.uv.sources] workspace = true``. A member
        render is context-independent: attached or standalone, it carries no
        fleet source and resolves from its declared requirements in a clone.
        """
        if not owns_workspace_table:
            u.Cli.toml_remove_key_if_present(uv, "workspace")
            cls._prune_member_sources(uv)
            return
        cls._sync_member_sources(uv, tuple(sorted(workspace_members)))


__all__: list[str] = ["FlextInfraUtilitiesPyprojectUvSources"]
