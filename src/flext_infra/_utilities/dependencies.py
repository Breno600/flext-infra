"""Dependency parsing and inspection helpers for flext-infra utilities.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from importlib.metadata import distributions, requires
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_cli import u
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from flext_core import r

# Why: dependency_waves subscripts r[t.SequenceOf[t.StrSequence]] at runtime, so
# the typings facade cannot be TYPE_CHECKING-only here. c -> t is a forward
# facade import and stays cycle-free.
from flext_infra import c, t

from .pyproject import FlextInfraUtilitiesPyproject

if TYPE_CHECKING:
    from flext_infra import m, p


class FlextInfraUtilitiesDependencies:
    """Static helpers for inspecting dependency declarations in pyproject payloads."""

    @staticmethod
    def dep_name(requirement: str, *, active_only: bool = False) -> str | None:
        """Extract one normalized dependency name, optionally evaluating markers."""
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
        cls, payload: t.JsonMapping
    ) -> t.StrSequence:
        """Return strict names from the PEP 621 runtime dependency array."""
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
    def dependency_order(
        direct_names: t.StrSequence,
        *,
        dependencies: Callable[[str], t.StrSequence],
        prefix: str = "",
        normalize: Callable[[str], str] = canonicalize_name,
    ) -> t.StrSequence:
        """Return a dependency-first order for any named dependency graph."""
        graph: MutableMapping[str, t.VariadicTuple[str]] = {}

        def collect(dependency_name: str) -> None:
            normalized = normalize(dependency_name)
            if normalized in graph:
                return
            children = tuple(
                child
                for raw_child in dependencies(normalized)
                if (child := normalize(raw_child))
                and (not prefix or child.startswith(prefix))
            )
            graph[normalized] = children
            for dependency in children:
                collect(dependency)

        roots = tuple(
            normalized
            for name in direct_names
            if (normalized := normalize(name))
            and (not prefix or normalized.startswith(prefix))
        )
        for root in roots:
            collect(root)
        ordered: list[str] = []
        visited: set[str] = set()
        active: list[str] = []

        def visit(distribution_name: str) -> None:
            if distribution_name in visited:
                return
            if distribution_name in active:
                cycle_start = active.index(distribution_name)
                cycle = " -> ".join((*active[cycle_start:], distribution_name))
                msg = f"cyclic dependency graph: {cycle}"
                raise ValueError(msg)
            active.append(distribution_name)
            for dependency in graph[distribution_name]:
                visit(dependency)
            active.pop()
            visited.add(distribution_name)
            ordered.append(distribution_name)

        for root in roots:
            visit(root)
        return tuple(ordered)

    @staticmethod
    def dependency_waves(
        edges: Mapping[str, t.StrSequence],
    ) -> p.Result[t.SequenceOf[t.StrSequence]]:
        """Split a closed named dependency graph into dependency-first waves.

        Wave ``n`` contains only names whose dependencies all live in earlier
        waves, so each wave may proceed in parallel while the sequence between
        waves stays strict. The graph is closed: every referenced name must be
        a key of ``edges``; an unknown reference or a cycle fails the result
        instead of raising, so callers (release publish ordering, codemod
        provider ordering) compose it through ``p.Result`` chaining.
        """
        unknown = sorted({
            dependency
            for deps in edges.values()
            for dependency in deps
            if dependency not in edges
        })
        if unknown:
            return r[t.SequenceOf[t.StrSequence]].fail(
                "dependency graph references names outside the graph: "
                + ", ".join(unknown)
            )
        pending = {name: set(deps) for name, deps in edges.items()}
        waves: list[t.StrSequence] = []
        while pending:
            ready = frozenset(name for name, deps in pending.items() if not deps)
            if not ready:
                return r[t.SequenceOf[t.StrSequence]].fail(
                    "cyclic dependency graph: " + ", ".join(sorted(pending))
                )
            waves.append(tuple(sorted(ready)))
            pending = {
                name: deps - ready
                for name, deps in pending.items()
                if name not in ready
            }
        return r[t.SequenceOf[t.StrSequence]].ok(tuple(waves))

    @classmethod
    def project_dependency_resource_files(
        cls,
        project_root: Path,
        *,
        resource_parts: t.StrSequence,
        distribution_prefix: str = "",
        suffix: str = "",
    ) -> t.SequenceOf[Path]:
        """Resolve runtime, local, and test dependency resources in order."""
        pyproject = project_root / c.PYPROJECT_FILENAME
        payload = u.Cli.toml_read_json(pyproject).unwrap()
        project_name = canonicalize_name(
            FlextInfraUtilitiesPyproject.project_name_from_payload(
                project_root, payload
            )
        )
        declared_names = cls.declared_dependency_names_from_payload(payload)

        def installed_dependencies(name: str) -> t.StrSequence:
            return tuple(
                dependency
                for raw_requirement in requires(name) or ()
                if (dependency := cls.dep_name(raw_requirement, active_only=True))
                is not None
            )

        ordered = list(
            cls.dependency_order(
                declared_names,
                dependencies=installed_dependencies,
                prefix=distribution_prefix,
            )
        )
        package_names: MutableMapping[str, str] = {
            name: name.replace("-", "_") for name in ordered
        }
        if not distribution_prefix or project_name.startswith(distribution_prefix):
            if project_name not in ordered:
                ordered.append(project_name)
            package_names[project_name] = (
                FlextInfraUtilitiesPyproject.package_name_from_payload(
                    project_root,
                    payload,
                    FlextInfraUtilitiesPyproject.docs_meta_from_payload(payload),
                )
            )
        discovered: list[Path] = []
        seen: set[Path] = set()
        for distribution_name in ordered:
            resource = files(package_names[distribution_name])
            for part in resource_parts:
                resource /= part
            resource_root = Path(str(resource))
            if not resource_root.is_dir():
                continue
            for candidate in sorted(resource_root.rglob(f"*{suffix}")):
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    discovered.append(resolved)
        return tuple(discovered)

    @staticmethod
    def constraint_specifier(version: str) -> str:
        """Return the resolved installed version as an open-ended dependency floor.

        PEP 440 permits a local version label only with ``==`` or ``!=``, so a
        floor built straight from a locally tagged resolution is rejected by
        every build backend. The public release is what a floor means, and the
        local build satisfies it.

        A prerelease resolution is not a floor either: publishing ``>=X.Yb1``
        forces every downstream consumer onto that beta, which is how the fleet
        ended up pinned to ``pydantic>=2.14.0b1`` from a single runtime resolution. The
        empty string means "this resolution cannot serve as a public floor", and
        every caller keeps the declared constraint instead of rewriting it.
        """
        public_version = version.strip().partition("+")[0]
        if not public_version:
            return ""
        try:
            parsed_version = Version(public_version)
        except InvalidVersion:
            return ""
        if parsed_version.is_prerelease:
            return ""
        return f">={public_version}"

    @classmethod
    def resolved_dependency_versions(cls) -> t.MappingKV[str, str]:
        """Read registry versions from the provisioned runtime, never release provenance."""
        versions: dict[str, str] = {}
        for distribution in distributions():
            if distribution.read_text("direct_url.json") is not None:
                continue
            name = distribution.metadata.get("Name")
            if name is None:
                msg = "Installed distribution has no Name metadata"
                raise TypeError(msg)
            normalized = cls.dep_name(name)
            if normalized is None:
                msg = f"Invalid installed distribution name: {name}"
                raise ValueError(msg)
            version = distribution.version
            if normalized in versions and versions[normalized] != version:
                msg = f"Ambiguous installed version: {normalized}"
                raise ValueError(msg)
            versions[normalized] = version
        if not versions:
            msg = "No registry packages found in the provisioned runtime"
            raise ValueError(msg)
        return versions

    @classmethod
    def rewrite_requirement_constraint(
        cls,
        requirement: str,
        *,
        resolved_versions: t.MappingKV[str, str],
        internal_names: t.StrSequence = (),
    ) -> str | None:
        """Rewrite one PEP 621 requirement to the resolved runtime floor."""
        result: str | None = None
        raw_text = requirement.strip()
        if raw_text:
            requirement_part, marker_separator, marker_part = raw_text.partition(";")
            if " @ " not in requirement_part:
                head_match = c.Infra.PEP621_REQUIREMENT_HEAD_RE.match(
                    requirement_part.strip()
                )
                if head_match is not None:
                    head = head_match.group("head").strip()
                    dependency_name = cls.dep_name(head)
                    internal_set = set(internal_names)
                    if (
                        dependency_name is not None
                        and dependency_name not in internal_set
                    ):
                        locked_version = resolved_versions.get(dependency_name)
                        if locked_version is not None:
                            try:
                                parsed = Requirement(requirement_part.strip())
                            except InvalidRequirement:
                                parsed = None
                            if parsed is not None and not parsed.specifier.contains(
                                locked_version, prereleases=True
                            ):
                                return None
                            retained = (
                                ()
                                if parsed is None
                                else tuple(
                                    str(specifier)
                                    for specifier in parsed.specifier
                                    if specifier.operator in {"<", "<=", "!="}
                                )
                            )
                            constraint = cls.constraint_specifier(locked_version)
                            if not constraint:
                                return None
                            if retained:
                                constraint = ",".join((constraint, *retained))
                            rewritten = f"{head}{constraint}"
                            marker_text = marker_part.strip()
                            if marker_separator and marker_text:
                                rewritten = f"{rewritten}; {marker_text}"
                            result = rewritten if rewritten != raw_text else None
        return result

    @staticmethod
    def dedupe_specs(specs: t.StrSequence) -> t.StrSequence:
        """Return deterministic unique dependency specs keyed by normalized name."""
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
    def declared_dependency_names(cls, document: t.Cli.TomlDocument) -> t.StrSequence:
        """Return normalized dependency names from one TOML document."""
        normalized = FlextInfraUtilitiesPyproject.normalized_toml_payload(document)
        if not normalized:
            return ()
        return cls.declared_dependency_names_from_payload(normalized)

    @classmethod
    def declared_dependency_names_from_payload(
        cls, payload: t.JsonMapping
    ) -> t.StrSequence:
        """Return normalized dependency names across supported dependency tables."""
        names: set[str] = set()
        cls._append_project_dependency_names(payload=payload, names=names)
        cls._append_dependency_group_names(payload=payload, names=names)
        cls._append_poetry_dependency_names(payload=payload, names=names)
        return tuple(sorted(names))

    @classmethod
    def _append_project_dependency_names(
        cls, *, payload: t.JsonMapping, names: set[str]
    ) -> None:
        """Append project dependency names."""
        project = payload.get(c.Infra.PROJECT)
        if not isinstance(project, Mapping):
            return
        cls._append_requirement_names(
            raw_requirements=project.get(c.Infra.DEPENDENCIES), names=names
        )
        optional_dependencies = project.get(c.Infra.OPTIONAL_DEPENDENCIES)
        if not isinstance(optional_dependencies, Mapping):
            return
        for raw_requirements in optional_dependencies.values():
            cls._append_requirement_names(
                raw_requirements=raw_requirements, names=names
            )

    @classmethod
    def _append_dependency_group_names(
        cls, *, payload: t.JsonMapping, names: set[str]
    ) -> None:
        """Append dependency group names."""
        dependency_groups = payload.get(c.Infra.DEPENDENCY_GROUPS)
        if not isinstance(dependency_groups, Mapping):
            return
        for raw_requirements in dependency_groups.values():
            cls._append_requirement_names(
                raw_requirements=raw_requirements, names=names
            )

    @classmethod
    def _append_poetry_dependency_names(
        cls, *, payload: t.JsonMapping, names: set[str]
    ) -> None:
        """Append poetry dependency names."""
        tool = payload.get(c.Infra.TOOL)
        if not isinstance(tool, Mapping):
            return
        poetry = tool.get(c.Infra.POETRY)
        if not isinstance(poetry, Mapping):
            return
        cls._append_mapping_dependency_names(
            raw_mapping=poetry.get(c.Infra.DEPENDENCIES), names=names
        )
        poetry_groups = poetry.get(c.Infra.GROUP)
        if not isinstance(poetry_groups, Mapping):
            return
        for raw_group in poetry_groups.values():
            if not isinstance(raw_group, Mapping):
                continue
            cls._append_mapping_dependency_names(
                raw_mapping=raw_group.get(c.Infra.DEPENDENCIES), names=names
            )

    @classmethod
    def _append_requirement_names(
        cls, *, raw_requirements: t.JsonValue, names: set[str]
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
        cls, *, raw_mapping: t.JsonValue, names: set[str]
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
        cls, payload: t.JsonMapping, *, workspace_project_names: t.StrSequence = ()
    ) -> t.StrSequence:
        """Return workspace-local dependency names from one payload."""
        declared = set(cls.declared_dependency_names_from_payload(payload))
        if not workspace_project_names:
            return ()
        workspace_names = set(workspace_project_names)
        return tuple(sorted(name for name in declared if name in workspace_names))

    @staticmethod
    def project_dev_groups_from_payload(
        payload: t.JsonMapping,
    ) -> t.MappingKV[str, t.StrSequence]:
        """Collect optional dependency groups from one normalized payload."""
        project = u.Cli.json_as_mapping(payload.get(c.Infra.PROJECT, None))
        optional = u.Cli.json_as_mapping(
            project.get(c.Infra.OPTIONAL_DEPENDENCIES, None)
        )
        groups = {
            str(group): tuple(
                str(item) for item in u.Cli.json_as_sequence(optional.get(group, None))
            )
            for group in c.Infra.CANONICAL_DEV_DEPENDENCY_GROUPS
        }
        return {group: values for group, values in groups.items() if values}

    @classmethod
    def project_dev_groups(
        cls, document: t.Cli.TomlDocument
    ) -> t.MappingKV[str, t.StrSequence]:
        """Collect optional dependency groups from one TOML document."""
        normalized = FlextInfraUtilitiesPyproject.normalized_toml_payload(document)
        if not normalized:
            # flext-j47u (codex): keep the empty mapping immutable and fully typed.
            return MappingProxyType(dict[str, t.VariadicTuple[str]]())
        return cls.project_dev_groups_from_payload(normalized)

    @classmethod
    def canonical_dev_dependencies(cls, document: t.Cli.TomlDocument) -> t.StrSequence:
        """Merge all canonical dev dependency groups from one TOML document."""
        normalized = FlextInfraUtilitiesPyproject.normalized_toml_payload(document)
        if not normalized:
            return ()
        return cls.canonical_dev_dependencies_from_payload(normalized)

    @classmethod
    def canonical_dev_dependencies_from_payload(
        cls, payload: t.JsonMapping
    ) -> t.StrSequence:
        """Merge all canonical dev dependency groups from one normalized payload."""
        groups = cls.project_dev_groups_from_payload(payload)
        return cls.dedupe_specs([
            requirement
            for group in c.Infra.CANONICAL_DEV_DEPENDENCY_GROUPS
            for requirement in groups.get(str(group), ())
        ])

    @classmethod
    def flext_dependency_namespaces(cls, document: t.Cli.TomlDocument) -> t.StrSequence:
        """Extract declared FLEXT dependency namespaces from one TOML document."""
        normalized = FlextInfraUtilitiesPyproject.normalized_toml_payload(document)
        if not normalized:
            return ()
        return cls.flext_dependency_namespaces_from_payload(normalized)

    @classmethod
    def flext_dependency_namespaces_from_payload(
        cls, payload: t.MappingKV[str, t.JsonValue]
    ) -> t.StrSequence:
        """Extract every declared ``flext-*`` dependency as a Python namespace."""
        # flext-j47u (codex): FLEXT dependencies are first-party contracts even
        # when their uv source declaration is owned by an enclosing workspace.
        normalized = FlextInfraUtilitiesPyproject.validate_infra_payload(payload)
        return tuple(
            sorted(
                name.replace("-", "_")
                for name in cls.declared_dependency_names_from_payload(normalized)
                if name == "flext" or name.startswith(c.Infra.PKG_PREFIX_HYPHEN)
            )
        )

    @staticmethod
    def dependency_profile_upstreams(
        profiles: t.SequenceOf[m.Infra.ScaffoldDependencyProfileSpec],
        *,
        distribution: str,
        runtime_names: t.Infra.StrSet,
    ) -> t.StrSequence:
        """Return the most specific shared profile upstreams one project selects.

        The root of the dependency tree declares no upstream distribution: a
        distribution that IS a profile's upstream owns that profile. Otherwise
        every shared profile whose upstream is a runtime dependency is a
        candidate, and a candidate implied by another candidate's runtime is
        dropped. One entry is the governed selection; none means no declared
        profile governs the project; several are an ambiguous declaration.
        """
        shared = tuple(item for item in profiles if item.project is None)
        own = next(
            (
                item
                for item in shared
                if item.upstream.replace("_", "-") == distribution
            ),
            None,
        )
        candidates = (
            (own,)
            if own is not None
            else tuple(
                item
                for item in shared
                if item.upstream.replace("_", "-") in runtime_names
            )
        )
        runtime_of = {
            item.upstream: {
                name
                for dependency in item.runtime
                if (name := FlextInfraUtilitiesDependencies.dep_name(dependency))
            }
            for item in candidates
        }
        return tuple(
            item.upstream
            for item in candidates
            if not any(
                item.upstream.replace("_", "-") in runtime_of[other.upstream]
                for other in candidates
                if other is not item
            )
        )

    @staticmethod
    def dependency_profile_rows(
        profiles: t.SequenceOf[m.Infra.ScaffoldDependencyProfileSpec],
        *,
        upstream: str,
        distribution: str,
    ) -> t.SequenceOf[m.Infra.ScaffoldDependencyProfileSpec]:
        """Return the shared upstream profile followed by the project's additions.

        Empty when the upstream declares no shared profile.
        """
        base = next(
            (
                item
                for item in profiles
                if item.project is None and item.upstream == upstream
            ),
            None,
        )
        if base is None:
            return ()
        return (base, *(item for item in profiles if item.project == distribution))


__all__: list[str] = ["FlextInfraUtilitiesDependencies"]
