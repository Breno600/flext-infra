"""Requirement parsing and declared-dependency inspection helpers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from flext_infra import c, p, t


class FlextInfraUtilitiesDependenciesInspectionMixin:
    """Static helpers for inspecting dependency declarations in pyproject payloads."""

    @staticmethod
    def raw_requirement_values(raw: p.AttributeProbe) -> list[str]:
        """Collect requirement strings from dependency arrays or group tables.

        Returns:
            Requirement strings retained from the declared arrays.
        """
        from flext_infra._utilities import FlextInfraUtilitiesDependencies

        if isinstance(raw, Mapping):
            values: list[str] = []
            for group in raw.values():
                values.extend(
                    FlextInfraUtilitiesDependencies.raw_requirement_values(
                        group,
                    ),
                )
            return values
        if isinstance(raw, (list, tuple)):
            return [item for item in raw if isinstance(item, str)]
        return []

    @staticmethod
    def active_requirement(
        requirement: str,
        *,
        environment: t.StrMapping,
    ) -> str | None:
        """Evaluate a strictly parsed requirement on the consumer interpreter.

        Returns:
            The resulting ``str | None``.

        """
        parsed = Requirement(requirement)
        return (
            str(parsed)
            if parsed.marker is None
            or parsed.marker.evaluate(environment=dict(environment))
            else None
        )

    @staticmethod
    def dependency_extras(requirements: t.StrSequence, name: str) -> str:
        """Retain the union of requested extras for one selected distribution.

        Returns:
            The resulting ``str``.

        """
        extras: set[str] = set()
        for requirement in requirements:
            parsed = Requirement(requirement)
            if canonicalize_name(parsed.name) == name:
                extras.update(parsed.extras)
        return f"[{','.join(sorted(extras))}]" if extras else ""

    @staticmethod
    def dependency_constraint(requirement: str, *, replace_source: bool) -> str:
        """Keep version bounds while installation inputs own extras and sources.

        Returns:
            The resulting ``str``.

        """
        parsed = Requirement(requirement)
        source = (
            f" @ {parsed.url}"
            if parsed.url and not replace_source
            else str(parsed.specifier)
        )
        marker = f"; {parsed.marker}" if parsed.marker is not None else ""
        return f"{parsed.name}{source}{marker}"

    @staticmethod
    def dep_name(requirement: str, *, active_only: bool = False) -> str | None:
        """Extract one normalized dependency name, optionally evaluating markers.

        Returns:
            The resulting ``str | None``.

        """
        text = requirement.strip()
        if not text:
            return None
        try:
            parsed = Requirement(text)
        except InvalidRequirement:
            parsed = None
        if parsed is not None:
            if (
                active_only
                and parsed.marker is not None
                and not parsed.marker.evaluate()
            ):
                return None
            return canonicalize_name(parsed.name)
        if ";" in text:
            text = text.split(";", maxsplit=1)[0].strip()
        if " @ " in text:
            text = text.split(" @ ", maxsplit=1)[0].strip()
        for separator in ("[", "==", ">=", "<=", "~=", "!=", ">", "<"):
            if separator in text:
                text = text.split(separator, maxsplit=1)[0].strip()
        if "/" in text:
            text = text.rsplit("/", maxsplit=1)[-1].strip()
        normalized = text.lower()
        return normalized or None

    @classmethod
    def project_dependency_names_from_payload(
        cls,
        payload: t.JsonMapping,
    ) -> t.StrSequence:
        """Return strict names from the PEP 621 runtime dependency array.

        Returns:
            Strict names from the PEP 621 runtime dependency array.

        Raises:
            TypeError: If pyproject payload must define a [project] mapping; or if
                [project].dependencies must be an array of requirement strings; or if
                [project].dependencies entries must be strings.
            ValueError: If [project].dependencies entries must not be blank.

        """
        project = payload.get(c.Infra.PROJECT)
        if not isinstance(project, Mapping):
            msg = "pyproject payload must define a [project] mapping"
            raise TypeError(msg)
        raw_dependencies = project.get(c.Infra.DEPENDENCIES, [])
        if not isinstance(raw_dependencies, list):
            msg = "[project].dependencies must be an array of requirement strings"
            raise TypeError(msg)
        names: list[str] = []
        for raw_requirement in raw_dependencies:
            if not isinstance(raw_requirement, str):
                msg = "[project].dependencies entries must be strings"
                raise TypeError(msg)
            dependency_name = cls.dep_name(raw_requirement)
            if dependency_name is None:
                msg = "[project].dependencies entries must not be blank"
                raise ValueError(msg)
            names.append(dependency_name)
        return tuple(names)

    @staticmethod
    def dedupe_specs(specs: t.StrSequence) -> t.StrSequence:
        """Return deterministic unique dependency specs keyed by normalized name.

        Returns:
            Deterministic unique dependency specs keyed by normalized name.

        """
        from flext_infra._utilities import FlextInfraUtilitiesDependencies

        selected_by_name: MutableMapping[str, str] = {}
        for raw in specs:
            item = raw.strip()
            if not item:
                continue
            dependency_name = FlextInfraUtilitiesDependencies.dep_name(item)
            if dependency_name is None or dependency_name in selected_by_name:
                continue
            selected_by_name[dependency_name] = item
        return tuple(selected_by_name[name] for name in sorted(selected_by_name))

    @classmethod
    def declared_dependency_names(
        cls,
        document: t.Cli.TomlDocument,
    ) -> t.StrSequence:
        """Return normalized dependency names from one TOML document.

        Returns:
            Normalized dependency names from one TOML document.

        """
        from flext_infra._utilities import FlextInfraUtilitiesPyproject

        normalized = FlextInfraUtilitiesPyproject.normalized_toml_payload(
            document,
        )
        if not normalized:
            return ()
        return cls.declared_dependency_names_from_payload(normalized)

    @classmethod
    def declared_dependency_names_from_payload(
        cls,
        payload: t.JsonMapping,
    ) -> t.StrSequence:
        """Return normalized dependency names across supported dependency tables.

        Returns:
            Normalized dependency names across supported dependency tables.

        """
        names: set[str] = set()
        cls._append_project_dependency_names(payload=payload, names=names)
        cls._append_dependency_group_names(payload=payload, names=names)
        cls._append_poetry_dependency_names(payload=payload, names=names)
        return tuple(sorted(names))

    @classmethod
    def _append_project_dependency_names(
        cls,
        *,
        payload: t.JsonMapping,
        names: set[str],
    ) -> None:
        """Append project dependency names."""
        project = payload.get(c.Infra.PROJECT)
        if not isinstance(project, Mapping):
            return
        cls._append_requirement_names(
            raw_requirements=project.get(c.Infra.DEPENDENCIES),
            names=names,
        )
        optional_dependencies = project.get(c.Infra.OPTIONAL_DEPENDENCIES)
        if not isinstance(optional_dependencies, Mapping):
            return
        for raw_requirements in optional_dependencies.values():
            cls._append_requirement_names(
                raw_requirements=raw_requirements,
                names=names,
            )

    @classmethod
    def _append_dependency_group_names(
        cls,
        *,
        payload: t.JsonMapping,
        names: set[str],
    ) -> None:
        """Append dependency group names."""
        dependency_groups = payload.get(c.Infra.DEPENDENCY_GROUPS)
        if not isinstance(dependency_groups, Mapping):
            return
        for raw_requirements in dependency_groups.values():
            cls._append_requirement_names(
                raw_requirements=raw_requirements,
                names=names,
            )

    @classmethod
    def _append_poetry_dependency_names(
        cls,
        *,
        payload: t.JsonMapping,
        names: set[str],
    ) -> None:
        """Append poetry dependency names."""
        tool = payload.get(c.Infra.TOOL)
        if not isinstance(tool, Mapping):
            return
        poetry = tool.get(c.Infra.POETRY)
        if not isinstance(poetry, Mapping):
            return
        cls._append_mapping_dependency_names(
            raw_mapping=poetry.get(c.Infra.DEPENDENCIES),
            names=names,
        )
        poetry_groups = poetry.get(c.Infra.GROUP)
        if not isinstance(poetry_groups, Mapping):
            return
        for raw_group in poetry_groups.values():
            if not isinstance(raw_group, Mapping):
                continue
            cls._append_mapping_dependency_names(
                raw_mapping=raw_group.get(c.Infra.DEPENDENCIES),
                names=names,
            )

    @classmethod
    def _append_requirement_names(
        cls,
        *,
        raw_requirements: t.JsonValue,
        names: set[str],
    ) -> None:
        """Append requirement names."""
        if not isinstance(raw_requirements, list):
            return
        for raw_requirement in raw_requirements:
            dependency_name = cls.dep_name(str(raw_requirement))
            if dependency_name is None:
                continue
            names.add(dependency_name)

    @classmethod
    def _append_mapping_dependency_names(
        cls,
        *,
        raw_mapping: t.JsonValue,
        names: set[str],
    ) -> None:
        """Append mapping dependency names."""
        if not isinstance(raw_mapping, Mapping):
            return
        for raw_name in raw_mapping:
            dependency_name = cls.dep_name(raw_name)
            if dependency_name is None or dependency_name == "python":
                continue
            names.add(dependency_name)

    @classmethod
    def local_dependency_names_from_payload(
        cls,
        payload: t.JsonMapping,
        *,
        workspace_project_names: t.StrSequence = (),
    ) -> t.StrSequence:
        """Return workspace-local dependency names from one payload.

        Returns:
            Workspace-local dependency names from one payload.

        """
        declared = set(cls.declared_dependency_names_from_payload(payload))
        if not workspace_project_names:
            return ()
        workspace_names = set(workspace_project_names)
        return tuple(
            sorted(name for name in declared if name in workspace_names),
        )


__all__: list[str] = ["FlextInfraUtilitiesDependenciesInspectionMixin"]
