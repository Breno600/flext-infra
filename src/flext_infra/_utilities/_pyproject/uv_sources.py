"""Conform-owned ``[tool.uv]`` rendering for one pyproject document.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from flext_cli import r, u

from flext_infra import c, t
from flext_infra._utilities._pyproject.requirements import (
    FlextInfraUtilitiesPyprojectRequirements,
)
from flext_infra._utilities._pyproject.session import (
    FlextInfraUtilitiesPyprojectSession,
)
from flext_infra._utilities.dependencies import FlextInfraUtilitiesDependencies

if TYPE_CHECKING:
    from flext_infra import m, p


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
                requirements.extend(cls.raw_requirement_values(project.get(key)))
        groups = payload.get(c.Infra.DEPENDENCY_GROUPS)
        if isinstance(groups, Mapping):
            for group in groups.values():
                requirements.extend(cls.raw_requirement_values(group))
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

    @classmethod
    def _sync_uv_sources(
        cls,
        document: t.Cli.TomlDocument,
        *,
        resolution: m.Infra.UvResolutionSpec,
        candidate_sources: t.StrMapping,
    ) -> p.Result[bool]:
        """Render the conform-owned ``[tool.uv]`` keys and drop workspace sources.

        The resolver keys are always declared, so the table always exists and
        never ends empty.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        tool = u.Cli.toml_table_child(document, c.Infra.TOOL)
        if tool is None:
            tool = u.Cli.toml_ensure_table(document, c.Infra.TOOL)
        uv = u.Cli.toml_table_child(tool, "uv")
        if uv is None:
            uv = u.Cli.toml_ensure_table(tool, "uv")
        # A declared candidate commit replaces every direct and transitive
        # requirement for that distribution during staging. The candidate
        # manifest owns this temporary pin; the committed lock owns normal
        # resolutions when no candidate is declared (flext-oe420).
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
        u.Cli.toml_remove_key_if_present(uv, "required-version")
        # Constraints are SSOT-rendered: the declared config value is the only
        # source, so a removed declaration exterminates the key everywhere and
        # no orphan cap can survive without an owner.
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
        # uv carries no cooldown key: `exclude-newer` (any form) is banned
        # (operator 2026-09-16). The fleet cooldown lives once in
        # codegen.toolchain.dependency_cooldown_days and reaches mise and
        # dependabot (operator 2026-10-01). Removed declarations exterminate
        # the keys everywhere so no orphan cap survives (flext-gzfd2 class).
        u.Cli.toml_remove_key_if_present(uv, "exclude-newer")
        u.Cli.toml_remove_key_if_present(uv, "exclude-newer-package")
        # Environments come from the fleet toolchain SSOT: an empty declaration
        # removes the key so uv resolves every environment, and a declared
        # sequence skips the splits the fleet does not support (win32 resolves
        # meltano's structlog cap against flext-core's floor and is
        # unsatisfiable).
        if resolution.environments:
            # Declared as list[JsonValue], not list[str]: `list` is invariant,
            # so the narrower element type is not assignable to the writer's
            # parameter even though every element is a valid JsonValue.
            environments: list[t.JsonValue] = list(resolution.environments)
            u.Cli.toml_sync_value(uv, "environments", environments)
        else:
            u.Cli.toml_remove_key_if_present(uv, "environments")
        # Project is a flext-infra routing key only; uv scoped form is
        # {package={name, version?}, dependencies=[...]} (uv settings docs).
        # Emit on every owning pyproject so standalone CI clones resolve;
        # do not gate on owns_uv_root_policy (that stripped member excludes).
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
        # Each repository owns its own frozen lock and external environment.
        # A root uv workspace would require every gitlink in root-only CI.
        u.Cli.toml_remove_key_if_present(uv, "workspace")
        sources = u.Cli.toml_table_child(uv, "sources")
        if sources is None:
            return r[bool].ok(value=True)
        for source_name in tuple(sources):
            if source_name.startswith("flext-"):
                u.Cli.toml_remove_key_if_present(sources, source_name)
        if not tuple(sources):
            u.Cli.toml_remove_key_if_present(uv, "sources")
        return r[bool].ok(value=True)

    @staticmethod
    def raw_requirement_values(raw: p.AttributeProbe) -> list[str]:
        """Collect raw requirement strings from a dependencies value or group table.

        ``project.dependencies`` is one array while ``optional-dependencies``
        and ``dependency-groups`` are tables of arrays; this is the single
        owner of that shape for read-only requirement scans.

        Returns:
            The resulting ``list[str]``.

        """
        if isinstance(raw, Mapping):
            values: list[str] = []
            for group in raw.values():
                values.extend(
                    FlextInfraUtilitiesPyprojectUvSources.raw_requirement_values(group),
                )
            return values
        if isinstance(raw, (list, tuple)):
            return [item for item in raw if isinstance(item, str)]
        return []


__all__: list[str] = ["FlextInfraUtilitiesPyprojectUvSources"]
