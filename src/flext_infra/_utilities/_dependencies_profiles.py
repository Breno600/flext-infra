"""Dev-group and dependency-profile surfaces of the dependency facade.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType

from flext_infra import c, m, t


class FlextInfraUtilitiesDependenciesProfilesMixin:
    """Dev-group and dependency-profile surfaces of the dependency facade."""

    @staticmethod
    def project_dev_groups_from_payload(
        payload: t.JsonMapping,
    ) -> t.MappingKV[str, t.StrSequence]:
        """Collect optional dependency groups from one normalized payload.

        Returns:
            The resulting ``t.MappingKV[str, t.StrSequence]``.

        """
        from flext_cli import u

        project = u.Cli.json_as_mapping(payload.get(c.Infra.PROJECT, None))
        optional = u.Cli.json_as_mapping(
            project.get(c.Infra.OPTIONAL_DEPENDENCIES, None),
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
        cls,
        document: t.Cli.TomlDocument,
    ) -> t.MappingKV[str, t.StrSequence]:
        """Collect optional dependency groups from one TOML document.

        Returns:
            The resulting ``t.MappingKV[str, t.StrSequence]``.

        """
        from flext_infra._utilities import FlextInfraUtilitiesPyproject

        normalized = FlextInfraUtilitiesPyproject.normalized_toml_payload(
            document,
        )
        if not normalized:
            # Keep the empty mapping immutable and fully typed.
            return MappingProxyType(dict[str, t.VariadicTuple[str]]())
        return cls.project_dev_groups_from_payload(normalized)

    @classmethod
    def canonical_dev_dependencies(
        cls,
        document: t.Cli.TomlDocument,
    ) -> t.StrSequence:
        """Merge all canonical dev dependency groups from one TOML document.

        Returns:
            The resulting ``t.StrSequence``.

        """
        from flext_infra._utilities import FlextInfraUtilitiesPyproject

        normalized = FlextInfraUtilitiesPyproject.normalized_toml_payload(
            document,
        )
        if not normalized:
            return ()
        return cls.canonical_dev_dependencies_from_payload(normalized)

    @classmethod
    def canonical_dev_dependencies_from_payload(
        cls,
        payload: t.JsonMapping,
    ) -> t.StrSequence:
        """Merge all canonical dev dependency groups from one normalized payload.

        Returns:
            The resulting ``t.StrSequence``.

        """
        from flext_infra._utilities import FlextInfraUtilitiesDependencies

        groups = cls.project_dev_groups_from_payload(payload)
        return FlextInfraUtilitiesDependencies.dedupe_specs([
            requirement
            for group in c.Infra.CANONICAL_DEV_DEPENDENCY_GROUPS
            for requirement in groups.get(str(group), ())
        ])

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

        Returns:
            The most specific shared profile upstreams one project selects.

        """
        from flext_infra._utilities import FlextInfraUtilitiesDependencies

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
                if (
                    name := FlextInfraUtilitiesDependencies.dep_name(
                        dependency,
                    )
                )
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

        Returns:
            The shared upstream profile followed by the project's additions.

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
        return (
            base,
            *(item for item in profiles if item.project == distribution),
        )

    @classmethod
    def composed_dependency_profile(
        cls,
        profiles: t.SequenceOf[m.Infra.ScaffoldDependencyProfileSpec],
        *,
        upstream: str,
        distribution: str,
    ) -> m.Infra.ScaffoldDependencyProfileSpec | None:
        """Compose the shared upstream and project-specific dependency rows once.

        Returns:
            The resulting ``m.Infra.ScaffoldDependencyProfileSpec | None``.
        """
        rows = cls.dependency_profile_rows(
            profiles,
            upstream=upstream,
            distribution=distribution,
        )
        if not rows:
            return None
        profile, *additions = rows
        if not additions:
            return profile
        return m.Infra.ScaffoldDependencyProfileSpec.model_validate(
            {
                **profile.model_dump(),
                "runtime": tuple(
                    dict.fromkeys((
                        *profile.runtime,
                        *(
                            requirement
                            for item in additions
                            for requirement in item.runtime
                        ),
                    )),
                ),
                "codegen": tuple(
                    dict.fromkeys((
                        *profile.codegen,
                        *(
                            requirement
                            for item in additions
                            for requirement in item.codegen
                        ),
                    )),
                ),
            },
        )


__all__: list[str] = ["FlextInfraUtilitiesDependenciesProfilesMixin"]
